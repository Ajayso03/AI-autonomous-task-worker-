"""Tests for Independent Ground-Truth Verification Engine."""

import pytest
from app.environment.seed_data import seed_sandbox
from app.environment.company_sandbox import CompanySandbox
from app.agent.verifier import IndependentOutcomeVerifier
from app.models.verification import CheckStatus


@pytest.fixture(autouse=True)
def setup_environment():
    seed_sandbox()


def test_independent_verification_success():
    """Verify that accurate database entries pass all invariant checks."""
    sb = CompanySandbox()
    # Insert known verified invoice
    with sb.get_connection() as conn:
        conn.execute("""
            INSERT INTO invoices_payable (invoice_number, vendor_name, amount, due_date, status, entered_at)
            VALUES ('INV-VERIFY-001', 'Test Corp', 1500.00, '2025-05-01', 'ENTERED_PENDING_DISBURSEMENT', '2025-01-01')
        """)
        conn.commit()

    verifier = IndependentOutcomeVerifier(sandbox=sb)
    report = verifier.verify_invoice_processing(
        invoice_number="INV-VERIFY-001",
        expected_vendor="Test Corp",
        expected_amount=1500.00,
        expected_due_date="2025-05-01"
    )

    assert report.verified
    assert report.passed_count >= 4
    for c in report.checks:
        assert c.status in (CheckStatus.PASSED, CheckStatus.WARNING)


def test_independent_verification_fails_on_missing_record():
    """Verification immediately fails if target record is missing from database."""
    sb = CompanySandbox()
    verifier = IndependentOutcomeVerifier(sandbox=sb)

    report = verifier.verify_invoice_processing(invoice_number="INV-NON-EXISTENT-999")
    assert not report.verified
    assert report.passed_count == 0
    assert report.checks[0].status == CheckStatus.FAILED


def test_independent_verification_detects_amount_tampering_or_discrepancy():
    """Verifier must catch numerical discrepancies between expected and actual database amounts."""
    sb = CompanySandbox()
    with sb.get_connection() as conn:
        conn.execute("""
            INSERT INTO invoices_payable (invoice_number, vendor_name, amount, due_date, status, entered_at)
            VALUES ('INV-TAMPER-001', 'Tampered Corp', 999.00, '2025-05-01', 'ENTERED', '2025-01-01')
        """)
        conn.commit()

    verifier = IndependentOutcomeVerifier(sandbox=sb)
    # Expected amount is $1,500.00, but database only has $999.00
    report = verifier.verify_invoice_processing(
        invoice_number="INV-TAMPER-001",
        expected_vendor="Tampered Corp",
        expected_amount=1500.00,
        expected_due_date="2025-05-01"
    )

    assert not report.verified
    amount_check = [c for c in report.checks if c.check_name == "AMOUNT_NUMERICAL_ACCURACY"][0]
    assert amount_check.status == CheckStatus.FAILED
    assert amount_check.expected_value == 1500.00
    assert amount_check.actual_value == 999.00
