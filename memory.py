"""Working memory and state management for autonomous worker."""

from typing import Dict, Any, List, Optional
from datetime import datetime


class AgentMemory:
    """Manages working memory, discovered entities, action history, and execution context."""

    def __init__(self):
        self.working_memory: Dict[str, Any] = {}
        self.discovered_entities: Dict[str, Any] = {}
        self.history_traces: List[Dict[str, Any]] = []
        self.evidence_log: List[str] = []
        self.tool_call_counts: Dict[str, int] = {}
        self.tool_failure_counts: Dict[str, int] = {}

    def set(self, key: str, value: Any):
        self.working_memory[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.working_memory.get(key, default)

    def register_entity(self, entity_type: str, entity_id: str, data: Dict[str, Any]):
        if entity_type not in self.discovered_entities:
            self.discovered_entities[entity_type] = {}
        self.discovered_entities[entity_type][entity_id] = data

    def add_trace(self, trace_dict: Dict[str, Any]):
        self.history_traces.append(trace_dict)
        tool_name = trace_dict.get("action", {}).get("tool_name", "unknown")
        self.tool_call_counts[tool_name] = self.tool_call_counts.get(tool_name, 0) + 1

        obs = trace_dict.get("observation", {})
        if not obs.get("success", False):
            self.tool_failure_counts[tool_name] = self.tool_failure_counts.get(tool_name, 0) + 1

        evidence = obs.get("evidence")
        if evidence and evidence not in self.evidence_log:
            self.evidence_log.append(evidence)

    def get_failure_count(self, tool_name: str) -> int:
        return self.tool_failure_counts.get(tool_name, 0)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "working_memory": dict(self.working_memory),
            "discovered_entities": dict(self.discovered_entities),
            "tool_call_counts": dict(self.tool_call_counts),
            "tool_failure_counts": dict(self.tool_failure_counts),
            "evidence_count": len(self.evidence_log),
        }
