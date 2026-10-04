"""ERP and Internal Company System tools."""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.config import settings
from app.environment.company_sandbox import CompanySandbox
from app.models.tools import ToolResult
from app.tools.registry import default_registry


@default_registry.register(
    name="query_accounts_payable",
    description="Query internal ERP Accounts Payable database for existing invoice records by vendor or invoice number.",
    category="database"
)
def query_accounts_payable(vendor_name: Optional[str] = None, invoice_number: Optional[str] = None) -> ToolResult:
    """Queries invoices_payable table."""
    sb = CompanySandbox()
    with sb.get_connection() as conn:
        cursor = conn.cursor()
        if invoice_number:
            cursor.execute("SELECT * FROM invoices_payable WHERE invoice_number = ?", (invoice_number,))
        elif vendor_name:
            cursor.execute("SELECT * FROM invoices_payable WHERE LOWER(vendor_name) LIKE LOWER(?)", (f"%{vendor_name}%",))
        else:
            cursor.execute("SELECT * FROM invoices_payable ORDER BY id DESC LIMIT 20")

        rows = [dict(r) for r in cursor.fetchall()]

    if not rows:
        return ToolResult(
            success=True,
            tool_name="query_accounts_payable",
            output="No records found matching criteria in Accounts Payable.",
            data={"count": 0, "records": []},
            evidence="Queried invoices_payable table; 0 rows returned.",
        )

    return ToolResult(
        success=True,
        tool_name="query_accounts_payable",
        output=f"Found {len(rows)} records in Accounts Payable: " + json.dumps(rows, default=str),
        data={"count": len(rows), "records": rows},
        evidence=f"Retrieved {len(rows)} records from internal ERP.",
    )


@default_registry.register(
    name="create_payable_record",
    description="Enter a verified vendor invoice into internal Accounts Payable ERP database.",
    category="database",
    is_reversible=True,
    requires_approval=False,  # Evaluated dynamically based on amount policy
)
def create_payable_record(
    invoice_number: str,
    vendor_name: str,
    amount: float,
    due_date: str,
    notes: Optional[str] = None,
    approved_by: Optional[str] = None,
) -> ToolResult:
    """Inserts a new invoice payable into ERP database with validation and auditing."""
    sb = CompanySandbox()

    # Guardrail: Check high-value threshold
    if amount > settings.high_value_approval_threshold and not approved_by:
        return ToolResult(
            success=False,
            tool_name="create_payable_record",
            output=f"POLICY GUARD: Invoice amount ${amount:,.2f} exceeds standard employee threshold (${settings.high_value_approval_threshold:,.2f}). Human managerial approval required.",
            error="PolicyApprovalRequiredError",
            evidence=f"High-value transaction flagged: ${amount:,.2f} > ${settings.high_value_approval_threshold:,.2f}",
            data={
                "requires_approval": True,
                "amount": amount,
                "threshold": settings.high_value_approval_threshold,
                "invoice_number": invoice_number,
                "vendor_name": vendor_name,
                "due_date": due_date,
            }
        )

    with sb.get_connection() as conn:
        cursor = conn.cursor()
        # Check if already exists
        cursor.execute("SELECT id FROM invoices_payable WHERE invoice_number = ?", (invoice_number,))
        existing = cursor.fetchone()
        if existing:
            return ToolResult(
                success=False,
                tool_name="create_payable_record",
                output=f"Duplicate invoice entry rejected: Invoice {invoice_number} already exists in ERP.",
                error="DuplicateRecordError",
                evidence=f"Integrity check failed: invoice_number '{invoice_number}' collision.",
            )

        now_str = datetime.now().isoformat()
        status_val = "APPROVED" if approved_by else "ENTERED_PENDING_DISBURSEMENT"

        cursor.execute("""
            INSERT INTO invoices_payable (invoice_number, vendor_name, amount, due_date, status, entered_at, approved_by, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice_number,
            vendor_name,
            amount,
            due_date,
            status_val,
            now_str,
            approved_by or "autonomous_worker",
            notes or f"Auto-entered by worker from invoice {invoice_number}"
        ))
        record_id = cursor.lastrowid
        conn.commit()

    sb.record_audit(
        actor="autonomous_worker",
        action="CREATE_PAYABLE_RECORD",
        target_entity=f"invoices_payable:{invoice_number}",
        details={"record_id": record_id, "amount": amount, "vendor": vendor_name, "due_date": due_date},
        status="SUCCESS"
    )

    return ToolResult(
        success=True,
        tool_name="create_payable_record",
        output=f"Successfully created Accounts Payable record ID {record_id} for invoice {invoice_number} (${amount:,.2f}, due {due_date}).",
        data={
            "record_id": record_id,
            "invoice_number": invoice_number,
            "vendor_name": vendor_name,
            "amount": amount,
            "due_date": due_date,
            "status": status_val,
        },
        evidence=f"Inserted row into invoices_payable with ID {record_id} and timestamp {now_str}.",
    )


@default_registry.register(
    name="record_ledger_disbursement",
    description="Post a balanced journal entry into internal General Ledger for payment reconciliation.",
    category="database"
)
def record_ledger_disbursement(
    transaction_id: str,
    account_code: str,
    debit: float,
    credit: float,
    reference_invoice: str,
    memo: str,
) -> ToolResult:
    """Records entry into financial_ledger."""
    sb = CompanySandbox()
    with sb.get_connection() as conn:
        cursor = conn.cursor()
        now_str = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO financial_ledger (transaction_id, account_code, debit, credit, reference_invoice, timestamp, memo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            transaction_id,
            account_code,
            debit,
            credit,
            reference_invoice,
            now_str,
            memo
        ))
        conn.commit()

    sb.record_audit(
        actor="autonomous_worker",
        action="POST_LEDGER_ENTRY",
        target_entity=f"financial_ledger:{transaction_id}",
        details={"debit": debit, "credit": credit, "invoice": reference_invoice},
        status="SUCCESS"
    )

    return ToolResult(
        success=True,
        tool_name="record_ledger_disbursement",
        output=f"Successfully posted ledger transaction {transaction_id} for invoice {reference_invoice}.",
        data={"transaction_id": transaction_id, "account_code": account_code, "debit": debit, "credit": credit},
        evidence=f"General ledger updated for transaction {transaction_id}.",
    )


@default_registry.register(
    name="inspect_database_record",
    description="Directly inspect a database row by table and key for independent verification.",
    category="database"
)
def inspect_database_record(table_name: str, key_field: str, key_value: str) -> ToolResult:
    """Reads raw database state directly for independent verification checks."""
    allowed_tables = {"invoices_payable", "financial_ledger", "vendors", "audit_log", "vendor_portal_records"}
    if table_name not in allowed_tables:
        return ToolResult(
            success=False,
            tool_name="inspect_database_record",
            output=f"Access denied: table '{table_name}' is not in allowed audit tables.",
            error="SecurityViolationError",
        )

    sb = CompanySandbox()
    with sb.get_connection() as conn:
        cursor = conn.cursor()
        # Safe parameterized query
        query = f"SELECT * FROM {table_name} WHERE {key_field} = ?"
        try:
            cursor.execute(query, (key_value,))
            rows = [dict(r) for r in cursor.fetchall()]
        except Exception as exc:
            return ToolResult(
                success=False,
                tool_name="inspect_database_record",
                output=f"Query error: {str(exc)}",
                error=f"DatabaseError: {str(exc)}",
            )

    if not rows:
        return ToolResult(
            success=False,
            tool_name="inspect_database_record",
            output=f"No record found in {table_name} where {key_field} = '{key_value}'.",
            data={"count": 0, "rows": []},
            error="RecordNotFound",
        )

    return ToolResult(
        success=True,
        tool_name="inspect_database_record",
        output=f"Direct DB inspection returned: {json.dumps(rows[0], default=str)}",
        data={"count": len(rows), "record": rows[0]},
        evidence=f"Direct database read confirmed state for {table_name}.{key_field}={key_value}",
    )
