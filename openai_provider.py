"""OpenAI LLM provider for autonomous reasoning."""

import json
import os
from typing import Dict, Any, List, Tuple
from app.config import settings
from app.llm.base import BaseLLMProvider
from app.models.task import AgentPlan, PlanStep, StepAction, StepDecision
from app.models.tools import ToolDefinition

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider using function schemas and JSON output."""

    def __init__(self, api_key: str = "", model_name: str = ""):
        self.api_key = api_key or settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model_name = model_name or settings.openai_model or "gpt-4o-mini"
        if HAS_OPENAI and self.api_key:
            self.client = openai.OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def generate_plan(self, goal: str, available_tools: List[ToolDefinition]) -> AgentPlan:
        if not self.client:
            raise RuntimeError("OpenAI API key is not configured. Set OPENAI_API_KEY or use LLM_PROVIDER=deterministic.")

        tools_desc = "\n".join([f"- {t.name}: {t.description}" for t in available_tools])
        response = self.client.chat.completions.create(
            model=self.model_name,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are an autonomous enterprise AI task planner. Return JSON."},
                {"role": "user", "content": f"Goal: {goal}\nTools:\n{tools_desc}\nReturn {{\"interpreted_objective\": \"...\", \"steps\": [{{\"index\": 1, \"description\": \"...\"}}]}}"}
            ]
        )
        data = json.loads(response.choices[0].message.content)
        steps = [PlanStep(index=s["index"], description=s["description"]) for s in data.get("steps", [])]
        return AgentPlan(
            goal=goal,
            interpreted_objective=data.get("interpreted_objective", goal),
            steps=steps,
            current_step_index=0
        )

    def decide_next_action(
        self,
        goal: str,
        plan: AgentPlan,
        available_tools: List[ToolDefinition],
        working_memory: Dict[str, Any],
        history_traces: List[Dict[str, Any]],
        step_number: int,
    ) -> Tuple[StepAction, StepDecision, bool]:
        if not self.client:
            raise RuntimeError("OpenAI API key is not configured. Set OPENAI_API_KEY or use LLM_PROVIDER=deterministic.")

        tools_desc = json.dumps([{"name": t.name, "description": t.description, "parameters": t.parameters_schema} for t in available_tools])
        response = self.client.chat.completions.create(
            model=self.model_name,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are an autonomous agent ReAct execution loop. Output valid JSON with thought, tool_name, arguments, rationale, next_step_decision, decision_reason, and is_terminal."},
                {"role": "user", "content": f"Goal: {goal}\nMemory: {json.dumps(working_memory, default=str)}\nTools: {tools_desc}\nHistory steps count: {len(history_traces)}"}
            ]
        )
        data = json.loads(response.choices[0].message.content)
        action = StepAction(
            tool_name=data.get("tool_name", "search_company_documents"),
            arguments=data.get("arguments", {}),
            rationale=data.get("rationale", ""),
            thought=data.get("thought", "")
        )
        decision = StepDecision(
            next_step=data.get("next_step_decision", "Execute next step"),
            reason=data.get("decision_reason", "")
        )
        is_terminal = bool(data.get("is_terminal", False))
        return action, decision, is_terminal
