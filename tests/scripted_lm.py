"""Provider-free HW1 scripted model, ported with agent-trace ToolCall types."""

from __future__ import annotations

import copy
from collections.abc import Sequence, Callable
from typing import Any

Message = dict
VALID_ROLES = {"system", "user", "assistant"}

class ScriptExhausted(RuntimeError):
    """Raised when a ScriptedLM is called more times than its script allows."""


def _validate_messages(messages: Sequence[Message]) -> None:
    if not isinstance(messages, (list, tuple)) or not messages:
        raise ValueError("messages must be a non-empty list of {'role', 'content'} dicts")
    for m in messages:
        if not isinstance(m, dict) or set(m) != {"role", "content"}:
            raise ValueError(
                f"each message must be a dict with exactly the keys 'role' and 'content', got {m!r}"
            )
        if m["role"] not in VALID_ROLES:
            raise ValueError(f"role must be one of {VALID_ROLES}, got {m['role']!r}")
        if not isinstance(m["content"], str):
            raise ValueError("message content must be a string")


class ScriptedLM:
    """A fake LM that replays a fixed script. Used by the deterministic tests.

    Each script entry is one model reply, given as one of:

    * a string, returned as is;
    * a dict ``{"text": str, "tool_call": {"name": str, "args": dict}}``,
      rendered to a string by ``formatter(text, ToolCall)``. The tests pass
      your ``run_format_tool_call`` adapter as the formatter, so scripted
      tool calls arrive in your own format;
    * a callable ``f(messages) -> str``.

    Every call's messages are recorded in ``.calls`` so tests can inspect
    exactly what your code sent to the model. When the script runs out the
    LM raises ``ScriptExhausted``, unless ``repeat_last=True``, in which case
    the last entry is replayed forever.
    """

    model = "scripted"

    def __init__(
        self,
        script: Sequence[Any],
        *,
        formatter: Callable[[str, Any], str] | None = None,
        repeat_last: bool = False,
    ) -> None:
        self.script = list(script)
        self.formatter = formatter
        self.repeat_last = repeat_last
        self.calls: list[list[Message]] = []
        self.replies: list[str] = []

    def __call__(self, messages: Sequence[Message]) -> str:
        _validate_messages(messages)
        index = len(self.calls)
        self.calls.append(copy.deepcopy(list(messages)))
        if index >= len(self.script):
            if not (self.repeat_last and self.script):
                raise ScriptExhausted(
                    f"ScriptedLM was called {index + 1} times but the script has "
                    f"{len(self.script)} entries. Your code made a model call the test "
                    "did not expect."
                )
            index = len(self.script) - 1
        entry = self.script[index]
        if callable(entry):
            reply = entry(self.calls[-1])
        elif isinstance(entry, dict):
            reply = self._render(entry)
        else:
            reply = str(entry)
        self.replies.append(reply)
        return reply

    @property
    def remaining(self) -> int:
        return max(len(self.script) - len(self.calls), 0)

    def _render(self, entry: dict) -> str:
        text = entry.get("text", "")
        call = entry.get("tool_call")
        if call is None:
            return text
        if self.formatter is None:
            raise RuntimeError("ScriptedLM needs a formatter to render scripted tool calls")
        from agent_trace.types import ToolCall

        return self.formatter(text, ToolCall(name=call["name"], args=dict(call.get("args", {}))))

    def usage(self) -> dict:
        return {"model": "scripted", "calls": len(self.calls), "cost_usd": 0.0}
