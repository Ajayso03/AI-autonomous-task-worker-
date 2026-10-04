"""Tests for Architecture Generalization across Varied Business Tasks."""

import pytest
from app.environment.seed_data import seed_sandbox
from app.agent.runtime import AutonomousWorker
from app.models.task import TaskStatus


@pytest.fixture(autouse=True)
def setup_environment():
    seed_sandbox()


def test_task_variation_cyberdyne_general_ledger():
    """Task Variation: Process Cyberdyne Systems contract, record ledger disbursement,

    and verify financial ledger balance.
    """
    worker = AutonomousWorker()
    summary = worker.run(
        "Process payment reconciliation for Cyberdyne Systems contract, record disbursement into the financial ledger, and verify the updated balance."
    )

    assert summary.status == TaskStatus.COMPLETED_VERIFIED
    tool_sequence = [t.action.tool_name for t in summary.traces]
    assert "record_ledger_disbursement" in tool_sequence

    # Verify both accounts payable and general ledger checks passed
    assert summary.verification_report.verified
    gl_check = [c for c in summary.verification_report.checks if c.check_name == "GENERAL_LEDGER_POSTING"][0]
    assert gl_check.status.value == "PASSED"


def test_task_variation_multiple_goals_with_same_worker_instance():
    """Worker instance can execute sequential varied tasks without cross-task state leakage."""
    worker = AutonomousWorker()

    # Task 1: Acme
    s1 = worker.run("Find the latest invoice from Acme Corp, extract amount and due date, enter it into our internal system, and confirm it was saved.")
    assert s1.status == TaskStatus.COMPLETED_VERIFIED

    # Task 2: Cyberdyne
    s2 = worker.run("Process payment reconciliation for Cyberdyne Systems contract, record disbursement into the financial ledger, and verify the updated balance.")
    assert s2.status == TaskStatus.COMPLETED_VERIFIED
    assert s1.task_id != s2.task_id
