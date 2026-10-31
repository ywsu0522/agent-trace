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
