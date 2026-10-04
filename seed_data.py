"""Database and file system seeder for enterprise sandbox testing."""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from app.config import settings
from app.environment.company_sandbox import CompanySandbox

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def generate_invoice_pdf(file_path: Path, invoice_data: dict):
    """Generate a genuine PDF invoice using ReportLab if installed."""
    if not HAS_REPORTLAB:
        # Fallback to plain text if reportlab is not present
        file_path.with_suffix(".txt").write_text(json.dumps(invoice_data, indent=2), encoding="utf-8")
        return

    c = canvas.Canvas(str(file_path), pagesize=letter)
    width, height = letter

    # Header
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 60, f"OFFICIAL INVOICE: {invoice_data['invoice_number']}")
    c.setLineWidth(1)
    c.line(50, height - 70, width - 50, height - 70)

    # Vendor Details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 100, f"Vendor: {invoice_data['vendor_name']}")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 120, f"Tax ID / EIN: {invoice_data.get('tax_id', 'US-9823471')}")
    c.drawString(50, height - 135, f"Billing Email: billing@{invoice_data['vendor_name'].lower().replace(' ', '')}.com")

    # Dates and Amount
    c.setFont("Helvetica-Bold", 11)
    c.drawString(350, height - 100, f"Issue Date: {invoice_data['issue_date']}")
    c.drawString(350, height - 120, f"Due Date: {invoice_data['due_date']}")
    c.drawString(350, height - 140, f"Payment Terms: {invoice_data.get('terms', 'Net 30')}")

    # Line item table box
    c.rect(50, height - 260, width - 100, 90)
    c.drawString(60, height - 190, "Description")
    c.drawString(450, height - 190, "Amount (USD)")
    c.line(50, height - 200, width - 50, height - 200)

    c.setFont("Helvetica", 10)
    c.drawString(60, height - 225, invoice_data.get("description", "Enterprise Cloud & Software Licensing Services"))
    c.drawRightString(width - 65, height - 225, f"${invoice_data['total_amount']:,.2f}")

    # Total Box
    c.setFont("Helvetica-Bold", 14)
    c.drawString(300, height - 300, f"TOTAL BALANCE DUE: ${invoice_data['total_amount']:,.2f}")
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, height - 340, "Thank you for your business. Remit payment to corporate account wire routing.")

    c.save()


def seed_sandbox(sandbox: Optional[CompanySandbox] = None) -> CompanySandbox:
    """Seeds the SQLite database and file system with enterprise test data."""
    sb = sandbox or CompanySandbox()
    db_conn = sb.get_connection()

    with db_conn:
        cursor = db_conn.cursor()

        # Clear existing rows to guarantee clean state
        cursor.execute("DELETE FROM invoices_payable")
        cursor.execute("DELETE FROM financial_ledger")
        cursor.execute("DELETE FROM audit_log")
        cursor.execute("DELETE FROM vendor_portal_records")
        cursor.execute("DELETE FROM vendors")

        # 1. Seed Vendors
        vendors = [
            ("VEN-001", "Acme Corp", "US-9912381", "ap@acmecorp.com", "Net 30"),
            ("VEN-002", "Cyberdyne Systems", "US-8841290", "finance@cyberdyne.io", "Net 15"),
            ("VEN-003", "Stark Industries", "US-7719283", "invoicing@starkindustries.com", "Net 30"),
            ("VEN-004", "Initech LLC", "US-6612984", "billing@initech.org", "Net 30"),
            ("VEN-005", "Wayne Enterprises", "US-5541928", "accounting@wayne.corp", "Net 45"),
        ]
        cursor.executemany("""
            INSERT INTO vendors (vendor_id, name, tax_id, contact_email, payment_terms)
            VALUES (?, ?, ?, ?, ?)
        """, vendors)

        # 2. Seed Vendor Portal Records (External Truth)
        portal_records = [
            ("INV-2024-001", "Acme Corp", "2024-01-10", "2024-02-15", 1250.00, "hash_acme_001"),
            ("INV-2024-089", "Acme Corp", "2024-09-15", "2024-10-25", 3450.00, "hash_acme_089"),
            ("INV-2024-104", "Cyberdyne Systems", "2024-10-01", "2024-11-01", 4800.00, "hash_cyb_104"),
            ("INV-2024-205", "Stark Industries", "2024-10-05", "2024-11-15", 14200.00, "hash_stk_205"),
            ("INV-2024-301", "Initech LLC", "2024-10-12", "2024-12-01", 2150.00, "hash_ini_301"),
        ]
        cursor.executemany("""
            INSERT INTO vendor_portal_records (invoice_number, vendor_name, issue_date, due_date, total_amount, hash_checksum)
            VALUES (?, ?, ?, ?, ?, ?)
        """, portal_records)

        # Initial Audit Record
        cursor.execute("""
            INSERT INTO audit_log (timestamp, actor, action, target_entity, details, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            "SYSTEM_SEEDER",
            "INITIALIZE_ENVIRONMENT",
            "ERP_DATABASE",
            json.dumps({"seeded_vendors": len(vendors), "seeded_portal_records": len(portal_records)}),
            "INITIALIZED"
        ))
        db_conn.commit()

    # 3. Create Files in Sandbox Directory
    base_dir = sb.sandbox_dir
    invoices_dir = base_dir / "invoices"
    contracts_dir = base_dir / "contracts"
    portal_dir = base_dir / "vendor_portal"

    invoices_dir.mkdir(parents=True, exist_ok=True)
    contracts_dir.mkdir(parents=True, exist_ok=True)
    portal_dir.mkdir(parents=True, exist_ok=True)

    # 3A. Acme Corp Invoices (One older, one latest)
    (invoices_dir / "INV-2024-001_AcmeCorp_Jan.txt").write_text("""
======================================================================
INVOICE: INV-2024-001
Vendor: Acme Corp
Date: 2024-01-10
Due Date: 2024-02-15
Description: Initial consulting onboarding services
Subtotal: $1,250.00
Tax: $0.00
Total Balance: $1,250.00
Status: Historical Archive (Paid)
======================================================================
""".strip(), encoding="utf-8")

    acme_latest_data = {
        "invoice_number": "INV-2024-089",
        "vendor_name": "Acme Corp",
        "issue_date": "2024-09-15",
        "due_date": "2024-10-25",
        "total_amount": 3450.00,
        "description": "Enterprise API & Platform Subscription - Q3",
        "terms": "Net 30",
    }
    # Write both text and PDF version for full multi-modal compatibility
    (invoices_dir / "INV-2024-089_AcmeCorp_Latest.txt").write_text("""
======================================================================
OFFICIAL INVOICE: INV-2024-089
Vendor: Acme Corp
Tax ID: US-9912381
Invoice Date: 2024-09-15
Due Date: 2024-10-25
Payment Terms: Net 30
Item: Enterprise API & Platform Subscription - Q3
Total Amount Due: $3,450.00
Remittance: ACH to routing 021000021 / acct 8829104
======================================================================
""".strip(), encoding="utf-8")
    generate_invoice_pdf(invoices_dir / "INV-2024-089_AcmeCorp_Latest.pdf", acme_latest_data)

    # 3B. Cyberdyne Systems Invoice
    (invoices_dir / "INV-2024-104_CyberdyneSystems.txt").write_text("""
======================================================================
INVOICE: INV-2024-104
Vendor: Cyberdyne Systems
Tax ID: US-8841290
Issue Date: 2024-10-01
Due Date: 2024-11-01
Service: Autonomous Neural Hardware Infrastructure Cluster Support
Amount Due: $4,800.00
Payment Terms: Net 15
Please remit via wire transfer within payment terms.
======================================================================
""".strip(), encoding="utf-8")

    # 3C. Stark Industries High-Value Invoice ($14,200 > $5,000 threshold)
    stark_data = {
        "invoice_number": "INV-2024-205",
        "vendor_name": "Stark Industries",
        "issue_date": "2024-10-05",
        "due_date": "2024-11-15",
        "total_amount": 14200.00,
        "description": "Arc Reactor Clean Energy Substation Maintenance",
        "terms": "Net 30",
    }
    (invoices_dir / "INV-2024-205_StarkIndustries_HighValue.txt").write_text("""
======================================================================
INVOICE: INV-2024-205
Vendor: Stark Industries
Tax ID: US-7719283
Issue Date: 2024-10-05
Due Date: 2024-11-15
Line Items: Arc Reactor Clean Energy Substation Maintenance
Total Amount Due: $14,200.00
POLICY WARNING: Transactions over $5,000 require CFO / Controller approval.
======================================================================
""".strip(), encoding="utf-8")
    generate_invoice_pdf(invoices_dir / "INV-2024-205_StarkIndustries_HighValue.pdf", stark_data)

    # 3D. Initech Invoice with OCR error/corruption in Due Date
    (invoices_dir / "INV-2024-301_Initech_CorruptScan.txt").write_text("""
======================================================================
INVOICE: INV-2024-301
Vendor: Initech LLC
Date: 2024-10-12
Due Date: [SCAN_BLUR_CORRUPTED_VALUE - REQUERY_PORTAL]
Description: Enterprise TPS Report Automation Module License
Total Due: $2,150.00
Notice: Due date field damaged during scan. Consult vendor portal record.
======================================================================
""".strip(), encoding="utf-8")

    # 3E. Portal backup index JSON
    portal_index = {
        "portal_version": "2.4.0",
        "last_sync": datetime.now().isoformat(),
        "records": [
            {
                "invoice_number": "INV-2024-001",
                "vendor": "Acme Corp",
                "amount": 1250.00,
                "due_date": "2024-02-15",
                "status": "ARCHIVED"
            },
            {
                "invoice_number": "INV-2024-089",
                "vendor": "Acme Corp",
                "amount": 3450.00,
                "due_date": "2024-10-25",
                "status": "APPROVED"
            },
            {
                "invoice_number": "INV-2024-104",
                "vendor": "Cyberdyne Systems",
                "amount": 4800.00,
                "due_date": "2024-11-01",
                "status": "VERIFIED"
            },
            {
                "invoice_number": "INV-2024-205",
                "vendor": "Stark Industries",
                "amount": 14200.00,
                "due_date": "2024-11-15",
                "status": "PENDING_CFO_SIGN_OFF"
            },
            {
                "invoice_number": "INV-2024-301",
                "vendor": "Initech LLC",
                "amount": 2150.00,
                "due_date": "2024-12-01",
                "status": "ACTIVE_ACCURATE"
            }
        ]
    }
    (portal_dir / "portal_index.json").write_text(json.dumps(portal_index, indent=2), encoding="utf-8")

    return sb


if __name__ == "__main__":
    sb = seed_sandbox()
    print(f"Successfully seeded sandbox at {sb.db_path} and {sb.sandbox_dir}")
