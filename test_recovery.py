"""Tests for Failure Detection, Error Adaptation, and Autonomous Recovery."""

import pytest
from app.environment.seed_data import seed_sandbox
from app.agent.runtime import AutonomousWorker
from app.models.task import TaskStatus


@pytest.fixture(autouse=True)
def setup_environment():
    seed_sandbox()


def test_recovery_from_corrupted_due_date():
    """When a local invoice document has a corrupted due date, the worker

    must detect the anomaly and autonomously recover the official date
    by querying the external vendor clearinghouse portal.
    """
    worker = AutonomousWorker()
    summary = worker.run(
        "Process the invoice for Initech, extract the details, enter it into our internal system, and confirm it was saved."
    )

    # 1. Autonomous recovery succeeded
    assert summary.status == TaskStatus.COMPLETED_VERIFIED

    # 2. Trace confirms extraction failure was detected
    failed_steps = [t for t in summary.traces if not t.observation.success or "RECOVERY" in t.observation.summary]
    assert len(failed_steps) >= 1

    # 3. Destination database contains the accurate recovered due date '2024-12-01'
    rec_check = [c for c in summary.verification_report.checks if c.check_name == "DUE_DATE_ACCURACY"][0]
    assert rec_check.actual_value == "2024-12-01"
    assert rec_check.status.value == "PASSED"


def test_recovery_from_duplicate_entry():
    """Worker recovers gracefully when record already exists in ERP."""
    worker = AutonomousWorker()

    # Run once to enter record
    worker.run("Find the latest invoice from Acme Corp, extract amount and due date, enter it into our internal system, and confirm it was saved.")

    # Run again: worker should detect existing record and handle cleanly
    summary2 = worker.run("Find the latest invoice from Acme Corp, extract amount and due date, enter it into our internal system, and confirm it was saved.")
    assert summary2.verification_report is not None
    assert summary2.verification_report.verified
