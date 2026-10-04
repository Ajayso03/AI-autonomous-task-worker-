"""Core Autonomous AI Task Worker Orchestration Runtime."""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from app.config import settings
from app.models.task import (
    TaskStatus,
    StepAction,
    StepObservation,
    StepDecision,
    StepTrace,
    AgentPlan,
    AgentExecutionSummary,
)
from app.models.tools import ToolCall, ToolResult
from app.models.approval import ApprovalRequest, ApprovalDecision, ApprovalStatus
from app.models.verification import VerificationReport
from app.tools.registry import ToolRegistry, default_registry
from app.llm import get_llm_provider, BaseLLMProvider
from app.agent.memory import AgentMemory
from app.agent.planner import DynamicPlanner
from app.agent.safety import SafetyPolicyEngine
from app.agent.recovery import RecoveryEngine
from app.agent.verifier import IndependentOutcomeVerifier

logger = logging.getLogger("AutonomousWorker")


class AutonomousWorker:
    """The Autonomous AI Task Worker Runtime.

    Implements the complete enterprise cognitive loop:
    Goal → Understand → Plan → Execute → Observe → Adapt → Verify → Complete
    """

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        tool_registry: Optional[ToolRegistry] = None,
        max_steps: Optional[int] = None,
    ):
        self.llm_provider = llm_provider or get_llm_provider()
        self.tool_registry = tool_registry or default_registry
        self.max_steps = max_steps or settings.agent_max_steps
        self.planner = DynamicPlanner(self.llm_provider)
        self.safety_engine = SafetyPolicyEngine()
        self.recovery_engine = RecoveryEngine()
        self.verifier = IndependentOutcomeVerifier()

    def run(
        self,
        goal: str,
        task_id: Optional[str] = None,
        pause_for_approval: bool = False,
        approval_handler: Optional[Callable[[ApprovalRequest], bool]] = None,
    ) -> AgentExecutionSummary:
        """Executes a natural language task autonomously from end to end."""
        start_time = time.perf_counter()
        task_id = task_id or f"TASK-{uuid.uuid4().hex[:8].upper()}"

        memory = AgentMemory()
        available_tools = self.tool_registry.list_definitions()

        # 1. UNDERSTAND & PLAN
        plan = self.planner.create_initial_plan(goal, available_tools)

        traces: List[StepTrace] = []
        status = TaskStatus.EXECUTING
        completion_msg = ""
        verification_report: Optional[VerificationReport] = None
        pending_approval: Optional[ApprovalRequest] = None

        step_idx = 1
        while step_idx <= self.max_steps and status == TaskStatus.EXECUTING:
            # 2. DECIDE NEXT ACTION
            action, decision, is_terminal = self.llm_provider.decide_next_action(
                goal=goal,
                plan=plan,
                available_tools=available_tools,
                working_memory=memory.working_memory,
                history_traces=memory.history_traces,
                step_number=step_idx,
            )

            # TERMINAL CONDITION
            if is_terminal:
                # 7. INDEPENDENT VERIFICATION
                inv_data = memory.get("invoice_data", {})
                inv_num = inv_data.get("invoice_number")

                if inv_num:
                    check_ledger = "ledger" in goal.lower() or "disbursement" in goal.lower()
                    verification_report = self.verifier.verify_invoice_processing(
                        invoice_number=inv_num,
                        expected_vendor=inv_data.get("vendor_name"),
                        expected_amount=inv_data.get("amount"),
                        expected_due_date=inv_data.get("due_date"),
                        check_ledger=check_ledger,
                    )
                    if verification_report.verified:
                        status = TaskStatus.COMPLETED_VERIFIED
                        completion_msg = f"Task completed and independently verified: {verification_report.summary}"
                    else:
                        status = TaskStatus.COMPLETED_UNVERIFIED
                        completion_msg = f"Task completed but independent verification found discrepancies: {verification_report.summary}"
                else:
                    status = TaskStatus.COMPLETED_UNVERIFIED
                    completion_msg = "Task finished, but no target invoice record was identified for verification."

                break

            # 3. SAFETY & POLICY EVALUATION
            approval_req = self.safety_engine.evaluate_proposed_action(
                task_id=task_id,
                tool_name=action.tool_name,
                arguments=action.arguments,
                memory=memory,
            )

            if approval_req:
                if pause_for_approval and not approval_handler:
                    # Pause execution for human-in-the-loop interaction
                    status = TaskStatus.AWAITING_APPROVAL
                    pending_approval = approval_req
                    completion_msg = f"Execution paused: Action '{action.tool_name}' requires human approval ({approval_req.reason})"
                    break
                elif approval_handler:
                    is_approved = approval_handler(approval_req)
                    if is_approved:
                        action.arguments["approved_by"] = "human_operator"
                        memory.set("approved_by", "human_operator")
                    else:
                        status = TaskStatus.FAILED
                        completion_msg = "Action rejected by human operator policy check."
                        break
                else:
                    # By default in non-interactive run, record approval requirement and flag
                    status = TaskStatus.AWAITING_APPROVAL
                    pending_approval = approval_req
                    completion_msg = f"Action '{action.tool_name}' halted: requires managerial approval."
                    break

            # 4. EXECUTE ACTION
            tool_call = ToolCall(tool_name=action.tool_name, arguments=action.arguments)
            tool_result = self.tool_registry.execute(tool_call)

            # 5. OBSERVE
            obs = StepObservation(
                success=tool_result.success,
                summary=tool_result.output,
                data=tool_result.data,
                evidence=tool_result.evidence,
                error=tool_result.error,
                execution_time_ms=tool_result.execution_time_ms,
            )

            # 6. ADAPT & UPDATE MEMORY
            if tool_result.success:
                if action.tool_name == "search_company_documents":
                    memory.set("search_results", tool_result.data.get("results", []))
                elif action.tool_name == "extract_invoice_data":
                    memory.set("invoice_data", tool_result.data)
                elif action.tool_name == "query_vendor_portal":
                    # Adapt: portal query returned clean records, merge into invoice_data
                    recs = tool_result.data.get("records", [])
                    if recs:
                        prec = recs[0]
                        cur_data = memory.get("invoice_data", {}) or {}
                        cur_data["due_date"] = prec.get("due_date")
                        cur_data["amount"] = prec.get("total_amount")
                        cur_data["vendor_name"] = prec.get("vendor_name")
                        cur_data["invoice_number"] = prec.get("invoice_number")
                        memory.set("invoice_data", cur_data)
                elif action.tool_name == "query_accounts_payable":
                    memory.set("erp_checked", True)
                    if tool_result.data and tool_result.data.get("count", 0) > 0:
                        memory.set("existing_erp_record", True)
                        memory.set("payable_created", True)
                elif action.tool_name == "create_payable_record":
                    memory.set("payable_created", True)
                elif action.tool_name == "record_ledger_disbursement":
                    memory.set("ledger_recorded", True)
                elif action.tool_name == "inspect_database_record":
                    memory.set("verified_in_db", True)
            else:
                # FAILURE HANDLING & RECOVERY
                can_recover, strat_msg, alt_call = self.recovery_engine.analyze_failure(
                    tool_call=tool_call,
                    result=tool_result,
                    memory=memory,
                )
                if can_recover and alt_call:
                    decision.next_step = f"Recovering: {strat_msg}"
                    decision.reason = f"Failure in {action.tool_name}; applying recovery strategy."

                    # Execute alternative recovery tool immediately
                    rec_result = self.tool_registry.execute(alt_call)
                    if rec_result.success:
                        # Adaptation successful
                        if alt_call.tool_name == "query_vendor_portal":
                            recs = rec_result.data.get("records", [])
                            if recs:
                                prec = recs[0]
                                cur_data = memory.get("invoice_data", {}) or {}
                                cur_data["due_date"] = prec.get("due_date")
                                cur_data["amount"] = prec.get("total_amount")
                                cur_data["vendor_name"] = prec.get("vendor_name")
                                cur_data["invoice_number"] = prec.get("invoice_number")
                                memory.set("invoice_data", cur_data)
                        elif alt_call.tool_name == "query_accounts_payable":
                            memory.set("payable_created", True)
                            memory.set("existing_erp_record", True)
                        obs.summary += f" [RECOVERY SUCCESS: {rec_result.output}]"
                        obs.evidence += f" [Recovered via {alt_call.tool_name}]"
                else:
                    status = TaskStatus.FAILED
                    completion_msg = f"Task unrecoverable after failure in {action.tool_name}: {tool_result.error}"

            trace = StepTrace(
                step_number=step_idx,
                action=action,
                observation=obs,
                decision=decision,
            )
            traces.append(trace)
            memory.add_trace(trace.model_dump())

            # Progress plan step
            self.planner.mark_step_complete(plan, step_idx, notes=decision.next_step)
            step_idx += 1

        if step_idx > self.max_steps and status == TaskStatus.EXECUTING:
            status = TaskStatus.PARTIALLY_COMPLETED
            completion_msg = f"Execution exceeded maximum step limit ({self.max_steps}). Safety guardrail halted loop."

        duration_sec = round(time.perf_counter() - start_time, 2)

        return AgentExecutionSummary(
            task_id=task_id,
            original_goal=goal,
            status=status,
            plan=plan,
            total_steps=len(traces),
            traces=traces,
            discovered_entities=memory.discovered_entities,
            verification_report=verification_report,
            pending_approval=pending_approval,
            evidence=memory.evidence_log,
            completion_message=completion_msg,
            execution_time_seconds=duration_sec,
        )

    def resume(
        self,
        summary: AgentExecutionSummary,
        decision: ApprovalDecision,
    ) -> AgentExecutionSummary:
        """Resumes an execution that was paused awaiting human approval."""
        if summary.status != TaskStatus.AWAITING_APPROVAL or not summary.pending_approval:
            raise ValueError("Task is not in AWAITING_APPROVAL state.")

        if decision.status == ApprovalStatus.REJECTED:
            summary.status = TaskStatus.FAILED
            summary.completion_message = f"Action '{summary.pending_approval.action_name}' rejected by {decision.approved_by}: {decision.comment or 'No comment'}"
            summary.pending_approval = None
            return summary

        # Human approved: re-run task with approved_by injected into arguments
        approved_args = dict(summary.pending_approval.parameters)
        approved_args["approved_by"] = decision.approved_by

        # Execute the approved tool call
        approved_call = ToolCall(
            tool_name=summary.pending_approval.action_name,
            arguments=approved_args,
        )
        tool_result = self.tool_registry.execute(approved_call)

        step_num = summary.total_steps + 1
        action = StepAction(
            tool_name=summary.pending_approval.action_name,
            arguments=approved_args,
            rationale="Resumed execution following explicit human managerial approval.",
            thought="Managerial approval granted. Committing transaction to internal ERP."
        )
        obs = StepObservation(
            success=tool_result.success,
            summary=tool_result.output,
            data=tool_result.data,
            evidence=tool_result.evidence,
            error=tool_result.error,
            execution_time_ms=tool_result.execution_time_ms,
        )
        dec = StepDecision(
            next_step="Proceed to independent database verification.",
            reason="Payable record committed upon approval."
        )

        trace = StepTrace(
            step_number=step_num,
            action=action,
            observation=obs,
            decision=dec,
        )
        summary.traces.append(trace)
        summary.total_steps = len(summary.traces)
        summary.pending_approval = None

        # Verify outcome
        inv_num = approved_args.get("invoice_number")
        verification_report = self.verifier.verify_invoice_processing(
            invoice_number=inv_num,
            expected_vendor=approved_args.get("vendor_name"),
            expected_amount=approved_args.get("amount"),
            expected_due_date=approved_args.get("due_date"),
        )
        summary.verification_report = verification_report

        if verification_report.verified:
            summary.status = TaskStatus.COMPLETED_VERIFIED
            summary.completion_message = f"Task completed and independently verified post-approval: {verification_report.summary}"
        else:
            summary.status = TaskStatus.COMPLETED_UNVERIFIED
            summary.completion_message = f"Record entered upon approval, but verification reported checks: {verification_report.summary}"

        return summary
