"""Tool Registry and execution harness."""

import time
import inspect
from typing import Callable, Dict, Any, List, Optional
from pydantic import BaseModel, create_model

from app.models.tools import ToolDefinition, ToolResult, ToolCall


class ToolRegistry:
    """Central registry and execution manager for autonomous agent tools."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._definitions: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        category: str = "general",
        is_reversible: bool = True,
        requires_approval: bool = False,
        approval_reason: Optional[str] = None,
    ):
        """Decorator to register a python function as an agent tool."""
        def decorator(func: Callable):
            sig = inspect.signature(func)
            doc = description or func.__doc__ or "No description provided."

            # Build JSON schema parameters
            properties: Dict[str, Any] = {}
            required: List[str] = []

            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue

                param_type = "string"
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation in (list, List[str]):
                    param_type = "array"
                elif param.annotation in (dict, Dict[str, Any]):
                    param_type = "object"

                properties[param_name] = {
                    "type": param_type,
                    "description": f"Parameter {param_name}",
                }

                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            parameters_schema = {
                "type": "object",
                "properties": properties,
                "required": required,
            }

            definition = ToolDefinition(
                name=name,
                description=doc.strip(),
                parameters_schema=parameters_schema,
                category=category,
                is_reversible=is_reversible,
                requires_approval=requires_approval,
                approval_reason=approval_reason,
            )

            self._tools[name] = func
            self._definitions[name] = definition
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)

    def get_definition(self, name: str) -> Optional[ToolDefinition]:
        return self._definitions.get(name)

    def list_definitions(self) -> List[ToolDefinition]:
        return list(self._definitions.values())

    def get_schemas_for_llm(self) -> List[Dict[str, Any]]:
        """Returns standard OpenAI / Gemini compatible function definitions."""
        schemas = []
        for defn in self._definitions.values():
            schemas.append({
                "name": defn.name,
                "description": defn.description,
                "parameters": defn.parameters_schema,
            })
        return schemas

    def execute(self, tool_call: ToolCall) -> ToolResult:
        """Executes a tool call with robust error handling and execution timing."""
        tool_name = tool_call.tool_name
        args = tool_call.arguments or {}

        if tool_name not in self._tools:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                output=f"Error: Tool '{tool_name}' is not recognized in the tool registry.",
                error=f"ToolNotFound: {tool_name}",
                evidence="",
                execution_time_ms=0.0,
            )

        func = self._tools[tool_name]
        start_time = time.perf_counter()

        try:
            # Execute underlying tool function
            result = func(**args)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            if isinstance(result, ToolResult):
                result.execution_time_ms = duration_ms
                return result

            if isinstance(result, dict):
                return ToolResult(
                    success=result.get("success", True),
                    tool_name=tool_name,
                    output=str(result.get("output", result.get("message", "Success"))),
                    data=result.get("data", result),
                    evidence=str(result.get("evidence", "")),
                    error=result.get("error"),
                    execution_time_ms=duration_ms,
                )

            return ToolResult(
                success=True,
                tool_name=tool_name,
                output=str(result),
                data={"result": result},
                evidence=f"Executed {tool_name} successfully",
                error=None,
                execution_time_ms=duration_ms,
            )

        except TypeError as te:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return ToolResult(
                success=False,
                tool_name=tool_name,
                output=f"Invalid arguments for tool '{tool_name}': {str(te)}",
                error=f"ArgumentValidationError: {str(te)}",
                evidence="",
                execution_time_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return ToolResult(
                success=False,
                tool_name=tool_name,
                output=f"Execution error in tool '{tool_name}': {str(exc)}",
                error=f"{type(exc).__name__}: {str(exc)}",
                evidence="",
                execution_time_ms=duration_ms,
            )


# Global default registry instance
default_registry = ToolRegistry()
