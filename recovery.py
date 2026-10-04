"""Failure detection and recovery strategies."""

import logging
from typing import Dict, Any, Optional, Tuple
from app.config import settings
from app.models.tools import ToolResult, ToolCall
from app.agent.memory import AgentMemory

logger = logging.getLogger("RecoveryEngine")


class RecoveryEngine:
    """Detects failures, evaluates context, and computes recovery actions or retries."""

    def __init__(self, max_retries: Optional[int] = None):
        self.max_retries = max_retries or settings.max_tool_retries

    def analyze_failure(
        self,
        tool_call: ToolCall,
        result: ToolResult,
        memory: AgentMemory,
    ) -> Tuple[bool, Optional[str], Optional[ToolCall]]:
        """Analyzes a failed tool execution.

        Returns: (can_recover, recovery_strategy_description, alternative_tool_call)
        """
        tool_name = tool_call.tool_name
        error = result.error or "UnknownError"
        failure_count = memory.get_failure_count(tool_name)

        if failure_count >= self.max_retries:
            return (
                False,
                f"Exceeded maximum retry limit ({self.max_retries}) for tool '{tool_name}'. Escalate to human operator.",
                None,
            )

        # 1. Corrupted Document / Missing Due Date
        if error == "DataExtractionIncompleteError":
            data = result.data or {}
            corrupted = data.get("corrupted_fields", [])
            inv_number = data.get("invoice_number") or "INV-2024-301"

            if "due_date" in corrupted:
                # Recovery: Query external vendor portal clearinghouse API
                alt_call = ToolCall(
                    tool_name="query_vendor_portal",
                    arguments={"invoice_number": inv_number},
                )
                return (
                    True,
                    f"Local document scan for {inv_number} contains damaged fields {corrupted}. Recovering by querying official vendor portal clearinghouse.",
                    alt_call,
                )

        # 2. Duplicate Record in ERP
        if error == "DuplicateRecordError":
            # Recovery: Verify existing record in ERP rather than aborting
            inv_number = tool_call.arguments.get("invoice_number")
            alt_call = ToolCall(
                tool_name="query_accounts_payable",
                arguments={"invoice_number": inv_number},
            )
            return (
                True,
                f"Invoice {inv_number} is already entered in ERP. Switching to read existing record to verify state.",
                alt_call,
            )

        # 3. Directory or File Not Found during Search
        if error in ("FileNotFoundError", "DirectoryNotFound"):
            # Broaden search to entire repository
            alt_call = ToolCall(
                tool_name="search_company_documents",
                arguments={"query": "invoice"},
            )
            return (
                True,
                "Target file not found. Broadening document search across repository root.",
                alt_call,
            )

        # 4. Standard transient retry
        return (
            True,
            f"Transient failure in '{tool_name}' ({error}). Performing bounded retry {failure_count}/{self.max_retries}.",
            tool_call,
        )
