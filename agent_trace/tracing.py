"""A single user-request tracing boundary for CLI and Python callers."""

from copy import deepcopy
import json
from pathlib import Path
import time

from agent_trace.agent.observability import ChatRecorder, ObservedLM
from agent_trace.traces import write_report


class TraceRun:
    """Write evidence while running; produce reports on success or exception.

    Use one instance per user request, even when reusing an AgentSession. Model
    and event-sink hooks are restored after send(). Auxiliary models must be
    wrapped with observe(aux, 'aux') before binding them to tool functions.
    """

    def __init__(self, out, *, question='', metadata=None, expected_answers=(),
                 kind='full', environment=None, document_result_budget=None, trace=False):
        self.out = Path(out).resolve()
        self.out.mkdir(parents=True, exist_ok=False)
        self.recorder = ChatRecorder(self.out, trace=trace, events_name='events.jsonl')
        self.metadata = deepcopy(metadata or {})
        self.context = {'id': self.out.name, 'question': question, 'kind': kind,
                        'environment': environment, 'expected_answers': [expected_answers] if isinstance(expected_answers, str) else list(expected_answers),
                        'document_result_budget': document_result_budget}
        self.result = None
        self.report = None
        self.entered = False
        self.sent = False

    def __enter__(self):
        if self.entered:
            raise RuntimeError('TraceRun instances cannot be reused')
        self.entered = True
        self.started = time.monotonic()
        self.recorder.emit('send_start', message=self.context['question'])
        self.save_metadata()
        return self

    def save_metadata(self):
        self.metadata['run_context'] = deepcopy(self.context)
        (self.out / 'metadata.json').write_text(json.dumps(self.metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def observe(self, lm, role='agent'):
        if isinstance(lm, ObservedLM) and lm.recorder is self.recorder:
            return lm
        return ObservedLM(lm, role, self.recorder)

    def _start(self, question):
        if not self.entered or self.sent:
            raise RuntimeError('Use one send/decision inside a TraceRun context')
        self.sent = True
        self.context['question'] = question
        self.save_metadata()

    def send(self, session, question):
        self._start(question)
        original_lm, original_sink = session.lm, session.event_sink

        def sink(event):
            self.recorder.agent_event(event)
            if original_sink is not None:
                original_sink(event)

        session.lm = self.observe(original_lm)
        session.event_sink = sink
        try:
            # Preserve the exact initial context for this user request, including
            # earlier conversation history when the session is reused.
            initial = deepcopy(session.messages) + [{'role': 'user', 'content': question}]
            (self.out / 'initial-request.json').write_text(json.dumps(initial, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            answer = session.send(question)
            self.result = {'text': answer.text, 'status': answer.status, 'error': None}
            return answer
        finally:
            session.lm, session.event_sink = original_lm, original_sink

    def decision(self, lm, messages):
        if self.context['kind'] == 'full':
            raise ValueError('Decision-only requests require kind=probe or replay')
        self._start(self.context['question'])
        (self.out / 'initial-request.json').write_text(json.dumps(messages, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        text = self.observe(lm)(deepcopy(messages))
        self.result = {'text': text, 'status': 'decision_only', 'error': None}
        return text

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            self.result = {'text': '', 'status': 'interrupted' if not isinstance(exc, Exception) else 'request_error',
                           'error': {'type': type(exc).__name__, 'message': str(exc)}}
        if self.result is None:
            self.result = {'text': '', 'status': 'incomplete', 'error': None}
        self.result.update(id=self.out.name, condition=self.context['environment'],
                           seconds=round(time.monotonic() - self.started, 3))
        expected = self.context['expected_answers']
        self.result['answer_match'] = (any(s in self.result['text'] for s in expected)
                                       if expected and self.context['kind'] == 'full' and self.result['status'] == 'done' else None)
        self.result['answer_match_method'] = 'exact substring; not a semantic judge' if expected else 'not evaluated'
        self.recorder.emit('send_complete', **self.result)
        self.save_metadata()
        # Persist a recovery result before rendering, so a renderer failure does
        # not destroy the recorded exception or original model/tool events.
        result_path = self.out / 'result.json'
        result_path.write_text(json.dumps(self.result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        try:
            self.report = write_report(self.recorder.events_path, metadata=self.metadata,
                                       result=self.result, context=self.context)
            self.result.update(agent_requests=self.report['main_count'], aux_requests=self.report['aux_count'],
                               tool_sequence=[t['name'] for turn in self.report['turns'] for t in turn['tools']],
                               tools_executed=any(t['status'] in ('ok', 'tool_error') for turn in self.report['turns'] for t in turn['tools']),
                               parse_error=next((t['parse']['error'] for t in reversed(self.report['turns'])
                                                 if t['parse'] and t['parse'].get('error')), None),
                               events='events.jsonl', report='trace.html')
        except Exception as report_error:
            self.result['report_error'] = {'type': type(report_error).__name__, 'message': str(report_error)}
            if exc is None:
                raise
        finally:
            result_path.write_text(json.dumps(self.result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return False
