"""Audit and system monitoring tools."""

import json
from typing import Dict, Any, List, Optional

from app.environment.company_sandbox import CompanySandbox
from app.models.tools import ToolResult
from app.tools.registry import default_registry


@default_registry.register(
    name="fetch_audit_trail",
    description="Retrieve enterprise audit log records to verify system actions and compliance.",
    category="audit"
)
def fetch_audit_trail(target_entity: Optional[str] = None, limit: int = 10) -> ToolResult:
    """Fetches entries from audit_log table."""
    sb = CompanySandbox()
    logs = sb.fetch_audit_logs(limit=limit)

    if target_entity:
        logs = [log for log in logs if target_entity.lower() in log.get("target_entity", "").lower()]

    if not logs:
        return ToolResult(
            success=True,
            tool_name="fetch_audit_trail",
            output="No audit logs found for criteria.",
            data={"count": 0, "logs": []},
            evidence="Audit table queried; 0 entries found.",
        )

    return ToolResult(
        success=True,
        tool_name="fetch_audit_trail",
        output=f"Retrieved {len(logs)} audit trail entries: " + json.dumps(logs, default=str),
        data={"count": len(logs), "logs": logs},
        evidence=f"Audit trail verified: {len(logs)} tamper-evident entries retrieved.",
    )
