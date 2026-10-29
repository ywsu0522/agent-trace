"""The reproduction entry point prepares data and checks actual model identity."""

import json

from agent_trace.cli import main
from agent_trace.llm_ollama import OllamaClient
from agent_trace.paths import asset_root


def test_reproduce_dry_run_has_no_provider_or_download(monkeypatch, capsys):
    import agent_trace.data as data
    monkeypatch.setattr(data, 'prepare_email', lambda *a, **k: (_ for _ in ()).throw(AssertionError('download')))
    monkeypatch.setattr(OllamaClient, '_request', lambda *a, **k: (_ for _ in ()).throw(AssertionError('provider')))
    assert main(['reproduce', '--task', 'd02', '--dry-run']) == 0
    assert json.loads(capsys.readouterr().out)['agent_profile']['model_digest']


def test_reproduce_prepares_missing_corpus_before_executing(tmp_path, monkeypatch):
    import agent_trace.data as data
    calls = []
    emails = tmp_path / 'emails.jsonl'

    def prepare(destination, **kwargs):
        assert kwargs == {'download': True}
        calls.append('prepare')
        emails.write_text('', encoding='utf-8')

    digest = json.loads((asset_root() / 'configs/agents/current.json').read_text())['model_digest']

    def request(self, endpoint, payload=None):
        if endpoint == '/api/version': return {'version': 'test'}
        if endpoint == '/api/tags': return {'models': [{'name': self.model, 'digest': digest}]}
        calls.append('chat')
        return {'message': {'content': '14 characters'}}

    monkeypatch.setattr(data, 'prepare_email', prepare)
    monkeypatch.setattr(OllamaClient, '_request', request)
    out = tmp_path / 'run'
    assert main(['reproduce', '--task', 'd02', '--emails', str(emails), '--out', str(out)]) == 0
    assert calls == ['prepare', 'chat']
    assert json.loads((out / 'result.json').read_text())['answer_match'] is True


def test_reproduce_rejects_same_model_name_with_different_digest(tmp_path, monkeypatch):
    import agent_trace.data as data
    emails = tmp_path / 'emails.jsonl'
    emails.write_text('')
    monkeypatch.setattr(data, 'prepare_email', lambda *a, **k: None)

    def request(self, endpoint, payload=None):
        if endpoint == '/api/version': return {'version': 'test'}
        if endpoint == '/api/tags': return {'models': [{'name': self.model, 'digest': 'different-model'}]}
        raise AssertionError('Wrong model was contacted')

    monkeypatch.setattr(OllamaClient, '_request', request)
    out = tmp_path / 'run'
    assert main(['reproduce', '--emails', str(emails), '--out', str(out)]) == 1
    result = json.loads((out / 'result.json').read_text())
    assert result['agent_requests'] == 0 and result['status'] == 'request_error'
