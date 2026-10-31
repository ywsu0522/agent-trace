"""Thin Ollama chat adapter for the HW1-inspired local RAG experiment.

From repository root:
    uv run python -m agent_trace.llm_ollama --check
    uv run python -m agent_trace.llm_ollama --check --model qwen3.5:4b-q4_K_M

Only the Python standard library is required. `OllamaClient` is callable:
    text = OllamaClient()([{'role': 'user', 'content': 'Hello'}])

JSON output is enabled by default for multi-hop QA. Use json_mode=False for
plain-text answers and the marker-based tool protocol used by agent_loop.
"""

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaClient:
    def __init__(
        self,
        model: str = "qwen3.5:4b-q4_K_M",
        base_url: str = "http://127.0.0.1:11434",
        timeout: int = 180,
        *,
        json_mode: bool = True,
        temperature: float = 0,
        num_ctx: int = 8192,
        think: bool = False,
        num_batch: int | None = None,
        num_gpu: int | None = None,
        task_options: dict | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.json_mode = json_mode
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.think = think
        self.num_batch = num_batch
        self.num_gpu = num_gpu
        self.task_options = task_options or {}

    def _request(self, endpoint: str, payload: dict | None = None) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = Request(
            self.base_url + endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST" if payload is not None else "GET",
        )
        try:
            with urlopen(req, timeout=self.timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Ollama HTTP {exc.code}: {detail}. Check `ollama list` and --model."
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Start the Ollama Windows app or run `ollama serve` in another PowerShell window. "
                f"Original error: {exc}"
            ) from exc

    def _task_options(self, messages):
        if not self.task_options or not messages:
            return {}
        try:
            value = json.loads(messages[-1]['content'])
            return self.task_options.get(value.get('task'), {}) if isinstance(value, dict) else {}
        except (ValueError, TypeError, KeyError):
            return {}

    def request_json_mode(self, messages):
        return self._task_options(messages).get('json_mode', self.json_mode)

    def __call__(self, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.think,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
        }
        if self.num_gpu is not None:
            payload['options']['num_gpu'] = self.num_gpu
        if self.num_batch is not None:
            payload['options']['num_batch'] = self.num_batch
        overrides = self._task_options(messages)
        if 'num_predict' in overrides:
            payload['options']['num_predict'] = overrides['num_predict']
        if self.request_json_mode(messages):
            payload["format"] = overrides.get("format", "json")
        result = self._request("/api/chat", payload)
        content = result.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(
                "Ollama returned empty text. Check /api/chat response and model thinking support."
            )
        return content

    def check(self) -> None:
        version = self._request("/api/version")
        tags = self._request("/api/tags")
        models = [m.get("name") for m in tags.get("models", [])]
        print("Ollama version:", version.get("version", version))
        print("Installed models:", models)
        if self.model not in models:
            raise RuntimeError(
                f"Model {self.model!r} not present. Run `ollama pull {self.model}` "
                "or specify an exact name from `ollama list`."
            )
        reply = self([
            {"role": "system", "content": "Reply with a JSON object only."},
            {"role": "user", "content": 'Reply with exactly {"status":"ok"}.'},
        ])
        print("Model response:", reply)
        obj = json.loads(reply)
        if not isinstance(obj, dict) or obj.get("status") != "ok":
            raise RuntimeError("Expected JSON with status='ok'. Inspect model response above.")
        print("PASS: Ollama HTTP API and JSON reply are working.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the local Ollama chat API")
    parser.add_argument("--check", action="store_true", help="Run a server/model/JSON smoke test")
    parser.add_argument("--model", default="qwen3.5:4b-q4_K_M")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    if not args.check:
        parser.error("Pass --check to test your Ollama server and model")
    OllamaClient(model=args.model, base_url=args.base_url).check()


if __name__ == "__main__":
    main()
