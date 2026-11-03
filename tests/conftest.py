"""Local course-reference tests are not part of the independent project."""

collect_ignore = ['test_legacy_profile.py']


import pytest
from copy import deepcopy
from threading import Lock


@pytest.fixture
def reply_lm():
    """Independent constant-reply model, including concurrent digest calls."""
    class ReplyLM:
        def __init__(self, reply):
            self.reply = reply
            self.calls = []
            self.lock = Lock()

        def __call__(self, messages):
            with self.lock:
                self.calls.append(deepcopy(messages))
            return self.reply

    return ReplyLM



def pytest_addoption(parser):
    parser.addoption('--hw1-emails', default=None, help='Full local email corpus for P03')


@pytest.fixture(scope='session')
def archive(request):
    import json
    from pathlib import Path
    from agent_trace.data import Corpus, file_hash
    from agent_trace.paths import asset_root

    root = asset_root()
    path = Path(request.config.getoption('--hw1-emails') or root / '.cache/emails.jsonl')
    if not path.is_file():
        pytest.fail('P03 needs the full corpus: run agent-trace prepare-data or use --hw1-emails PATH', pytrace=False)
    spec = json.loads((root / 'datasets/email-source.json').read_text(encoding='utf-8'))
    if file_hash(path) != spec['uncompressed_sha256']:
        pytest.fail('P03 email corpus checksum differs from the full HW1 archive', pytrace=False)
    emails = Corpus(root / 'datasets/docs', path).emails()
    assert len(emails) == spec['emails']
    return emails


@pytest.fixture
def scripted():
    from agent_trace.agent.protocol import format_tool_call
    from tests.scripted_lm import ScriptedLM

    def make(script, *, repeat_last=False):
        return ScriptedLM(script, formatter=format_tool_call, repeat_last=repeat_last)
    return make


@pytest.fixture
def canned_aux():
    from tests.scripted_lm import ScriptedLM
    return ScriptedLM(['Summary of earlier conversation: (canned summary).'], repeat_last=True)


@pytest.fixture
def offline_only(monkeypatch):
    import socket
    from agent_trace.llm_ollama import OllamaClient

    def forbidden(*args, **kwargs):
        pytest.fail('A deterministic test attempted network or provider access')

    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
    monkeypatch.setattr(OllamaClient, '_request', forbidden)
