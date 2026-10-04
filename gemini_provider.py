"""Google Gemini LLM provider for live autonomous reasoning."""

import json
import os
import warnings
from typing import Dict, Any, List, Tuple
from app.config import settings
from app.llm.base import BaseLLMProvider
from app.models.task import AgentPlan, PlanStep, StepAction, StepDecision
from app.models.tools import ToolDefinition

warnings.simplefilter("ignore", category=FutureWarning)

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider with structured JSON generation."""

    def __init__(self, api_key: str = "", model_name: str = ""):
        self.api_key = api_key or settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name or settings.gemini_model or "gemini-1.5-flash"
        if HAS_GEMINI and self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
        else:
            self.model = None

    def generate_plan(self, goal: str, available_tools: List[ToolDefinition]) -> AgentPlan:
        if not self.model:
            raise RuntimeError("Gemini API key is not configured. Set GEMINI_API_KEY or use LLM_PROVIDER=deterministic.")

        tools_desc = "\n".join([f"- {t.name}: {t.description}" for t in available_tools])
        prompt = f"""
You are an autonomous AI Task Worker for enterprise operations.
A user gave you the following business goal:
"{goal}"

Available Tools:
{tools_desc}

Break this goal down into a sequence of actionable logical steps.
Return ONLY valid JSON matching this schema:
{{
  "interpreted_objective": "concise statement of the goal",
  "steps": [
    {{"index": 1, "description": "step 1"}},
    {{"index": 2, "description": "step 2"}}
  ]
}}
"""
        response = self.model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
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
        if not self.model:
            raise RuntimeError("Gemini API key is not configured. Set GEMINI_API_KEY or use LLM_PROVIDER=deterministic.")

        tools_desc = json.dumps([{"name": t.name, "description": t.description, "parameters": t.parameters_schema} for t in available_tools], indent=2)
        memory_desc = json.dumps(working_memory, indent=2, default=str)
        history_summary = []
        for t in history_traces[-4:]:
            history_summary.append({
                "step": t.get("step_number"),
                "action": t.get("action", {}).get("tool_name"),
                "args": t.get("action", {}).get("arguments"),
                "success": t.get("observation", {}).get("success"),
                "observation": t.get("observation", {}).get("summary"),
            })

        prompt = f"""
You are an autonomous AI Task Worker executing a task loop.
Goal: {goal}
Current Plan: {[s.description for s in plan.steps]}
Working Memory: {memory_desc}
Recent Action History: {json.dumps(history_summary, indent=2)}
Available Tools:
{tools_desc}

Reason carefully about the current state:
1. Has the goal been completed and independently verified? If yes, set is_terminal to true.
2. If not, what tool should be invoked next with what exact arguments?
3. If an earlier tool call failed, what alternative or recovery action should you take?

Return ONLY valid JSON matching this schema:
{{
  "thought": "Your internal reasoning about current state and next move",
  "tool_name": "exact tool name to invoke",
  "arguments": {{}},
  "rationale": "Why this action is needed",
  "next_step_decision": "What to do after this or what was decided",
  "decision_reason": "Justification for decision",
  "is_terminal": false
}}
"""
        response = self.model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)

        action = StepAction(
            tool_name=data.get("tool_name", "search_company_documents"),
            arguments=data.get("arguments", {}),
            rationale=data.get("rationale", ""),
            thought=data.get("thought", "")
        )
        decision = StepDecision(
            next_step=data.get("next_step_decision", "Proceed to next action"),
            reason=data.get("decision_reason", "")
        )
        is_terminal = bool(data.get("is_terminal", False))

        return action, decision, is_terminal
