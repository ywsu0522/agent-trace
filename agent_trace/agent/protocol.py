"""Text-based tool-call protocol shared by local and course agent entry points."""
"""
render_tools() → 把工具與格式規則放進 prompt
lm(prompt)     → LLM 產生文字
parse_response(reply) → 解析成 ToolCall 或回報錯誤
"""
# from __future__ import annotations

import json
import re

from agent_trace.types import ParsedResponse, ToolCall

START = "<<<TOOL_CALL>>>"
END = "<<<END_TOOL_CALL>>>"
_START_RE = re.compile(r"^<<<TOOL_CALL>>>\r?$", re.MULTILINE)
_END_RE = re.compile(r"^<<<END_TOOL_CALL>>>\r?$", re.MULTILINE)


def render_tools(schemas: list[dict]) -> str:
    lines = [
        "You may use the tools below. Call a tool only when needed.",
        "To call a tool, write exactly ONE call in this format, with each marker on its own line:",
        START,
        '{"name":"tool_name","args":{"argument_name":"value"}}',
        END,
        'Replace "tool_name" with the exact name after a "Tool:" label below.',
        'Replace {"argument_name":"value"} with arguments matching that tool\'s Parameters JSON Schema: use its "properties" names as keys, include "required" keys, and match value types.',
        'Keep the outer keys "name" and "args". The schema describes "args" only; put all tool parameters inside "args".',
        "If the task is finished, reply in plain text WITHOUT tool markers.",
        "After a tool result is given, decide whether to call another tool or answer.",
        "Available tools:",
    ]
    for schema in schemas:
        lines.append(f"Tool: {schema['name']}")
        lines.append(f"Description: {schema['description']}")
        lines.append("Parameters JSON Schema: " + json.dumps(
            schema["parameters"], ensure_ascii=False
        ))

    return "\n".join(lines)


def format_tool_call(text: str, call: ToolCall) -> str:
    payload = json.dumps(
        {"name": call.name, "args": call.args},
        ensure_ascii=False, separators=(",", ":"),
    )
    prefix = text.strip()
    return (prefix + "\n" if prefix else "") + START + "\n" + payload + "\n" + END


def parse_response(reply: str) -> ParsedResponse:
    """Never execute tools here; return parsed text, optional call, and error."""
    if not isinstance(reply, str):
        return ParsedResponse("", None, "Reply must be a string")

    starts = list(_START_RE.finditer(reply))
    if not starts:
        return ParsedResponse(reply.strip(), None, None)
    if len(starts) != 1:
        return ParsedResponse(reply.strip(), None, "Multiple tool calls in one reply")

    start = starts[0]
    ends = [m for m in _END_RE.finditer(reply) if m.start() > start.end()]
    if len(ends) != 1:
        return ParsedResponse(reply[:start.start()].strip(), None, "Incomplete tool call")

    end = ends[0]
    text = reply[:start.start()].strip()
    if reply[end.end():].strip():
        return ParsedResponse(text, None, "Unexpected text after tool call")

    try:
        obj = json.loads(reply[start.end():end.start()].strip())
        if not isinstance(obj, dict):
            raise ValueError("Tool call must be a JSON object")
        name, args = obj.get("name"), obj.get("args")
        if not isinstance(name, str) or not isinstance(args, dict):
            raise ValueError(
                'Tool call requires string "name" and object "args"; '
                'nest all tool parameters inside "args", not beside "name"'
            )
        return ParsedResponse(text, ToolCall(name, args), None)
    except (ValueError, TypeError) as exc:
        return ParsedResponse(text, None, f"Malformed tool call: {exc}")
