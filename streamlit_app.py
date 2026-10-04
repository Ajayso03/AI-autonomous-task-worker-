"""CentrAlign AI — Autonomous AI Task Worker Executive Web Dashboard."""

import sys
from pathlib import Path

# Ensure project root directory is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import json
from datetime import datetime

from app.config import settings
from app.environment.seed_data import seed_sandbox
from app.environment.company_sandbox import CompanySandbox
from app.agent.runtime import AutonomousWorker
from app.models.task import TaskStatus
from app.models.approval import ApprovalDecision, ApprovalStatus
from app.models.verification import CheckStatus

st.set_page_config(
    page_title="CentrAlign AI — Autonomous Task Worker",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom styling for high-clarity executive UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #E2E8F0;
    }
    .trace-card {
        border-left: 4px solid #3B82F6;
        padding-left: 12px;
        margin-bottom: 14px;
    }
    .trace-card-fail {
        border-left: 4px solid #EF4444;
        padding-left: 12px;
        margin-bottom: 14px;
    }
</style>
""", unsafe_allow_html=True)


# Initialize Session State
if "sandbox" not in st.session_state:
    st.session_state.sandbox = CompanySandbox()
if "current_summary" not in st.session_state:
    st.session_state.current_summary = None
if "pending_task" not in st.session_state:
    st.session_state.pending_task = None
if "selected_preset" not in st.session_state:
    st.session_state.selected_preset = ""


# Sidebar Controls
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=64)
    st.title("Worker Control Panel")
    st.caption("CentrAlign Autonomous Operator")

    st.markdown("### Runtime Configuration")
    st.info(f"**Engine:** `{settings.llm_provider.upper()}`\n\n"
            f"**Max Steps:** `{settings.agent_max_steps}`\n\n"
            f"**Approval Ceiling:** `${settings.high_value_approval_threshold:,.2f}`\n\n"
            f"**Strict Verification:** `{settings.strict_independent_verification}`")

    st.markdown("---")
    st.markdown("### Task Presets")
    st.caption("Click any preset to populate the task runner:")

    if st.button("📋 1. Acme Corp (Happy Path)", use_container_width=True):
        st.session_state.task_input = "Find the latest invoice from Acme Corp, extract the amount and due date, enter it into our internal system, and confirm it was saved."

    if st.button("🔄 2. Initech (Damage Recovery)", use_container_width=True):
        st.session_state.task_input = "Process the invoice for Initech, extract the details, enter it into our internal system, and confirm it was saved."

    if st.button("🛡️ 3. Stark Industries (Policy Approval)", use_container_width=True):
        st.session_state.task_input = "Find invoice for Stark Industries, extract amount and due date, enter it into our internal system, and confirm it was saved."

    if st.button("⚖️ 4. Cyberdyne (Ledger Reconciliation)", use_container_width=True):
        st.session_state.task_input = "Process payment reconciliation for Cyberdyne Systems contract, record disbursement into the financial ledger, and verify the updated balance."

    st.markdown("---")
    if st.button("🧹 Reset & Re-Seed Sandbox", use_container_width=True):
        seed_sandbox()
        st.session_state.current_summary = None
        st.session_state.pending_task = None
        st.success("Sandbox database and document repository reset to initial state!")


# Header
st.markdown('<div class="main-header">CentrAlign AI — Autonomous Task Worker</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Autonomous Business Task Completion | Goal → Understand → Plan → Execute → Observe → Adapt → Verify</div>', unsafe_allow_html=True)

# Main Task Input Box
task_input = st.text_area(
    "Natural Language Company Task",
    value=st.session_state.get("task_input", "Find the latest invoice from Acme Corp, extract the amount and due date, enter it into our internal system, and confirm it was saved."),
    height=80,
    help="Enter an end-to-end task objective. The autonomous worker will infer all steps, execute tools, recover from anomalies, and independently verify outcomes."
)

col1, col2 = st.columns([1, 4])
with col1:
    deploy_clicked = st.button("🚀 Deploy Worker", type="primary", use_container_width=True)

if deploy_clicked and task_input:
    with st.spinner("Autonomous worker reasoning, executing tools, and verifying state..."):
        worker = AutonomousWorker()
        summary = worker.run(goal=task_input, pause_for_approval=True)
        st.session_state.current_summary = summary
        st.session_state.pending_task = summary if summary.status == TaskStatus.AWAITING_APPROVAL else None


# Execution Summary & Human-in-the-Loop Banner
summary = st.session_state.current_summary
if summary:
    # Status Banner
    status_colors = {
        TaskStatus.COMPLETED_VERIFIED: ("#DCFCE7", "#166534", "✅ COMPLETED & INDEPENDENTLY VERIFIED"),
        TaskStatus.COMPLETED_UNVERIFIED: ("#FEF9C3", "#854D0E", "⚠️ COMPLETED (VERIFICATION DISCREPANCY)"),
        TaskStatus.AWAITING_APPROVAL: ("#FEE2E2", "#991B1B", "🛡️ AWAITING HUMAN MANAGERIAL APPROVAL"),
        TaskStatus.FAILED: ("#FEE2E2", "#991B1B", "❌ TASK FAILED"),
        TaskStatus.EXECUTING: ("#DBEAFE", "#1E40AF", "⚙️ EXECUTING"),
    }
    bg, fg, label = status_colors.get(summary.status, ("#F1F5F9", "#334155", str(summary.status)))

    st.markdown(
        f'<div style="background-color: {bg}; color: {fg}; padding: 12px 18px; border-radius: 8px; font-weight: bold; margin-bottom: 20px;">'
        f'{label} — Task ID: <code>{summary.task_id}</code> | Time: {summary.execution_time_seconds}s | Steps: {summary.total_steps}'
        f'</div>',
        unsafe_allow_html=True
    )

    # HUMAN-IN-THE-LOOP INTERACTION CARD
    if summary.status == TaskStatus.AWAITING_APPROVAL and summary.pending_approval:
        req = summary.pending_approval
        st.warning("### ⚠️ Human Managerial Approval Required")
        st.markdown(f"**Policy Trigger:** {req.reason}")
        st.markdown(f"**Context:** {req.context_summary}")

        c_app1, c_app2, c_app3 = st.columns([2, 1, 1])
        with c_app1:
            comment_input = st.text_input("Managerial Note / Authorization Reference", value="Approved for corporate processing")
        with c_app2:
            if st.button("✅ Authorize Action", type="primary", use_container_width=True):
                worker = AutonomousWorker()
                decision = ApprovalDecision(
                    request_id=req.request_id,
                    status=ApprovalStatus.APPROVED,
                    approved_by="Corporate_Manager",
                    comment=comment_input
                )
                resumed = worker.resume(summary, decision)
                st.session_state.current_summary = resumed
                st.session_state.pending_task = None
                st.rerun()
        with c_app3:
            if st.button("⛔ Reject Action", use_container_width=True):
                worker = AutonomousWorker()
                decision = ApprovalDecision(
                    request_id=req.request_id,
                    status=ApprovalStatus.REJECTED,
                    approved_by="Corporate_Manager",
                    comment=comment_input
                )
                resumed = worker.resume(summary, decision)
                st.session_state.current_summary = resumed
                st.session_state.pending_task = None
                st.rerun()


    # TABS FOR RICH INSPECTION
    tab_trace, tab_verify, tab_erp, tab_files = st.tabs([
        "🔬 Execution Trace",
        "🎯 Independent Verification",
        "🏢 Company ERP Database",
        "📁 Sandbox Documents"
    ])

    with tab_trace:
        if summary.plan:
            st.markdown("#### Autonomous Plan Deconstruction")
            st.caption(f"Objective: {summary.plan.interpreted_objective}")
            plan_df = pd.DataFrame([
                {"Step": s.index, "Planned Action": s.description, "Status": "Completed" if s.completed else "Pending"}
                for s in summary.plan.steps
            ])
            st.dataframe(plan_df, use_container_width=True, hide_index=True)

        st.markdown("#### ReAct Step-by-Step Trajectory")
        for t in summary.traces:
            border_cls = "trace-card" if t.observation.success else "trace-card-fail"
            with st.expander(f"Step {t.step_number}: {t.action.tool_name} — {t.decision.next_step[:70]}...", expanded=True):
                st.markdown(f"**Thought:** *{t.action.thought}*")
                st.markdown(f"**Action:** `{t.action.tool_name}({json.dumps(t.action.arguments)})`")
                if t.observation.success:
                    st.success(f"**Observation:** {t.observation.summary}")
                else:
                    st.error(f"**Observation (Failure):** {t.observation.summary}")
                st.markdown(f"**Decision:** {t.decision.next_step} (*{t.decision.reason}*)")
                st.caption(f"Tool latency: {t.observation.execution_time_ms} ms | Evidence: {t.observation.evidence}")

    with tab_verify:
        st.markdown("### Independent Outcome Verification Engine")
        st.caption("Verification directly queries the destination database independently of the action loop.")

        if summary.verification_report:
            rep = summary.verification_report
            if rep.verified:
                st.success(rep.summary)
            else:
                st.error(rep.summary)

            checks_data = []
            for c in rep.checks:
                status_icon = "✅ PASS" if c.status == CheckStatus.PASSED else ("⚠️ WARN" if c.status == CheckStatus.WARNING else "❌ FAIL")
                checks_data.append({
                    "Status": status_icon,
                    "Check Name": c.check_name,
                    "Target Table": c.target_entity,
                    "Expected Value": str(c.expected_value),
                    "Actual Persisted DB Value": str(c.actual_value),
                    "Evidence Source": c.evidence_source,
                })
            st.dataframe(pd.DataFrame(checks_data), use_container_width=True, hide_index=True)

            if rep.independent_query_data:
                st.markdown("#### Raw Verified Database Record")
                st.json(rep.independent_query_data)
        else:
            st.info("No verification report generated yet.")

    with tab_erp:
        st.markdown("### Internal Enterprise Database (Live State)")
        sb = CompanySandbox()

        st.markdown("#### Accounts Payable Subledger (`invoices_payable`)")
        inv_rows = sb.fetch_all_invoices()
        if inv_rows:
            st.dataframe(pd.DataFrame(inv_rows), use_container_width=True, hide_index=True)
        else:
            st.write("No records in `invoices_payable`.")

        st.markdown("#### General Ledger (`financial_ledger`)")
        ledger_rows = sb.fetch_ledger_entries()
        if ledger_rows:
            st.dataframe(pd.DataFrame(ledger_rows), use_container_width=True, hide_index=True)
        else:
            st.write("No records in `financial_ledger`.")

        st.markdown("#### Compliance Audit Trail (`audit_log`)")
        audit_rows = sb.fetch_audit_logs(limit=15)
        if audit_rows:
            st.dataframe(pd.DataFrame(audit_rows), use_container_width=True, hide_index=True)

    with tab_files:
        st.markdown("### Sandbox Document Repository Files")
        base_dir = settings.sandbox_dir
        for root, _, files in __import__("os").walk(base_dir):
            for f in sorted(files):
                fpath = __import__("pathlib").Path(root) / f
                rel = fpath.relative_to(base_dir).as_posix()
                with st.expander(f"📄 {rel} ({fpath.stat().st_size} bytes)"):
                    try:
                        if fpath.suffix.lower() == ".pdf":
                            st.write("Binary PDF document file.")
                        else:
                            st.code(fpath.read_text(encoding="utf-8"))
                    except Exception as e:
                        st.write(f"Cannot preview file: {e}")
