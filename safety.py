"""Safety guardrails and Human-in-the-Loop policy engine."""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from app.config import settings
from app.models.approval import ApprovalRequest, RiskLevel, ApprovalStatus
from app.agent.memory import AgentMemory


class SafetyPolicyEngine:
    """Evaluates proposed actions against organizational risk policies

    and triggers Human-in-the-Loop approval when thresholds or irreversible boundaries are crossed.
    """

    def __init__(self, high_value_threshold: Optional[float] = None):
        self.high_value_threshold = high_value_threshold or settings.high_value_approval_threshold

    def evaluate_proposed_action(
        self,
        task_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        memory: AgentMemory,
    ) -> Optional[ApprovalRequest]:
        """Inspects tool call parameters and returns an ApprovalRequest if human sign-off is required."""
        # 1. Accounts Payable high-value policy
        if tool_name == "create_payable_record":
            amount = float(arguments.get("amount", 0.0))
            approved_by = arguments.get("approved_by")

            if amount > self.high_value_threshold and not approved_by:
                return ApprovalRequest(
                    request_id=f"APPR-{uuid.uuid4().hex[:8].upper()}",
                    task_id=task_id,
                    risk_level=RiskLevel.HIGH,
                    action_name=tool_name,
                    parameters=arguments,
                    threshold_value=self.high_value_threshold,
                    actual_value=amount,
                    reason=f"Financial control policy: payable entry (${amount:,.2f}) exceeds autonomous limit (${self.high_value_threshold:,.2f}).",
                    context_summary=f"Invoice {arguments.get('invoice_number')} from {arguments.get('vendor_name')} for ${amount:,.2f} due {arguments.get('due_date')}",
                    status=ApprovalStatus.PENDING,
                )

        # 2. Critical disbursement threshold
        if tool_name == "record_ledger_disbursement":
            debit = float(arguments.get("debit", 0.0))
            if debit > 25000.0 and not arguments.get("approved_by"):
                return ApprovalRequest(
                    request_id=f"APPR-{uuid.uuid4().hex[:8].upper()}",
                    task_id=task_id,
                    risk_level=RiskLevel.CRITICAL,
                    action_name=tool_name,
                    parameters=arguments,
                    threshold_value=25000.0,
                    actual_value=debit,
                    reason=f"Treasury risk policy: general ledger posting (${debit:,.2f}) exceeds auto-journal ceiling ($25,000.00).",
                    context_summary=f"General ledger debit ${debit:,.2f} against invoice {arguments.get('reference_invoice')}",
                    status=ApprovalStatus.PENDING,
                )

        return None
