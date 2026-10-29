"""Observable invariants: real archived paths, interruption, concurrency and safe views."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading

import pytest

from agent_trace.agent.protocol import format_tool_call
from agent_trace.agent.registry import ToolRegistry
from agent_trace.agent.session import AgentSession
from agent_trace.cli import main
from agent_trace.llm_ollama import OllamaClient
from agent_trace.paths import asset_root
from agent_trace.recording import RecordedClient
from agent_trace.reports import report_path
from agent_trace.traces import write_report
from agent_trace.tracing import TraceRun
from agent_trace.types import AgentConfig, ToolCall, ToolSpec

ROOT = asset_root()
BATCH = ROOT / 'studies/baseline-20/record'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def archived(case, tmp_path):
    source = BATCH / case / 'events.jsonl'
    trace = report_path(BATCH / case, tmp_path / case)
    return source, trace


def test_real_success_has_continuation_and_exact_full_evidence(tmp_path):
    source, trace = archived('d09', tmp_path)
    assert (trace['main_count'], trace['aux_count'], trace['answer_match']) == (5, 0, True)
    windows = [tool for turn in trace['turns'] for tool in turn['tools'] if tool.get('window')]
    assert [(w['window']['start_line'], w['window']['end_line']) for w in windows] == [(1, 88), (89, 158)]
    assert '接續前一次視窗。' in windows[1]['annotations']
    assert all(w['next_request_contains_result'] is True for w in windows)
    assert (tmp_path / 'd09/events.jsonl').read_bytes() == source.read_bytes()
    events = [json.loads(line) for line in source.read_text(encoding='utf-8').splitlines()]
    requests = [e['messages'] for e in events if e['kind'] == 'model_request' and e['role'] == 'agent']
    assert [t['messages'] for t in trace['turns']] == requests


def test_real_repeated_window_and_budget_are_separate_from_answer(tmp_path):
    _, trace = archived('d07', tmp_path)
    repeated = [note for turn in trace['turns'] for tool in turn['tools'] for note in tool['annotations']
                if note == '重複讀取相同文件視窗。']
    assert len(repeated) == 2
    assert trace['answer_match'] is True and trace['document_result_tokens_estimate'] == 6790
    assert trace['evidence_support'] == 'not_reviewed'


def test_real_auxiliary_requests_stay_inside_their_main_turn(tmp_path):
    _, trace = archived('d01', tmp_path)
    assert (trace['main_count'], trace['aux_count']) == (3, 4)
    assert len(trace['turns'][0]['aux']) == 4
    assert all(t['aux'] == [] for t in trace['turns'][1:])


def test_imported_report_is_portable_without_original_companion_files(tmp_path):
    _, original = archived('d09', tmp_path)
    rebuilt = report_path(tmp_path / 'd09', tmp_path / 'portable')
    for key in ('question', 'status', 'answer_match', 'expected_answers', 'raw_sha256', 'final'):
        assert rebuilt[key] == original[key]


def registry():
    return ToolRegistry([ToolSpec('echo', 'Return text.', {'type': 'object', 'properties': {'text': {'type': 'string'}},
                         'required': ['text']}, lambda text: text)])


def test_library_reports_each_send_and_restores_session_hooks(tmp_path):
    reply = format_tool_call('', ToolCall('echo', {'text': 'hello'}))
    replies = iter([reply, 'hello', reply, 'hello'])
    lm = lambda messages: next(replies)
    session = AgentSession(lm, registry(), AgentConfig(max_turns=2))
    observed = []
    sink = lambda event: observed.append(deepcopy(event))
    session.event_sink = sink
    for i in range(2):
        with TraceRun(tmp_path / str(i), expected_answers=['hello']) as run:
            result = run.send(session, f'Question {i}')
            assert result.status == 'done'
        trace = read(tmp_path / str(i) / 'trace.json')
        assert trace['main_count'] == 2 and trace['question'] == f'Question {i}'
        assert trace['answer_match'] is True
        assert session.lm is lm and session.event_sink is sink
    first = read(tmp_path / '0/trace.json')['turns'][0]['messages']
    second = read(tmp_path / '1/trace.json')['turns'][0]['messages']
    assert len(second) > len(first) and len(observed) == 10
    rebuilt = report_path(tmp_path / '1', tmp_path / 'rebuilt')
    assert rebuilt['question'] == 'Question 1' and rebuilt['expected_answers'] == ['hello']


@pytest.mark.parametrize('exception,status', [(RuntimeError('offline'), 'request_error'), (KeyboardInterrupt(), 'interrupted')])
def test_error_and_interrupt_still_finalize_reports(tmp_path, exception, status):
    def broken(messages):
        raise exception

    session = AgentSession(broken, registry())
    with pytest.raises(type(exception)):
        with TraceRun(tmp_path / 'broken', question='question') as run:
            run.send(session, 'question')
    trace = read(tmp_path / 'broken/trace.json')
    assert trace['status'] == status and trace['main_count'] == 1
    assert trace['turns'][0]['completion'] is None
    assert trace['turns'][0]['error']['type'] == type(exception).__name__
    assert (tmp_path / 'broken/trace.html').is_file()
    assert session.lm is broken and session.event_sink is None


def test_unfinished_jsonl_stays_incomplete_without_reparsing(tmp_path):
    source = tmp_path / 'partial.jsonl'
    event = {'kind': 'model_request', 'role': 'agent', 'call_id': 'missing',
             'messages': [{'role': 'user', 'content': 'Question'}]}
    source.write_text(json.dumps(event) + '\n{"kind":', encoding='utf-8')
    trace = write_report(source, tmp_path / 'report')
    assert trace['turns'][0]['decision'] == 'incomplete_request'
    assert trace['turns'][0]['parse'] is None and trace['status'] == 'incomplete'
    assert trace['warnings'] and trace['turns'][0]['completion'] is None


def test_probe_records_intent_without_claiming_tool_execution(tmp_path):
    reply = format_tool_call('', ToolCall('echo', {'text': 'hello'}))
    with TraceRun(tmp_path / 'probe', kind='probe') as run:
        run.decision(lambda messages: reply, [{'role': 'user', 'content': 'hello'}])
    trace = read(tmp_path / 'probe/trace.json')
    assert trace['tool_attempts'] == 0 and trace['turns'][0]['decision'] == 'echo'
    assert trace['answer_match'] is None and run.result['tools_executed'] is False
    assert any('不執行工具' in n for n in trace['turns'][0]['annotations'])


def test_raw_document_html_cannot_be_executed_in_report(tmp_path):
    malicious = '</pre><script>globalThis.pwned=true</script><img src="https://invalid.test/x">'
    with TraceRun(tmp_path / 'html', kind='probe', question=malicious) as run:
        run.decision(lambda messages: malicious, [{'role': 'user', 'content': malicious}])
    html = (tmp_path / 'html/trace.html').read_text(encoding='utf-8')
    assert '<script>' not in html and '<img ' not in html
    assert '&lt;script&gt;' in html
    assert read(tmp_path / 'html/trace.json')['turns'][0]['completion'] == malicious


def test_concurrent_aux_http_is_correlated_by_call_id(tmp_path, monkeypatch):
    barrier = threading.Barrier(2)

    def http(self, endpoint, payload=None):
        barrier.wait(timeout=5)
        return {'message': {'content': payload['messages'][0]['content']}}

    monkeypatch.setattr(OllamaClient, '_request', http)
    with TraceRun(tmp_path / 'concurrent') as run:
        aux = run.observe(RecordedClient(run.recorder, 'aux'), 'aux')

        def parallel():
            with ThreadPoolExecutor(max_workers=2) as pool:
                return list(pool.map(lambda text: aux([{'role': 'user', 'content': text}]), ['one', 'two']))

        tools = ToolRegistry([ToolSpec('parallel', 'Parallel aux.', {'type': 'object'}, parallel)])
        replies = iter([format_tool_call('', ToolCall('parallel')), 'done'])
        run.send(AgentSession(lambda messages: next(replies), tools), 'question')
    trace = read(tmp_path / 'concurrent/trace.json')
    assert trace['aux_count'] == 2 and trace['main_count'] == 2
    for aux_record in trace['turns'][0]['aux']:
        assert aux_record['http_request']['messages'] == aux_record['messages']
        assert aux_record['http_response']['message']['content'] == aux_record['completion']


def test_custom_question_is_unscored_and_task_can_run_without_study_files(tmp_path, monkeypatch, capsys):
    import shutil
    import agent_trace.execution as execution
    shutil.copytree(ROOT / 'configs', tmp_path / 'configs')
    monkeypatch.setattr(execution, 'asset_root', lambda: tmp_path)
    assert main(['run', 'An unrelated question?', '--dry-run']) == 0
    config = json.loads(capsys.readouterr().out)
    assert config['question'] == 'An unrelated question?' and config['expected_answers'] == []
    assert main(['run', '--task', 'd09', '--dry-run']) == 0
    config = json.loads(capsys.readouterr().out)
    assert config['task'] == 'd09' and config['expected_answers']
    assert not (tmp_path / 'studies').exists()


def test_cli_provider_startup_failure_leaves_readable_report(tmp_path, monkeypatch):
    monkeypatch.setattr(OllamaClient, '_request', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('provider unavailable')))
    out = tmp_path / 'startup-error'
    assert main(['run', '--probe', '--out', str(out)]) == 1
    assert read(out / 'trace.json')['main_count'] == 0
    assert read(out / 'result.json')['status'] == 'request_error'
    assert (out / 'trace.html').is_file()


def test_saved_request_replay_does_not_inherit_default_task_answer(tmp_path, capsys):
    request = tmp_path / 'request.json'
    request.write_text(json.dumps([{'role': 'system', 'content': 'old system'},
                                   {'role': 'user', 'content': 'A different question'}]), encoding='utf-8')
    assert main(['replay', '--request', str(request), '--dry-run']) == 0
    config = json.loads(capsys.readouterr().out)
    assert config['question'] == 'A different question'
    assert config['task'] is None and config['expected_answers'] == []


def test_docs_only_catalogue_does_not_require_email_corpus(tmp_path, monkeypatch):
    from agent_trace.agent.protocol import render_tools
    from agent_trace.runtime import catalogue_from_system
    original = (ROOT / 'configs/prompts/E4.system.txt').read_text(encoding='utf-8')
    schemas = [s for s in catalogue_from_system(original) if s['name'] == 'read_doc']
    system = tmp_path / 'docs-only.txt'
    system.write_text(render_tools(schemas), encoding='utf-8')
    replies = iter([format_tool_call('', ToolCall('read_doc', {'doc_id': 'gridlens-api-spec'})), '600'])

    def request(self, endpoint, payload=None):
        if endpoint == '/api/version': return {'version': 'test'}
        if endpoint == '/api/tags': return {'models': [{'name': self.model}]}
        return {'message': {'content': next(replies)}}

    monkeypatch.setattr(OllamaClient, '_request', request)
    out = tmp_path / 'docs-only'
    assert main(['run', 'What is the API rate limit?', '--system', str(system), '--emails', str(tmp_path / 'missing'), '--out', str(out)]) == 0
    trace = read(out / 'trace.json')
    assert trace['answer_match'] is None and trace['main_count'] == 2
    assert trace['turns'][0]['tools'][0]['next_request_contains_result'] is True
