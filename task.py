"""Task and execution trace models."""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.verification import VerificationReport
from app.models.approval import ApprovalRequest


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RECOVERING = "RECOVERING"
    VERIFYING = "VERIFYING"
    COMPLETED_VERIFIED = "COMPLETED_VERIFIED"
    COMPLETED_UNVERIFIED = "COMPLETED_UNVERIFIED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"


class StepAction(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    thought: str = ""


class StepObservation(BaseModel):
    success: bool
    summary: str
    data: Optional[Dict[str, Any]] = None
    evidence: str = ""
    error: Optional[str] = None
    execution_time_ms: float = 0.0


class StepDecision(BaseModel):
    next_step: str
    reason: str
    status_update: Optional[TaskStatus] = None


class StepTrace(BaseModel):
    step_number: int
    action: StepAction
    observation: StepObservation
    decision: StepDecision
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class PlanStep(BaseModel):
    index: int
    description: str
    completed: bool = False
    notes: Optional[str] = None


class AgentPlan(BaseModel):
    goal: str
    interpreted_objective: str
    steps: List[PlanStep] = Field(default_factory=list)
    current_step_index: int = 0


class AgentExecutionSummary(BaseModel):
    task_id: str
    original_goal: str
    status: TaskStatus
    plan: Optional[AgentPlan] = None
    total_steps: int
    traces: List[StepTrace] = Field(default_factory=list)
    discovered_entities: Dict[str, Any] = Field(default_factory=dict)
    verification_report: Optional[VerificationReport] = None
    pending_approval: Optional[ApprovalRequest] = None
    evidence: List[str] = Field(default_factory=list)
    completion_message: str = ""
    execution_time_seconds: float = 0.0
