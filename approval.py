"""Human in the loop approval models."""

from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ApprovalRequest(BaseModel):
    request_id: str
    task_id: str
    risk_level: RiskLevel
    action_name: str
    parameters: Dict[str, Any]
    reason: str
    threshold_value: Optional[float] = None
    actual_value: Optional[float] = None
    context_summary: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ApprovalDecision(BaseModel):
    request_id: str
    status: ApprovalStatus
    approved_by: str = "human_operator"
    comment: Optional[str] = None
    decided_at: str = Field(default_factory=lambda: datetime.now().isoformat())
