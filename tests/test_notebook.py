"""The notebook must preserve evidence and distinguish execution from intent."""

import json
from pathlib import Path

import pytest

from agent_trace.notebook import normalize, evidence_paths, block


def fixture(tmp_path, *, probe=False, mismatch=False, missing_response=False):
    system = {'role': 'system', 'content': 'Tool: read_doc\nDescription: partial document\nParameters JSON Schema: {"type":"object"}'}
    user = {'role': 'user', 'content': 'Which date?'}
    messages = [system, user]
    completion = '<<<TOOL_CALL>>>\n{"name":"read_doc","args":{"doc_id":"spec"}}\n<<<END_TOOL_CALL>>>'
    events = []

    def emit(kind, **fields):
        events.append({'kind': kind, 'time': '2026-10-28T00:00:00+00:00', 'turn': 1, **fields})

    emit('model_request', role='agent', call_id='main', model='model', messages=messages)
    emit('ollama_http_request', role='agent', http_id='http', payload={'messages': [system] if mismatch else messages})
    emit('ollama_http_response', role='agent', http_id='http', response={'prompt_eval_count': 99})
    if not missing_response:
        emit('model_response', role='agent', call_id='main', content=completion)
    emit('parse_result', call_id='main', error=None, tool_call={'name': 'read_doc', 'args': {'doc_id': 'spec'}})
    emit('agent_event', event={'type': 'assistant', 'content': completion})
    if not probe:
        emit('agent_event', event={'type': 'tool_call', 'name': 'read_doc', 'args': {'doc_id': 'spec'}})
        emit('model_request', role='aux', call_id='aux', messages=[user])
        emit('model_response', role='aux', call_id='aux', content='aux answer')
        emit('agent_event', event={'type': 'tool_result', 'name': 'read_doc', 'status': 'ok', 'content': '{"text":"actual evidence"}'})
    (tmp_path / 'source.jsonl').write_text('\n'.join(json.dumps(e) for e in events), encoding='utf-8')
    (tmp_path / 'meta.json').write_text('{"settings":{"model":"model"}}', encoding='utf-8')
    return {'id': 'fixture', 'source': 'source.jsonl', 'metadata': 'meta.json', 'result': None, 'kind': 'probe' if probe else 'full'}


def test_associates_aux_and_late_tool_result_without_duplicate_assistant(tmp_path):
    record = normalize(fixture(tmp_path), tmp_path)
    assert record['main_count'] == 1 and record['aux_count'] == 1
    turn = record['turns'][0]
    assert turn['tools'][0]['content'] == '{"text":"actual evidence"}'
    assert turn['aux'][0]['completion'] == 'aux answer'
    assert turn['native_prompt_tokens'] == 99
    assert turn['messages'][-1]['content'] == 'Which date?'


def test_parsed_probe_is_not_reported_as_executed(tmp_path):
    record = normalize(fixture(tmp_path, probe=True), tmp_path)
    assert record['turns'][0]['decision'] == 'read_doc'
    assert record['tool_count'] == 0 and record['read_count'] == 0
    assert record['answer_match'] is None


def test_refuses_mismatched_application_and_http_prompt(tmp_path):
    with pytest.raises(ValueError, match='differs from recorded HTTP'):
        normalize(fixture(tmp_path, mismatch=True), tmp_path)


def test_refuses_incomplete_trace_instead_of_inventing_completion(tmp_path):
    with pytest.raises(ValueError, match='Missing response'):
        normalize(fixture(tmp_path, missing_response=True), tmp_path)


def test_refuses_mismatched_http_completion(tmp_path):
    entry = fixture(tmp_path)
    p = tmp_path / 'source.jsonl'
    events = [json.loads(line) for line in p.read_text().splitlines()]
    next(e for e in events if e['kind'] == 'ollama_http_response')['response']['message'] = {'content': 'different response'}
    p.write_text('\n'.join(json.dumps(e) for e in events), encoding='utf-8')
    with pytest.raises(ValueError, match='completion differs'):
        normalize(entry, tmp_path)


def test_portable_archive_fallback(tmp_path):
    archive = tmp_path / 'archive'
    (archive / 'evidence').mkdir(parents=True)
    (archive / 'metadata').mkdir()
    (archive / 'evidence/fixture.jsonl').write_text('evidence', encoding='utf-8')
    (archive / 'metadata/fixture.json').write_text('{}', encoding='utf-8')
    source, metadata, result = evidence_paths({'id': 'fixture', 'source': 'missing.jsonl', 'metadata': 'missing.json'}, tmp_path, archive)
    assert source.read_text() == 'evidence' and metadata.read_text() == '{}'
    assert result is None


def test_markdown_evidence_cannot_close_its_own_fence():
    value = '```json\noriginal evidence\n```'
    rendered = block(value)
    assert rendered.startswith('````text\n')
    assert value in rendered
