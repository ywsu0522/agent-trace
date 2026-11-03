# Ported HW1 deterministic cases; original assertions and parameters retained.
"""Tests for problem (email_qa)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = pytest.mark.usefixtures("offline_only")

from tests.scripted_lm import ScriptedLM
from agent_trace.pipelines.email_qa import answer_email_question

HOP_BUDGET = 3


class FakeSearch:
    """A search function that records its calls. Every call returns k new
    emails with ids em-80001, em-80002, ... (or nothing, if empty=True)."""

    def __init__(self, empty: bool = False):
        self.empty = empty
        self.queries: list[str] = []
        self.returned_ids: list[str] = []

    def __call__(self, query: str, k: int = 5) -> list[dict]:
        self.queries.append(query)
        if self.empty:
            return []
        emails = []
        for _ in range(k):
            n = len(self.returned_ids) + 1
            email = {
                "id": f"em-8{n:04d}",
                "thread_id": f"th-8{n:04d}",
                "reply_to": None,
                "from": f"person{n}@cardinal.example",
                "to": ["sam.lee@cardinal.example"],
                "date": f"2001-05-{1 + n % 28:02d}T09:00:00Z",
                "subject": "" if n % 4 == 0 else f"Status note {n}",
                "body": f"Note {n}: the review moved to room {100 + n}.\n",
            }
            self.returned_ids.append(email["id"])
            emails.append(email)
        return emails


# The scripted model gives the same reply to every call. The replies follow
# no particular format. Several ask for another search in different ways, to
# check that no reply can make the loop search more than three times.
REPLIES = {
    "garbage": "%%% <<>> lorem ipsum {]",
    "empty": "",
    "wants_search_1": "SEARCH: budget review room",
    "wants_search_2": "I need more information. Next query: budget review room",
    "wants_search_3": '{"action": "search", "query": "budget review room"}',
    "wants_search_4": "<search>budget review room</search>",
    "unknown_id": "The answer is room 101, based on em-99999 and em-00000.",
    "every_keyword": "ANSWER SEARCH QUERY FINAL SUPPORT em-99999 answer: search: query: final:",
    "long": "I am not sure. " * 300,
}


def check_shape(result, search: FakeSearch, context: str) -> None:
    shown = f"{context} run_email_qa returned {result!r}."
    assert isinstance(result, dict), f"run_email_qa should return a dict. {shown}"
    assert "answer" in result and "support" in result, (
        f"The result needs the keys 'answer' and 'support'. {shown}"
    )
    assert result["answer"] is None or isinstance(result["answer"], str), (
        f"'answer' must be a string, or None when no answer was found. {shown}"
    )
    assert isinstance(result["support"], list) and all(
        isinstance(i, str) for i in result["support"]
    ), f"'support' must be a list of email id strings. {shown}"
    unknown = [i for i in result["support"] if i not in search.returned_ids]
    assert not unknown, (
        f"'support' contains {unknown}, which search() did not return during this call. "
        f"search() returned {search.returned_ids}. {shown}"
    )


@pytest.mark.parametrize("name", list(REPLIES))
def test_hop_budget_and_shape_for_any_reply(name):
    search = FakeSearch()
    lm = ScriptedLM([REPLIES[name]], repeat_last=True)
    result = answer_email_question("Which room did the budget review move to?", search, lm)
    context = f"Every model call was answered with the {name!r} scripted reply."
    assert len(search.queries) <= HOP_BUDGET, (
        f"search() was called {len(search.queries)} times; the hop budget is {HOP_BUDGET}. {context}"
    )
    check_shape(result, search, context)


@pytest.mark.parametrize("name", ["garbage", "wants_search_1", "unknown_id"])
def test_search_returns_nothing(name):
    search = FakeSearch(empty=True)
    lm = ScriptedLM([REPLIES[name]], repeat_last=True)
    result = answer_email_question("Which room did the budget review move to?", search, lm)
    context = f"search() returned no emails and the model replied with the {name!r} scripted reply."
    assert len(search.queries) <= HOP_BUDGET, (
        f"search() was called {len(search.queries)} times; the hop budget is {HOP_BUDGET}. {context}"
    )
    check_shape(result, search, context)
