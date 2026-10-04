"""Tests for Loop Prevention, Guardrails, and Recursion Boundaries."""

import pytest
from app.environment.seed_data import seed_sandbox
from app.agent.runtime import AutonomousWorker
from app.models.task import TaskStatus


@pytest.fixture(autouse=True)
def setup_environment():
    seed_sandbox()


def test_max_step_guardrail_prevents_infinite_loop():
    """Worker terminates safely with PARTIALLY_COMPLETED if maximum step limit is reached."""
    # Configure tiny step limit of 2
    worker = AutonomousWorker(max_steps=2)
    summary = worker.run(
        "Find the latest invoice from Acme Corp, extract amount and due date, enter it into our internal system, and confirm it was saved."
    )

    # Must halt within 2 steps without looping
    assert summary.total_steps <= 2
    assert summary.status == TaskStatus.PARTIALLY_COMPLETED
    assert "exceeded maximum step limit" in summary.completion_message
