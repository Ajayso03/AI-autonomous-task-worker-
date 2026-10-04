"""Tool representation and execution schemas."""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    category: str
    is_reversible: bool = True
    requires_approval: bool = False
    approval_reason: Optional[str] = None


class ToolCall(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    call_id: Optional[str] = None


class ToolResult(BaseModel):
    success: bool
    tool_name: str
    output: str
    data: Optional[Dict[str, Any]] = None
    evidence: str = ""
    error: Optional[str] = None
    execution_time_ms: float = 0.0
