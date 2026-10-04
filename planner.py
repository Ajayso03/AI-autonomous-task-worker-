"""Plan generation and dynamic progression."""

from typing import List, Optional
from app.llm.base import BaseLLMProvider
from app.models.task import AgentPlan, PlanStep
from app.models.tools import ToolDefinition


class DynamicPlanner:
    """Manages creation, execution tracking, and adaptive updates of the agent plan."""

    def __init__(self, llm_provider: BaseLLMProvider):
        self.llm_provider = llm_provider

    def create_initial_plan(self, goal: str, available_tools: List[ToolDefinition]) -> AgentPlan:
        return self.llm_provider.generate_plan(goal, available_tools)

    def mark_step_complete(self, plan: AgentPlan, step_index: int, notes: Optional[str] = None):
        for s in plan.steps:
            if s.index == step_index:
                s.completed = True
                s.notes = notes
                break
        plan.current_step_index = min(step_index, len(plan.steps) - 1)
