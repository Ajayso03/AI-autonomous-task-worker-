"""Company sandbox environment: SQLite ERP database and file repository."""

import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.config import settings


class CompanySandbox:
    """Manages the simulated internal company infrastructure:

    - Real SQLite ERP database for Accounts Payable, General Ledger, Audit Logs
    - Real file repository with invoices, statements, PDFs, and portal records
    """

    def __init__(self, db_path: Optional[Path] = None, sandbox_dir: Optional[Path] = None):
        self.db_path = db_path or settings.erp_db_path
        self.sandbox_dir = sandbox_dir or settings.sandbox_dir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Vendors table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vendors (
                    vendor_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    tax_id TEXT,
                    contact_email TEXT,
                    payment_terms TEXT,
                    status TEXT DEFAULT 'ACTIVE'
                )
            """)

            # Invoices Payable table (Accounts Payable subledger)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoices_payable (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_number TEXT UNIQUE NOT NULL,
                    vendor_name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    due_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
                    entered_at TEXT NOT NULL,
                    verified_at TEXT,
                    approved_by TEXT,
                    notes TEXT
                )
            """)

            # Financial Ledger table (General Ledger)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS financial_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT UNIQUE NOT NULL,
                    account_code TEXT NOT NULL,
                    debit REAL NOT NULL,
                    credit REAL NOT NULL,
                    reference_invoice TEXT,
                    timestamp TEXT NOT NULL,
                    memo TEXT
                )
            """)

            # Audit Log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_entity TEXT NOT NULL,
                    details TEXT,
                    status TEXT NOT NULL
                )
            """)

            # Vendor Portal records (external system representation)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vendor_portal_records (
                    invoice_number TEXT PRIMARY KEY,
                    vendor_name TEXT NOT NULL,
                    issue_date TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    total_amount REAL NOT NULL,
                    hash_checksum TEXT
                )
            """)
            conn.commit()

    def record_audit(self, actor: str, action: str, target_entity: str, details: Dict[str, Any], status: str = "SUCCESS"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_log (timestamp, actor, action, target_entity, details, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                actor,
                action,
                target_entity,
                json.dumps(details),
                status
            ))
            conn.commit()

    def fetch_invoice(self, invoice_number: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoices_payable WHERE invoice_number = ?", (invoice_number,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def fetch_invoices_by_vendor(self, vendor_name: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoices_payable WHERE LOWER(vendor_name) LIKE LOWER(?)", (f"%{vendor_name}%",))
            return [dict(r) for r in cursor.fetchall()]

    def fetch_all_invoices(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoices_payable ORDER BY id DESC")
            return [dict(r) for r in cursor.fetchall()]

    def fetch_ledger_entries(self, reference_invoice: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if reference_invoice:
                cursor.execute("SELECT * FROM financial_ledger WHERE reference_invoice = ? ORDER BY id DESC", (reference_invoice,))
            else:
                cursor.execute("SELECT * FROM financial_ledger ORDER BY id DESC")
            return [dict(r) for r in cursor.fetchall()]

    def fetch_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]
