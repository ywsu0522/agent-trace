"""Shared data types for agent sessions and tools."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

LMCallable = Callable[[list[dict]], str]
Email = dict
DocWindow = dict


@dataclass
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class ParsedResponse:
    text: str
    tool_call: ToolCall | None = None
    error: str | None = None


@dataclass
class ToolResult:
    status: str
    content: str


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    fn: Callable[..., Any]
    read_only: bool = True


@dataclass
class AgentResult:
    text: str
    status: str
    transcript: list[dict]


@dataclass
class AgentConfig:
    max_turns: int = 12
    token_budget: int = 400_000
    aux_lm: Any = None
    user: Any = None
    mode: str = 'auto'
    deny_rules: tuple[str, ...] = ()
    workspace: Path | None = None
