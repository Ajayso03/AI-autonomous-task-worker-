"""Tests for Safety Guardrails, Human-in-the-Loop, and Approval Policies."""

import pytest
from app.environment.seed_data import seed_sandbox
from app.environment.company_sandbox import CompanySandbox
from app.agent.runtime import AutonomousWorker
from app.models.task import TaskStatus
from app.models.approval import ApprovalDecision, ApprovalStatus, RiskLevel


@pytest.fixture(autouse=True)
def setup_environment():
    seed_sandbox()


def test_high_value_transaction_triggers_approval():
    """Stark Industries invoice ($14,200) exceeds $5,000 threshold and must pause for approval."""
    worker = AutonomousWorker()
    summary = worker.run(
        "Find invoice for Stark Industries, extract amount and due date, enter it into our internal system, and confirm it was saved.",
        pause_for_approval=True
    )

    assert summary.status == TaskStatus.AWAITING_APPROVAL
    assert summary.pending_approval is not None
    assert summary.pending_approval.risk_level == RiskLevel.HIGH
    assert summary.pending_approval.actual_value == 14200.0
    assert summary.pending_approval.threshold_value == 5000.0

    # Ensure no record was prematurely committed to database
    sb = CompanySandbox()
    assert sb.fetch_invoice("INV-2024-205") is None


def test_approval_resumption_workflow():
    """Approving a paused high-value task successfully resumes and completes verification."""
    worker = AutonomousWorker()
    summary = worker.run(
        "Find invoice for Stark Industries, extract amount and due date, enter it into our internal system, and confirm it was saved.",
        pause_for_approval=True
    )
    assert summary.status == TaskStatus.AWAITING_APPROVAL

    decision = ApprovalDecision(
        request_id=summary.pending_approval.request_id,
        status=ApprovalStatus.APPROVED,
        approved_by="CFO_Carol",
        comment="Authorized enterprise energy infrastructure maintenance"
    )

    resumed = worker.resume(summary, decision)
    assert resumed.status == TaskStatus.COMPLETED_VERIFIED
    assert resumed.verification_report.verified

    # Verify committed database row reflects approval
    sb = CompanySandbox()
    rec = sb.fetch_invoice("INV-2024-205")
    assert rec is not None
    assert rec["approved_by"] == "CFO_Carol"
    assert rec["amount"] == 14200.0


def test_rejection_halts_execution_without_database_write():
    """Rejecting a pending approval request marks task FAILED and leaves database clean."""
    worker = AutonomousWorker()
    summary = worker.run(
        "Find invoice for Stark Industries, extract amount and due date, enter it into our internal system, and confirm it was saved.",
        pause_for_approval=True
    )
    assert summary.status == TaskStatus.AWAITING_APPROVAL

    decision = ApprovalDecision(
        request_id=summary.pending_approval.request_id,
        status=ApprovalStatus.REJECTED,
        approved_by="Compliance_Officer_Bob",
        comment="Budget freeze in effect"
    )

    resumed = worker.resume(summary, decision)
    assert resumed.status == TaskStatus.FAILED
    assert "rejected" in resumed.completion_message.lower()

    # Ensure no record entered into database
    sb = CompanySandbox()
    assert sb.fetch_invoice("INV-2024-205") is None
