"""Abstract LLM Provider interface for the autonomous worker."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple
from app.models.task import AgentPlan, StepAction, StepDecision
from app.models.tools import ToolDefinition


class BaseLLMProvider(ABC):
    """Abstract interface defining required LLM capabilities for the autonomous agent."""

    @abstractmethod
    def generate_plan(self, goal: str, available_tools: List[ToolDefinition]) -> AgentPlan:
        """Deconstructs the user goal into an initial structured execution plan."""
        pass

    @abstractmethod
    def decide_next_action(
        self,
        goal: str,
        plan: AgentPlan,
        available_tools: List[ToolDefinition],
        working_memory: Dict[str, Any],
        history_traces: List[Dict[str, Any]],
        step_number: int,
    ) -> Tuple[StepAction, StepDecision, bool]:
        """Decides the next action to take based on the current goal, plan, memory, and observations.

        Returns: (StepAction, StepDecision, is_terminal)
        """
        pass
