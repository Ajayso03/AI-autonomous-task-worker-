"""Vendor Portal API and external integration tools."""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.config import settings
from app.environment.company_sandbox import CompanySandbox
from app.models.tools import ToolResult
from app.tools.registry import default_registry


@default_registry.register(
    name="query_vendor_portal",
    description="Query external vendor portal / clearinghouse API for official invoice metadata and verification status.",
    category="external_api"
)
def query_vendor_portal(vendor_name: Optional[str] = None, invoice_number: Optional[str] = None) -> ToolResult:
    """Queries external vendor portal database."""
    sb = CompanySandbox()
    with sb.get_connection() as conn:
        cursor = conn.cursor()
        if invoice_number:
            cursor.execute("SELECT * FROM vendor_portal_records WHERE invoice_number = ?", (invoice_number,))
        elif vendor_name:
            cursor.execute("SELECT * FROM vendor_portal_records WHERE LOWER(vendor_name) LIKE LOWER(?)", (f"%{vendor_name}%",))
        else:
            cursor.execute("SELECT * FROM vendor_portal_records ORDER BY issue_date DESC")

        rows = [dict(r) for r in cursor.fetchall()]

    if not rows:
        return ToolResult(
            success=False,
            tool_name="query_vendor_portal",
            output=f"Vendor portal query returned 0 records for criteria (vendor='{vendor_name}', invoice='{invoice_number}').",
            data={"count": 0, "records": []},
            error="PortalRecordNotFound",
        )

    return ToolResult(
        success=True,
        tool_name="query_vendor_portal",
        output=f"Vendor portal API returned {len(rows)} official records: " + json.dumps(rows, default=str),
        data={"count": len(rows), "records": rows},
        evidence=f"Vendor portal verified {len(rows)} invoice records against clearinghouse API.",
    )


@default_registry.register(
    name="download_portal_attachment",
    description="Download a fresh official digital invoice copy from the vendor portal when local files are damaged or incomplete.",
    category="external_api"
)
def download_portal_attachment(invoice_number: str) -> ToolResult:
    """Recovers a pristine digital document copy from portal storage."""
    sb = CompanySandbox()
    portal_res = query_vendor_portal(invoice_number=invoice_number)
    if not portal_res.success or not portal_res.data.get("records"):
        return ToolResult(
            success=False,
            tool_name="download_portal_attachment",
            output=f"Cannot download attachment: invoice {invoice_number} not found in portal registry.",
            error="PortalAttachmentNotFound",
        )

    rec = portal_res.data["records"][0]
    out_dir = settings.sandbox_dir / "vendor_portal" / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{invoice_number}_official_copy.txt"

    clean_content = f"""
======================================================================
OFFICIAL CLEARINGHOUSE INVOICE COPY: {rec['invoice_number']}
Vendor: {rec['vendor_name']}
Issue Date: {rec['issue_date']}
Due Date: {rec['due_date']}
Total Amount Due: ${rec['total_amount']:,.2f}
Checksum: {rec.get('hash_checksum', 'SECURE_HASH')}
Status: VERIFIED_DIGITAL_ORIGINAL
======================================================================
""".strip()
    out_path.write_text(clean_content, encoding="utf-8")

    return ToolResult(
        success=True,
        tool_name="download_portal_attachment",
        output=f"Successfully downloaded pristine portal invoice to {out_path.relative_to(settings.sandbox_dir)}. Due Date: {rec['due_date']}, Amount: ${rec['total_amount']:,.2f}",
        data={
            "local_path": str(out_path.relative_to(settings.sandbox_dir)),
            "invoice_number": rec['invoice_number'],
            "due_date": rec['due_date'],
            "amount": rec['total_amount'],
        },
        evidence=f"Retrieved clean backup document from portal clearinghouse for {invoice_number}.",
    )
