"""Document search and extraction tools."""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.config import settings
from app.models.tools import ToolResult
from app.tools.registry import default_registry

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


@default_registry.register(
    name="search_company_documents",
    description="Search company document repository for invoices, agreements, or files matching keywords or company names.",
    category="filesystem"
)
def search_company_documents(query: str, doc_type: Optional[str] = None) -> ToolResult:
    """Searches documents in the sandbox directory."""
    base_dir = settings.sandbox_dir
    if not base_dir.exists():
        return ToolResult(
            success=False,
            tool_name="search_company_documents",
            output="Document repository directory does not exist.",
            error="DirectoryNotFound",
        )

    matched_files = []
    q_lower = query.lower()

    for root, _, files in os.walk(base_dir):
        for f in sorted(files):
            file_path = Path(root) / f
            rel_path = file_path.relative_to(base_dir).as_posix()

            # Filter by doc_type if provided
            if doc_type and doc_type.lower() not in rel_path.lower():
                continue

            # Check filename match or read text preview for match
            name_match = q_lower in f.lower() or q_lower in rel_path.lower()
            content_match = False
            preview = ""

            try:
                if file_path.suffix.lower() in (".txt", ".json"):
                    content = file_path.read_text(encoding="utf-8")
                    content_match = q_lower in content.lower()
                    preview = content[:200].replace("\n", " ").strip()
                elif file_path.suffix.lower() == ".pdf" and HAS_PYPDF:
                    reader = PdfReader(str(file_path))
                    text = "".join(page.extract_text() or "" for page in reader.pages)
                    content_match = q_lower in text.lower()
                    preview = text[:200].replace("\n", " ").strip()
            except Exception:
                pass

            if name_match or content_match:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                matched_files.append({
                    "relative_path": rel_path,
                    "filename": f,
                    "size_bytes": file_path.stat().st_size,
                    "last_modified": mtime,
                    "preview": preview,
                })

    if not matched_files:
        return ToolResult(
            success=True,
            tool_name="search_company_documents",
            output=f"No documents matched query '{query}'.",
            data={"count": 0, "results": []},
            evidence="Query executed across sandbox repository; zero files matched.",
        )

    output_lines = [f"Found {len(matched_files)} matching documents:"]
    for idx, item in enumerate(matched_files, 1):
        output_lines.append(f"{idx}. {item['relative_path']} (Modified: {item['last_modified']}) - {item['preview']}")

    return ToolResult(
        success=True,
        tool_name="search_company_documents",
        output="\n".join(output_lines),
        data={"count": len(matched_files), "results": matched_files},
        evidence=f"Matched {len(matched_files)} documents in repository.",
    )


@default_registry.register(
    name="read_document",
    description="Read the complete text content of a document (txt, json, or pdf).",
    category="filesystem"
)
def read_document(file_path: str) -> ToolResult:
    """Reads a text or PDF file from the sandbox directory."""
    target = Path(file_path)
    if not target.is_absolute():
        target = settings.sandbox_dir / file_path

    if not target.exists():
        return ToolResult(
            success=False,
            tool_name="read_document",
            output=f"File not found: {target.name}",
            error=f"FileNotFoundError: {file_path}",
        )

    try:
        if target.suffix.lower() == ".pdf":
            if not HAS_PYPDF:
                return ToolResult(
                    success=False,
                    tool_name="read_document",
                    output="pypdf library not available to parse PDF.",
                    error="DependencyMissing: pypdf",
                )
            reader = PdfReader(str(target))
            full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            full_text = target.read_text(encoding="utf-8")

        return ToolResult(
            success=True,
            tool_name="read_document",
            output=full_text,
            data={"file_path": str(target), "character_count": len(full_text)},
            evidence=f"Read {len(full_text)} characters from {target.name}",
        )
    except Exception as exc:
        return ToolResult(
            success=False,
            tool_name="read_document",
            output=f"Failed to read file: {str(exc)}",
            error=f"ReadError: {str(exc)}",
        )


@default_registry.register(
    name="extract_invoice_data",
    description="Parse raw document text or file to extract structured invoice fields (invoice_number, vendor_name, amount, due_date, issue_date).",
    category="parser"
)
def extract_invoice_data(file_path: str) -> ToolResult:
    """Extracts structured invoice information with validation."""
    read_res = read_document(file_path)
    if not read_res.success:
        return read_res

    text = read_res.output

    # Invoice number regex
    inv_match = re.search(r"(?:INVOICE|Invoice|INV)[\s:#-]*([A-Z0-9-]+)", text)
    invoice_number = inv_match.group(1).strip() if inv_match else None

    # Vendor name regex
    vendor_match = re.search(r"(?:Vendor|Company|From)[\s:#]+([A-Za-z0-9\s.,]+?)(?:\n|Tax|Date|Email)", text)
    vendor_name = vendor_match.group(1).strip() if vendor_match else None

    # Amount regex - search for total balance, total due, total amount, or currency amounts
    amount = None
    # 1. Look for explicit total patterns
    total_patterns = [
        r"(?:TOTAL BALANCE DUE|TOTAL AMOUNT DUE|TOTAL DUE|BALANCE DUE|TOTAL BALANCE|TOTAL|BALANCE)[\s:#$A-Za-z()]*\$?\s*([0-9,]+\.[0-9]{2})",
        r"(?:Amount Due|Amount)[\s:#$A-Za-z()]*\$?\s*([0-9,]+\.[0-9]{2})",
        r"\$\s*([0-9,]+\.[0-9]{2})",
    ]
    for pat in total_patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        if matches:
            try:
                # Find maximum or last total
                candidates = [float(m.replace(",", "")) for m in matches]
                amount = max(candidates)
                break
            except ValueError:
                continue

    # Due Date regex
    due_date_match = re.search(r"Due Date[\s:#]*([0-9]{4}-[0-9]{2}-[0-9]{2})", text, re.IGNORECASE)
    due_date = due_date_match.group(1).strip() if due_date_match else None

    # Issue Date regex
    issue_date_match = re.search(r"(?:Invoice Date|Issue Date|Date)[\s:#]*([0-9]{4}-[0-9]{2}-[0-9]{2})", text, re.IGNORECASE)
    issue_date = issue_date_match.group(1).strip() if issue_date_match else None

    # Check for corrupted fields
    corrupted_fields = []
    if "SCAN_BLUR" in text or "CORRUPTED" in text or "UNREADABLE" in text:
        if not due_date:
            corrupted_fields.append("due_date")
    if due_date is None and "due_date" not in corrupted_fields:
        corrupted_fields.append("due_date")

    parsed_data = {
        "invoice_number": invoice_number,
        "vendor_name": vendor_name,
        "amount": amount,
        "due_date": due_date,
        "issue_date": issue_date,
        "corrupted_fields": corrupted_fields,
        "source_file": file_path,
    }

    # If any critical field is missing or corrupted, report with action guidance
    if corrupted_fields or not all([invoice_number, vendor_name, amount is not None, due_date is not None]):
        missing = [k for k, v in parsed_data.items() if v is None and k != "issue_date"]
        missing.extend([c for c in corrupted_fields if c not in missing])
        return ToolResult(
            success=False,
            tool_name="extract_invoice_data",
            output=f"Partial extraction failure: fields {missing} could not be cleanly extracted or are corrupted.",
            data=parsed_data,
            evidence=f"Extracted partial data from {file_path}: {parsed_data}",
            error="DataExtractionIncompleteError",
        )

    return ToolResult(
        success=True,
        tool_name="extract_invoice_data",
        output=f"Successfully extracted: Invoice {invoice_number} from {vendor_name}, Amount: ${amount:,.2f}, Due: {due_date}",
        data=parsed_data,
        evidence=f"Structured invoice fields validated for {invoice_number}: ${amount:,.2f} due {due_date}",
    )
