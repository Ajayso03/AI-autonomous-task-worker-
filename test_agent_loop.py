"""Tests for Autonomous Worker Execution Loop (Happy Path & State Progression)."""

import pytest
from app.environment.seed_data import seed_sandbox
from app.agent.runtime import AutonomousWorker
from app.models.task import TaskStatus


@pytest.fixture(autouse=True)
def setup_environment():
    seed_sandbox()


def test_happy_path_acme_invoice_processing():
    """Verify end-to-end autonomous completion of the canonical invoice processing task."""
    worker = AutonomousWorker()
    summary = worker.run(
        "Find the latest invoice from Acme Corp, extract the amount and due date, enter it into our internal system, and confirm it was saved."
    )

    # 1. State Verification
    assert summary.status == TaskStatus.COMPLETED_VERIFIED
    assert summary.total_steps >= 4
    assert summary.total_steps <= 8

    # 2. Plan was generated
    assert summary.plan is not None
    assert len(summary.plan.steps) >= 5

    # 3. Traces contain required ReAct steps
    tool_sequence = [t.action.tool_name for t in summary.traces]
    assert "search_company_documents" in tool_sequence
    assert "extract_invoice_data" in tool_sequence
    assert "create_payable_record" in tool_sequence
    assert "inspect_database_record" in tool_sequence

    # 4. Independent Verification passed
    assert summary.verification_report is not None
    assert summary.verification_report.verified
    assert summary.verification_report.passed_count == summary.verification_report.total_count

    # 5. Evidence captured
    assert len(summary.evidence) > 0


def test_autonomy_infers_steps_without_explicit_commands():
    """Worker infers sub-steps (search -> read -> validate -> check ERP -> enter -> verify)

    from a vague high-level user request.
    """
    worker = AutonomousWorker()
    summary = worker.run("Please handle the Acme Corp bill.")

    assert summary.status == TaskStatus.COMPLETED_VERIFIED
    assert summary.verification_report.verified
