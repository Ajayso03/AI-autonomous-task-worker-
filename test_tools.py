"""Tests for Tool Registry, Tool Definition, and Execution Harness."""

import pytest
from app.environment.seed_data import seed_sandbox
from app.tools import default_registry
from app.models.tools import ToolCall, ToolResult
from app.tools.document_tools import search_company_documents, read_document, extract_invoice_data
from app.tools.erp_tools import query_accounts_payable, create_payable_record, inspect_database_record
from app.tools.portal_tools import query_vendor_portal


@pytest.fixture(autouse=True)
def setup_environment():
    seed_sandbox()


def test_tool_registry_registration():
    """Verify tool registration and schema generation."""
    tools = default_registry.list_definitions()
    assert len(tools) >= 8

    tool_names = [t.name for t in tools]
    assert "search_company_documents" in tool_names
    assert "extract_invoice_data" in tool_names
    assert "create_payable_record" in tool_names
    assert "inspect_database_record" in tool_names


def test_tool_execution_unrecognized_tool():
    """Calling an unrecognized tool returns structured error without crashing."""
    call = ToolCall(tool_name="non_existent_tool", arguments={})
    res = default_registry.execute(call)
    assert not res.success
    assert "ToolNotFound" in res.error


def test_tool_execution_invalid_arguments():
    """Calling a tool with missing or invalid arguments returns ArgumentValidationError."""
    call = ToolCall(tool_name="create_payable_record", arguments={"invalid_arg": 123})
    res = default_registry.execute(call)
    assert not res.success
    assert "ArgumentValidationError" in res.error


def test_search_documents():
    """Test searching repository files."""
    res = search_company_documents(query="Acme")
    assert res.success
    assert res.data["count"] >= 2
    assert any("INV-2024-089" in r["filename"] for r in res.data["results"])


def test_extract_invoice_data_pdf():
    """Test extracting fields from real PDF invoice."""
    res = extract_invoice_data("invoices/INV-2024-089_AcmeCorp_Latest.pdf")
    assert res.success
    assert res.data["invoice_number"] == "INV-2024-089"
    assert res.data["amount"] == 3450.0
    assert res.data["due_date"] == "2024-10-25"


def test_extract_invoice_data_corrupt_scan():
    """Test extraction failure detection on damaged document."""
    res = extract_invoice_data("invoices/INV-2024-301_Initech_CorruptScan.txt")
    assert not res.success
    assert "DataExtractionIncompleteError" in res.error
    assert "due_date" in res.data.get("corrupted_fields", [])


def test_create_payable_record_duplicate_prevention():
    """Creating duplicate invoice payable record should be safely rejected."""
    res1 = create_payable_record(
        invoice_number="INV-TEST-DUP-01",
        vendor_name="Test Vendor",
        amount=100.0,
        due_date="2025-01-01"
    )
    assert res1.success

    res2 = create_payable_record(
        invoice_number="INV-TEST-DUP-01",
        vendor_name="Test Vendor",
        amount=100.0,
        due_date="2025-01-01"
    )
    assert not res2.success
    assert "DuplicateRecordError" in res2.error


def test_inspect_database_security_guard():
    """Inspecting non-whitelisted database tables is blocked for security."""
    res = inspect_database_record(table_name="sqlite_master", key_field="type", key_value="table")
    assert not res.success
    assert "SecurityViolationError" in res.error
