"""Record a code-controlled pipeline without the agent tool-call protocol."""

import hashlib
import json
from threading import Lock
from pathlib import Path
import time

from agent_trace.agent.observability import ChatRecorder, ObservedLM
from agent_trace.recording import RecordedClient


def request_key(messages):
    return hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class ReplayOrLive:
    """Explicit exact-request reuse; cache events never impersonate HTTP calls."""
    def __init__(self, client, recorder, responses):
        self.client, self.recorder, self.responses = client, recorder, responses
        self.model = getattr(client, 'model', None)
        self.json_mode = getattr(client, 'json_mode', None)
        self.reused = self.fresh = 0
        self.lock = Lock()

    def request_json_mode(self, messages):
        method = getattr(self.client, 'request_json_mode', None)
        return method(messages) if method else self.json_mode

    def __call__(self, messages):
        key = request_key(messages)
        saved = self.responses.get(key)
        with self.lock:
            if saved is not None:
                self.reused += 1
            else:
                self.fresh += 1
        if saved is not None:
            self.recorder.emit('classification_replay', call_id=self.recorder.current_call.get(),
                               request_sha256=key, **{k: v for k, v in saved.items() if k != 'content'})
            return saved['content']
        return self.client(messages)


class PipelineRun:
    def __init__(self, out, *, settings, lm=None, responses=None):
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=False)
        self.recorder = ChatRecorder(self.out, events_name='events.jsonl')
        self.settings = settings
        client = lm if lm is not None else RecordedClient(self.recorder, 'pipeline', **settings)
        # A pipeline completion is data, not an agent tool-call decision.
        self.client = ReplayOrLive(client, self.recorder, responses or {})
        self.lm = ObservedLM(self.client, 'pipeline', self.recorder)
        self.output = None

    def save(self, name, value):
        (self.out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def __enter__(self):
        self.started = time.monotonic()
        self.save('settings.json', self.settings)
        self.recorder.emit('pipeline_start')
        return self

    def stage(self, name, **data):
        self.recorder.emit('pipeline_stage', name=name, **data)
        self.save(name + '.json', data)

    def finish(self, output):
        self.output = output

    def __exit__(self, kind, error, tb):
        result = {'output': self.output, 'reused_classifications': self.client.reused,
                  'fresh_model_calls': self.client.fresh, 'seconds': round(time.monotonic() - self.started, 3),
                  'error': {'type': type(error).__name__, 'message': str(error)} if error else None}
        self.save('output.json', result)
        self.recorder.emit('pipeline_complete', **result)
        return False
