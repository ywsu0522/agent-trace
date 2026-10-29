"""Record complete Ollama HTTP bodies alongside application-level events."""

import time
from uuid import uuid4

from agent_trace.llm_ollama import OllamaClient


class RecordedClient(OllamaClient):
    def __init__(self, recorder, role, **kwargs):
        super().__init__(**kwargs)
        self.recorder = recorder
        self.role = role

    def _request(self, endpoint, payload=None):
        http_id = uuid4().hex
        self.recorder.emit('ollama_http_request', role=self.role, http_id=http_id, endpoint=endpoint, payload=payload)
        started = time.monotonic()
        try:
            result = super()._request(endpoint, payload)
        except BaseException as exc:
            self.recorder.emit('ollama_http_error', role=self.role, http_id=http_id,
                               error_type=type(exc).__name__, message=str(exc))
            raise
        self.recorder.emit('ollama_http_response', role=self.role, http_id=http_id,
                           seconds=round(time.monotonic() - started, 3), response=result)
        return result
