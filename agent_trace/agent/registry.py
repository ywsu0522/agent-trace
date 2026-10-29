"""
Structure of a tool, e.g., in general it has an execution method
「什麼是一個工具」的基本資料結構，其實是課程 types.py 裡的 ToolSpec: 包含名稱、描述、參數 schema、執行函式與是否唯讀。
registry 是管理這些工具的地方。
"""

from __future__ import annotations

from jsonschema import Draft202012Validator, ValidationError, SchemaError
from agent_trace.types import ToolResult, ToolSpec


class ToolRegistry:
    def __init__(self, tools: list[ToolSpec]):
        self.tools = {tool.name: tool for tool in tools}

    def schemas(self) -> list[dict]:
        return [
            {"name": tool.name, "description": tool.description,
             "parameters": tool.parameters}
            for tool in self.tools.values()
        ]

    def validate(self, name: str, args: dict) -> ToolResult | None:
        tool = self.tools.get(name)
        if tool is None:
            return ToolResult("unknown_tool", f"Unknown tool: {name}")
        try:
            Draft202012Validator.check_schema(tool.parameters)
            Draft202012Validator(tool.parameters).validate(args)
        except (ValidationError, SchemaError, TypeError, ValueError) as exc:
            return ToolResult("invalid_args", f"Invalid arguments for {name}: {exc}")
        return None

    def execute(self, name: str, args: dict) -> ToolResult:
        error = self.validate(name, args)
        if error is not None:
            return error
        try:
            value = self.tools[name].fn(**args)
            return ToolResult("ok", str(value))
        except Exception as exc:
            return ToolResult("tool_error", str(exc))
