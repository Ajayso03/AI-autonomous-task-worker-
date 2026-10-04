"""Verification models and check results."""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"


class VerificationCheck(BaseModel):
    check_name: str
    target_entity: str
    field_name: str
    expected_value: Any
    actual_value: Any
    status: CheckStatus
    evidence_source: str
    details: str = ""


class VerificationReport(BaseModel):
    verified: bool
    passed_count: int
    total_count: int
    checks: List[VerificationCheck] = Field(default_factory=list)
    independent_query_data: Optional[Dict[str, Any]] = None
    summary: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
