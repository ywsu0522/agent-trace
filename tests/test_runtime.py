"""Research invariants, archived-payload replay, and independent CLI checks."""

import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from agent_trace.cli import main
from agent_trace.data import Corpus, prepare_email
from agent_trace.llm_ollama import OllamaClient
from agent_trace.paths import asset_root
from agent_trace.runtime import build_registry

ROOT = asset_root()
STUDY = ROOT / 'studies/d06'
MODEL = 'qwen3.5:4b-q4_K_M'


def archived(run_id):
    path = STUDY / 'record/evidence' / f'{run_id}.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def replay_http(monkeypatch, events):
    pending = []
    for event in events:
        if event['kind'] == 'ollama_http_request':
            response = next(e['response'] for e in events if e['kind'] == 'ollama_http_response' and e['http_id'] == event['http_id'])
            pending.append((event['payload'], response))

    def request(self, endpoint, payload=None):
        if endpoint == '/api/version':
            return {'version': 'offline-test'}
        if endpoint == '/api/tags':
            return {'models': [{'name': MODEL, 'digest': 'offline-test'}]}
        assert endpoint == '/api/chat'
        expected, response = pending.pop(0)
        assert payload == expected, 'Refactored runtime changed the archived request or tool feedback'
        return deepcopy(response)

    monkeypatch.setattr(OllamaClient, '_request', request)
    return pending


def test_no_official_runtime_or_test_helper_imports():
    import agent_trace
    package = Path(agent_trace.__file__).parent
    for path in package.rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith(('cs329z_hw1', 'tests', 'scripts'))
            if isinstance(node, ast.Import):
                assert not any(n.name.startswith(('cs329z_hw1', 'tests', 'scripts')) for n in node.names)
    assert importlib.util.find_spec('cs329z_hw1') is None


def test_document_pages_preserve_historical_boundaries(tmp_path):
    system = (STUDY / 'record/environments/E4.system.txt').read_text(encoding='utf-8')
    registry = build_registry(lambda messages: 'unused', Corpus(ROOT / 'datasets/docs', tmp_path / 'absent'), system)
    first = json.loads(registry.execute('read_doc', {'doc_id': 'gridlens-api-spec'}).content)
    second = json.loads(registry.execute('read_doc', {'doc_id': 'gridlens-api-spec', 'start_line': 90}).content)
    assert (first['start_line'], first['end_line'], first['total_lines']) == (1, 89, 131)
    assert '2026-12-31' not in first['text'] and '2026-12-31' in second['text']


def test_search_results_equal_all_archived_document_searches(tmp_path):
    corpus = Corpus(ROOT / 'datasets/docs', tmp_path / 'absent')
    manifest = json.loads((STUDY / 'manifest.json').read_text(encoding='utf-8'))
    verified = 0
    for entry in manifest['runs']:
        events = archived(entry['id'])
        system = next(e['messages'][0]['content'] for e in events if e['kind'] == 'model_request' and e['role'] == 'agent')
        registry = build_registry(lambda messages: 'unused', corpus, system)
        args = None
        for event in events:
            if event['kind'] != 'agent_event':
                continue
            item = event['event']
            if item['type'] == 'tool_call' and item['name'] == 'search_docs':
                args = item['args']
            if item['type'] == 'tool_result' and item['name'] == 'search_docs':
                assert registry.execute('search_docs', args).content == item['content']
                verified += 1
    assert verified > 10


def test_full_document_run_replays_identical_requests_and_tool_feedback(tmp_path, monkeypatch):
    pending = replay_http(monkeypatch, archived('protocol-after'))
    emails = tmp_path / 'empty.jsonl'
    emails.touch()
    output = tmp_path / 'full-run'
    assert main(['run', '--env', 'E3', '--emails', str(emails), '--out', str(output)]) == 0
    result = json.loads((output / 'result.json').read_text())
    assert result['agent_requests'] == 6 and result['aux_requests'] == 0
    assert result['tool_sequence'][-2:] == ['read_doc', 'read_doc']
    assert result['status'] == 'done' and result['answer_match'] is False
    assert not pending


@pytest.mark.parametrize('run_id,environment', [('paging-after', 'E4'), ('a-full', 'E0')])
def test_full_email_corpus_runs_replay_identical_requests(tmp_path, monkeypatch, run_id, environment):
    emails = ROOT / '.cache/emails.jsonl'
    if not emails.exists():
        pytest.skip('Optional historical email corpus: run prepare-data first')
    pending = replay_http(monkeypatch, archived(run_id))
    output = tmp_path / 'run'
    assert main(['run', '--env', environment, '--emails', str(emails), '--out', str(output)]) == 0
    assert not pending
    result = json.loads((output / 'result.json').read_text())
    assert result['agent_requests'] == 6
    assert result['aux_requests'] == (4 if run_id == 'a-full' else 0)


def test_decision_replay_changes_only_system_and_executes_no_tool(tmp_path, monkeypatch):
    history = json.loads((STUDY / 'record/traces/paging-after/turn-04.request.json').read_text(encoding='utf-8'))
    system = (STUDY / 'record/environments/E3.system.txt').read_text(encoding='utf-8')
    captured = []

    def request(self, endpoint, payload=None):
        if endpoint == '/api/version': return {'version': 'test'}
        if endpoint == '/api/tags': return {'models': [{'name': MODEL}]}
        captured.append(deepcopy(payload['messages']))
        return {'message': {'content': '<<<TOOL_CALL>>>\n{"name":"read_doc","args":{"doc_id":"gridlens-api-spec"}}\n<<<END_TOOL_CALL>>>'}}

    monkeypatch.setattr(OllamaClient, '_request', request)
    output = tmp_path / 'replay'
    assert main(['replay', 'paging-after', '--turn', '4', '--env', 'E3', '--out', str(output)]) == 0
    assert captured[0][1:] == history[1:] and captured[0][0]['content'] == system
    assert json.loads((output / 'result.json').read_text())['tools_executed'] is False


def test_dry_run_never_calls_a_provider(monkeypatch, capsys):
    monkeypatch.setattr(OllamaClient, '_request', lambda *a, **k: pytest.fail('Dry run contacted provider'))
    assert main(['run', '--env', 'E4', '--dry-run']) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan['system_sha256'] == hashlib.sha256((STUDY / 'record/environments/E4.system.txt').read_text(encoding='utf-8').encode()).hexdigest()


def test_missing_full_corpus_fails_before_model_request(tmp_path, monkeypatch):
    monkeypatch.setattr(OllamaClient, '_request', lambda *a, **k: pytest.fail('Missing-data run contacted provider'))
    assert main(['run', '--emails', str(tmp_path / 'missing'), '--out', str(tmp_path / 'output')]) == 1
    assert not (tmp_path / 'output').exists()


def test_custom_prompt_is_not_mislabeled_as_unchanged_environment(tmp_path, capsys):
    custom = tmp_path / 'custom.txt'
    custom.write_text((STUDY / 'record/environments/E4.system.txt').read_text(encoding='utf-8') + '\nA new research condition.', encoding='utf-8')
    assert main(['run', '--system', str(custom), '--dry-run']) == 0
    assert json.loads(capsys.readouterr().out)['environment'].startswith('custom-')


@pytest.mark.parametrize('agent,environment', [('current', 'E4'), ('baseline', 'E0')])
def test_named_agent_profiles_preserve_both_versions(capsys, agent, environment):
    assert main(['run', '--agent', agent, '--dry-run']) == 0
    config = json.loads(capsys.readouterr().out)
    assert config['environment'] == environment
    assert config['agent_profile']['id'] == agent
    assert config['model'] == MODEL and config['num_ctx'] == 8192
    expected = (STUDY / f'record/environments/{environment}.system.txt').read_text(encoding='utf-8')
    assert config['system_sha256'] == hashlib.sha256(expected.encode()).hexdigest()


def test_bad_email_archive_is_rejected(tmp_path):
    source = tmp_path / 'bad.gz'
    source.write_bytes(b'not the expected corpus')
    with pytest.raises(ValueError, match='checksum'):
        prepare_email(tmp_path / 'emails.jsonl', source)
    assert not (tmp_path / 'emails.jsonl').exists()


def test_explicit_environment_cannot_silently_modify_a_snapshot(tmp_path, monkeypatch):
    import agent_trace.execution as execution
    import shutil
    shutil.copytree(ROOT / 'configs', tmp_path / 'configs')
    (tmp_path / 'configs/prompts/E3.system.txt').write_text('modified original snapshot', encoding='utf-8')
    monkeypatch.setattr(execution, 'asset_root', lambda: tmp_path)
    assert main(['run', '--env', 'E3', '--dry-run']) == 1


def test_custom_system_catalogue_controls_schema_validation(tmp_path):
    system = 'Tool: read_doc\nDescription: custom research tool\nParameters JSON Schema: {"type":"object","properties":{"doc_id":{"type":"string"}},"required":["doc_id"],"additionalProperties":false}'
    registry = build_registry(lambda _: '', Corpus(ROOT / 'datasets/docs', tmp_path / 'unused'), system)
    assert registry.execute('read_doc', {}).status == 'invalid_args'
    assert registry.execute('read_doc', {'doc_id': 'gridlens-api-spec'}).status == 'ok'


def test_register_copies_evidence_and_rejects_overwrite(tmp_path):
    manifest = tmp_path / 'project/studies/d06/manifest.json'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({'runs': [], 'stages': []}))
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'events.jsonl').write_bytes(b'original evidence\n')
    for name in ('metadata.json', 'result.json'):
        (run / name).write_text('{}')
    (run / 'manifest-entry.json').write_text(json.dumps({'id': 'new-run', 'label': 'new', 'source': 'events.jsonl', 'metadata': 'metadata.json', 'result': 'result.json'}))
    args = ['register', str(run), '--manifest', str(manifest)]
    assert main(args) == 0
    assert (manifest.parent / 'record/evidence/new-run.jsonl').read_bytes() == b'original evidence\n'
    assert main(args) == 1
