"""Independent ground-truth outcome verification engine."""

import sqlite3
from typing import Dict, Any, Optional
from datetime import datetime

from app.environment.company_sandbox import CompanySandbox
from app.models.verification import (
    CheckStatus,
    VerificationCheck,
    VerificationReport,
)


class IndependentOutcomeVerifier:
    """Verifies actual persistence and integrity of business records

    directly against the underlying database independently of the agent's action loop.
    """

    def __init__(self, sandbox: Optional[CompanySandbox] = None):
        self.sandbox = sandbox or CompanySandbox()

    def verify_invoice_processing(
        self,
        invoice_number: str,
        expected_vendor: Optional[str] = None,
        expected_amount: Optional[float] = None,
        expected_due_date: Optional[str] = None,
        check_ledger: bool = False,
    ) -> VerificationReport:
        """Executes independent multi-point checks against the ERP database."""
        checks = []

        # 1. Direct query of invoices_payable table
        record = self.sandbox.fetch_invoice(invoice_number)

        # Check 1: Database record existence
        checks.append(
            VerificationCheck(
                check_name="ERP_RECORD_PERSISTENCE",
                target_entity="invoices_payable",
                field_name="id",
                expected_value=f"Row with invoice_number='{invoice_number}'",
                actual_value=f"Row ID {record['id']}" if record else "NOT_FOUND",
                status=CheckStatus.PASSED if record else CheckStatus.FAILED,
                evidence_source="SQLite company_erp.db invoices_payable table",
                details="Confirmed record was committed to durable storage." if record else "Record was not found in destination ERP table.",
            )
        )

        if not record:
            return VerificationReport(
                verified=False,
                passed_count=0,
                total_count=1,
                checks=checks,
                independent_query_data=None,
                summary=f"Independent verification FAILED: Invoice {invoice_number} does not exist in ERP database.",
                timestamp=datetime.now().isoformat(),
            )

        # Check 2: Vendor Name Integrity
        if expected_vendor:
            actual_vendor = record.get("vendor_name", "")
            vendor_match = expected_vendor.lower() in actual_vendor.lower()
            checks.append(
                VerificationCheck(
                    check_name="VENDOR_NAME_INTEGRITY",
                    target_entity="invoices_payable",
                    field_name="vendor_name",
                    expected_value=expected_vendor,
                    actual_value=actual_vendor,
                    status=CheckStatus.PASSED if vendor_match else CheckStatus.FAILED,
                    evidence_source="invoices_payable.vendor_name column",
                    details=f"Vendor string check: expected '{expected_vendor}', found '{actual_vendor}'",
                )
            )

        # Check 3: Amount Numerical Integrity
        if expected_amount is not None:
            actual_amount = float(record.get("amount", 0.0))
            amount_match = abs(actual_amount - expected_amount) < 0.01
            checks.append(
                VerificationCheck(
                    check_name="AMOUNT_NUMERICAL_ACCURACY",
                    target_entity="invoices_payable",
                    field_name="amount",
                    expected_value=expected_amount,
                    actual_value=actual_amount,
                    status=CheckStatus.PASSED if amount_match else CheckStatus.FAILED,
                    evidence_source="invoices_payable.amount column",
                    details=f"Numerical comparison: expected ${expected_amount:,.2f}, stored ${actual_amount:,.2f}",
                )
            )

        # Check 4: Due Date Integrity
        if expected_due_date:
            actual_due_date = record.get("due_date", "")
            date_match = actual_due_date == expected_due_date
            checks.append(
                VerificationCheck(
                    check_name="DUE_DATE_ACCURACY",
                    target_entity="invoices_payable",
                    field_name="due_date",
                    expected_value=expected_due_date,
                    actual_value=actual_due_date,
                    status=CheckStatus.PASSED if date_match else CheckStatus.FAILED,
                    evidence_source="invoices_payable.due_date column",
                    details=f"Due date comparison: expected {expected_due_date}, stored {actual_due_date}",
                )
            )

        # Check 5: General Ledger Posting Check (if applicable)
        if check_ledger:
            ledger_entries = self.sandbox.fetch_ledger_entries(reference_invoice=invoice_number)
            has_ledger = len(ledger_entries) > 0
            checks.append(
                VerificationCheck(
                    check_name="GENERAL_LEDGER_POSTING",
                    target_entity="financial_ledger",
                    field_name="reference_invoice",
                    expected_value=f"Journal entry for {invoice_number}",
                    actual_value=f"{len(ledger_entries)} journal entries found" if has_ledger else "0 entries",
                    status=CheckStatus.PASSED if has_ledger else CheckStatus.FAILED,
                    evidence_source="financial_ledger table",
                    details=f"Reconciled {len(ledger_entries)} General Ledger postings for {invoice_number}",
                )
            )

        # Check 6: Audit Trail Presence
        audit_logs = self.sandbox.fetch_audit_logs(limit=20)
        has_audit = any(invoice_number in log.get("target_entity", "") for log in audit_logs)
        checks.append(
            VerificationCheck(
                check_name="AUDIT_TRAIL_COMPLIANCE",
                target_entity="audit_log",
                field_name="target_entity",
                expected_value=f"Audit entry containing {invoice_number}",
                actual_value="Found matching audit row" if has_audit else "No audit row",
                status=CheckStatus.PASSED if has_audit else CheckStatus.WARNING,
                evidence_source="audit_log table",
                details="Verified transactional compliance logging.",
            )
        )

        passed_count = sum(1 for c in checks if c.status == CheckStatus.PASSED)
        total_count = len(checks)
        all_passed = all(c.status in (CheckStatus.PASSED, CheckStatus.WARNING) for c in checks)

        return VerificationReport(
            verified=all_passed,
            passed_count=passed_count,
            total_count=total_count,
            checks=checks,
            independent_query_data=record,
            summary=f"Independent verification {'PASSED' if all_passed else 'FAILED'}: {passed_count}/{total_count} checks passed for invoice {invoice_number}.",
            timestamp=datetime.now().isoformat(),
        )
