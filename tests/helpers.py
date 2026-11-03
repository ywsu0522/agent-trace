"""Local helpers for ported deterministic tests; no provider or course imports."""

import json
from pathlib import Path

from agent_trace.errors import OutputTruncated


def load_fixture(name):
    return json.loads((Path(__file__).parent / 'fixtures' / name).read_text(encoding='utf-8'))


def email_text(email):
    return email['subject'] + '\n' + email['body']


def events(transcript, type_):
    return [event for event in transcript if event.get('type') == type_]


def truncated(text='', *, max_tokens=64):
    # Only the exception type and partial text cross the local session boundary.
    def raise_it(messages):
        raise OutputTruncated(text)
    return raise_it
