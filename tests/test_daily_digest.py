"""Ported HW1 deterministic tests (standalone agent-trace APIs). Tests for problem (daily_digest)."""

from __future__ import annotations


import pytest

from agent_trace.pipelines.daily_digest import generate_digest


MAX_WORDS = 300  # the live tests check the length of what the model wrote


def make_email(n: int, subject: str, body: str, thread: int | None = None, reply_to=None) -> dict:
    return {
        "id": f"em-9{n:04d}",
        "thread_id": f"th-9{(thread or n):04d}",
        "reply_to": reply_to,
        "from": f"person{n}@cardinal.example",
        "to": ["sam.lee@cardinal.example"],
        "date": f"2001-05-14T{8 + n:02d}:00:00Z",
        "subject": subject,
        "body": body,
    }


DAY = [
    make_email(1, "Outage at the Topock compressor", "Sam, call me before 9. We need a decision."),
    make_email(2, "", "Here is our forecast\n\n "),
    make_email(3, "RE: Outage at the Topock compressor", "Any update?", thread=1, reply_to="em-90001"),
    make_email(4, "50% off toner this week only", "Click here for deals."),
    make_email(5, "", ""),
    make_email(6, "Lunch Thursday?", "Are you free?"),
]

LONG_REPLY = " ".join(f"word{i}" for i in range(500))

REPLIES = {
    "500_words": LONG_REPLY,
    "500_words_on_many_lines": LONG_REPLY.replace(" ", "\n"),
    "one_word": "urgent",
    "empty": "",
    "garbage": "%%% <<>> {]",
}


def check_digest(digest, context: str) -> None:
    assert isinstance(digest, str), (
        f"run_daily_digest should return a string, got {type(digest).__name__}. {context}"
    )


@pytest.mark.parametrize("name", list(REPLIES))
def test_returns_a_string_for_any_reply(name, reply_lm):
    """The scripted model gives the same reply to every call, including a
    500-word one and an empty one. The digest is a string, whatever its
    length: the length limit applies to what the real model writes (live
    tests), and is met by the prompt, not by cutting the text."""
    lm = reply_lm(REPLIES[name])
    digest = generate_digest(DAY, lm)
    check_digest(digest, f"Every model call was answered with the {name!r} scripted reply.")


def test_empty_day(reply_lm):
    lm = reply_lm(LONG_REPLY)
    digest = generate_digest([], lm)
    check_digest(digest, "The input was an empty list of emails.")


def test_blank_subjects_and_bodies(reply_lm):
    blank = [make_email(n, "", "" if n % 2 else "   \n") for n in range(1, 5)]
    lm = reply_lm("normal")
    digest = generate_digest(blank, lm)
    check_digest(digest, "Every email had a blank subject and a blank body.")


def test_emails_are_not_modified(reply_lm):
    day = [dict(email, to=list(email["to"])) for email in DAY]
    before = [dict(email, to=list(email["to"])) for email in day]
    generate_digest(day, reply_lm("normal"))
    assert day == before, "run_daily_digest should not change the emails it is given."
