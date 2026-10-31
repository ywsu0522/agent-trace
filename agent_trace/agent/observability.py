"""Local chat diagnostics, separate from the course transcript and model context."""

from datetime import datetime, timezone
from copy import deepcopy
from contextvars import ContextVar
import json
from pathlib import Path
from threading import Lock
from uuid import uuid4

from agent_trace.agent.protocol import parse_response
from agent_trace.tokens import count_message_tokens


class ChatRecorder:
    """Append full events immediately; save conversation snapshots separately."""

    def __init__(self, out: Path, trace: bool = False, *, trace_full: bool = False, events_name: str | None = None):
        out.mkdir(parents=True, exist_ok=True)
        self.started = datetime.now(timezone.utc).isoformat()
        stem = "ollama-chat-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        self.events_path = out / (events_name or stem + ".jsonl")
        self.summary_path = out / (stem + ".json")
        self.events_path.touch(exist_ok=False)
        self.trace = trace or trace_full
        self.trace_full = trace_full
        self.lock = Lock()
        self.send_id = 0
        self.turn = 0
        self.aux_request = 0
        self.tool = None
        self.calls: dict[str, dict] = {}
        self.previous_messages: dict[str, list[dict]] = {}
        self.shown_system_prompts: set[str] = set()
        self.current_call = ContextVar('trace_model_call', default=None)

    def emit(self, kind: str, **data) -> None:
        # Digest's auxiliary model calls may arrive concurrently.
        with self.lock:
            if kind.startswith('ollama_http_') and self.current_call.get():
                data.setdefault('call_id', self.current_call.get())
            if kind == "send_start":
                self.send_id += 1
                self.turn = self.aux_request = 0
                self.tool = None
            if kind == "model_request":
                if data["role"] == "agent":
                    self.turn += 1
                    self.aux_request = 0
                    self.tool = None
                else:
                    self.aux_request += 1
                self.calls[data["call_id"]] = {
                    "send_id": self.send_id, "turn": self.turn,
                    "aux_request": self.aux_request if data["role"] != "agent" else None,
                    "tool": self.tool,
                }
            context = self.calls.get(data.get("call_id"), {
                "send_id": self.send_id, "turn": self.turn,
            })
            if kind == "agent_event" and data["event"]["type"] == "tool_call":
                self.tool = data["event"]["name"]
            record = {"time": datetime.now(timezone.utc).isoformat(), "kind": kind,
                      **context, **deepcopy(data)}
            with self.events_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            if self.trace:
                self._show(record)

    def _preview(self, value, limit: int = 500) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        if self.trace_full:
            return text
        text = " ".join(text.split())
        if len(text) > limit:
            return text[:limit] + f" ... [{len(text) - limit} chars omitted; full text in JSONL]"
        return text

    @staticmethod
    def _label(record: dict) -> str:
        label = f"S{record['send_id']}"
        if record["turn"]:
            label += f" T{record['turn']}"
        if record.get("aux_request") is not None:
            label += f" AUX{record['aux_request']}"
        return label

    def _show(self, record: dict) -> None:
        """Bounded console view; the JSONL above always contains the exact payload."""
        kind = record["kind"]
        label = self._label(record)

        def line(stage, value):
            print(f"[{label}] {stage}: {self._preview(value)}", flush=True)

        if kind == "send_start":
            print(f"\n{'=' * 16} SEND {self.send_id} {'=' * 16}", flush=True)
        elif kind == "model_request":
            role = record["role"]
            if role == "agent":
                title = f"SEND {self.send_id} | TURN {self.turn} | AGENT"
                print(f"\n{'=' * 12} {title} {'=' * 12}", flush=True)
            else:
                title = (f"SEND {self.send_id} | TURN {self.turn} | "
                         f"AUX REQUEST {record['aux_request']} | tool={record['tool'] or '-'}")
                print(f"\n--- {title} ---", flush=True)
            messages = record["messages"]
            line("REQUEST", f"model={record['model']} | messages={len(messages)} | "
                 f"prompt_tokens~{count_message_tokens(messages)} | json_mode={record['json_mode']}")
            if self.trace_full:
                for i, message in enumerate(messages):
                    print(f"[{label}] PROMPT {i} | role={message['role']}\n{message['content']}", flush=True)
            else:
                previous = self.previous_messages.get(role, [])
                common = 0
                for old, new in zip(previous, messages):
                    if old != new:
                        break
                    common += 1
                if common:
                    line("CONTEXT", f"{common} unchanged prefix messages hidden (still sent to model)")
                changed = messages[common:]
                if len(changed) > 3:
                    line("CONTEXT", f"{len(changed) - 3} additional messages hidden; see JSONL")
                for i, message in enumerate(changed[-3:], start=len(messages) - min(len(changed), 3)):
                    content = message["content"]
                    if message["role"] == "system":
                        if content in self.shown_system_prompts:
                            content = "previously shown system prompt hidden (still sent to model)"
                        else:
                            self.shown_system_prompts.add(content)
                    line(f"PROMPT {i} ({message['role']})", content)
            self.previous_messages[role] = deepcopy(messages)
        elif kind == "model_response":
            line("RESPONSE", record["content"])
        elif kind == "model_error":
            line("MODEL ERROR", f"{record['error_type']}: {record['message']}")
        elif kind == "parse_result":
            if record["error"]:
                line("PARSE ERROR", record["error"])
            elif record["tool_call"] is None:
                line("PARSE", "final answer (no tool call)")
            else:
                line("PARSE", f"tool call -> {record['tool_call']['name']}")
        elif kind == "agent_event":
            event = record["event"]
            # Assistant content is already shown as RESPONSE.
            if event["type"] == "user":
                line("USER" if not self.turn else "USER (steering)", event["content"])
            elif event["type"] == "tool_call":
                line("TOOL CALL", f"{event['name']}({json.dumps(event['args'], ensure_ascii=False)})")
            elif event["type"] == "tool_result":
                line("TOOL RESULT", f"{event['name']} | status={event['status']} | {event['content']}")
            elif event["type"] == "error":
                line("ERROR", event["content"])
        elif kind == "send_complete":
            line("SEND COMPLETE", record["status"])
        elif kind == "session_error":
            line("SESSION ERROR", f"{record['type']}: {record['message']}")

    def agent_event(self, event: dict) -> None:
        # tool_call is emitted before validation/approval/execution; tool_result after.
        self.emit("agent_event", event=event)

    def save(self, session, turns: list[dict], settings: dict, error: dict | None) -> None:
        self.summary_path.write_text(json.dumps({
            "started": self.started,
            "settings": settings,
            "turns": turns,
            "transcript": session.transcript,
            "diagnostics_file": self.events_path.name,
            "error": error,
        }, ensure_ascii=False, indent=2), encoding="utf-8")


class ObservedLM:
    """Record exact inputs, outputs and failures without changing model requests."""

    def __init__(self, lm, role: str, recorder: ChatRecorder):
        self.lm = lm
        self.role = role
        self.recorder = recorder

    def __call__(self, messages):
        call_id = uuid4().hex
        self.recorder.emit("model_request", role=self.role, call_id=call_id,
                           model=getattr(self.lm, 'model', None), json_mode=(self.lm.request_json_mode(messages) if hasattr(self.lm, 'request_json_mode')
                                      else getattr(self.lm, 'json_mode', None)), messages=messages)
        token = self.recorder.current_call.set(call_id)
        try:
            reply = self.lm(messages)
        except BaseException as exc:
            self.recorder.emit("model_error", role=self.role, call_id=call_id,
                               error_type=type(exc).__name__, message=str(exc))
            raise
        finally:
            self.recorder.current_call.reset(token)
        self.recorder.emit("model_response", role=self.role, call_id=call_id, content=reply)
        if self.role == "agent":
            parsed = parse_response(reply)
            call = parsed.tool_call
            self.recorder.emit("parse_result", call_id=call_id, error=parsed.error,
                               tool_call=None if call is None else {"name": call.name, "args": call.args})
        return reply
