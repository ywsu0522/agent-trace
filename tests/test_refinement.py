"""Budget enforcement, evidence provenance and gold isolation for refinement."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from agent_trace.pipelines.doc_retrieval import build_doc_index
from agent_trace.refinement import observed_case, prepare, refine
from agent_trace.tokens import count_tokens


def example(*, complete=False):
    index = build_doc_index([{'doc_id': 'spec', 'title': 'API spec',
                             'text': 'API v1\nOld publication date: 2025-02-01.\nShutdown: 2027-03-15.'}])
    end = 3 if complete else 2
    value = {'doc_id': 'spec', 'start_line': 1, 'end_line': end, 'total_lines': 3,
             'text': '\n'.join(index['docs'][0]['text'].splitlines()[:end])}
    case = {'question': 'When will v1 shut down?', 'draft': '2025-02-01',
            'tools': [{'name': 'read_doc', 'args': {'doc_id': 'spec'}, 'status': 'ok',
                       'content': json.dumps(value)}]}
    return case, index


def test_continuation_is_chosen_by_read_progress_and_draft_is_preserved():
    case, index = example()
    original = deepcopy(case)
    review = prepare(case, index, continue_pages=False)
    repair = prepare(case, index, continue_pages=True)
    assert 'Shutdown: 2027-03-15.' not in review['messages'][-1]['content']
    assert 'Shutdown: 2027-03-15.' in repair['messages'][-1]['content']
    assert repair['extra_tools'][0]['args'] == {'doc_id': 'spec', 'start_line': 3}
    assert repair['total_document_tokens_estimate'] == (
        sum(count_tokens(t['content']) for t in case['tools']) + count_tokens(repair['extra_tools'][0]['content']))
    assert case == original


def test_gold_and_task_metadata_cannot_cross_generation_boundary():
    case, index = example()
    trace = {'kind': 'full', 'status': 'done', 'question': case['question'], 'final': case['draft'],
             'expected_answers': ['SECRET-GOLD'], 'reference_line': 12345,
             'turns': [{'tools': [{**case['tools'][0], 'gold': 'SECRET-GOLD'}]}]}
    clean = observed_case(trace)
    changed = deepcopy(trace)
    changed['expected_answers'] = ['DIFFERENT-GOLD']
    changed['reference_line'] = 42
    assert observed_case(changed) == clean
    prepared = prepare(clean, index, continue_pages=True)
    assert 'SECRET-GOLD' not in json.dumps(prepared)
    assert 'reference_line' not in json.dumps(prepared)


@pytest.mark.parametrize('complete,search_only', [(True, False), (False, True)])
def test_complete_or_search_only_history_has_no_invented_page(complete, search_only):
    case, index = example(complete=complete)
    if search_only:
        case['tools'] = [{'name': 'search_docs', 'args': {'query': 'API'}, 'status': 'ok',
                          'content': json.dumps([{'doc_id': 'spec', 'title': 'API', 'snippet': 'API v1'}])}]
    plan = prepare(case, index, continue_pages=True)
    assert plan['extra_tools'] == []
    assert plan['read_attempts'] == 0


def test_document_limit_is_shared_with_original_and_repeated_results():
    case, index = example()
    case['tools'] *= 2
    original = sum(count_tokens(t['content']) for t in case['tools'])
    plan = prepare(case, index, continue_pages=True, document_budget=original)
    assert plan['stop'] == 'document_budget'
    assert plan['extra_tools'] == []
    assert plan['original_document_tokens_estimate'] == original
    assert len(json.loads(plan['messages'][-1]['content'])['evidence']) == 1


def test_stale_corpus_is_rejected_instead_of_reading_a_different_next_page():
    case, index = example()
    index['by_id']['spec']['text'] = 'Different header\nOther text\nOther date'
    with pytest.raises(ValueError, match='differs'):
        prepare(case, index, continue_pages=True)


def test_two_document_continuations_share_the_read_limit():
    case, index = example()
    index['by_id']['other'] = {**index['docs'][0], 'doc_id': 'other'}
    tool = deepcopy(case['tools'][0])
    value = json.loads(tool['content'])
    value['doc_id'] = 'other'
    tool['content'] = json.dumps(value)
    case['tools'].append(tool)
    plan = prepare(case, index, continue_pages=True, max_extra_reads=1)
    assert len(plan['extra_tools']) == 1
    assert plan['extra_tools'][0]['args']['doc_id'] == 'spec'


@pytest.mark.parametrize('document_budget,prompt_budget', [(1, 7600), (6000, 1)])
def test_exceeded_budget_blocks_model_before_inference(document_budget, prompt_budget):
    case, index = example()
    plan = prepare(case, index, continue_pages=True, document_budget=document_budget)
    with pytest.raises(ValueError, match='budget'):
        refine(plan, lambda _: pytest.fail('No budget remains for a model call'), prompt_budget=prompt_budget)


def test_one_call_preserves_even_a_worse_completion_without_oracle_selection():
    case, index = example()
    plan = prepare(case, index, continue_pages=True)
    calls = []
    def model(messages):
        calls.append(messages)
        return '  An incorrect revised answer.\n'
    assert refine(plan, model) == '  An incorrect revised answer.\n'
    assert len(calls) == 1


def test_model_error_propagates_without_unbounded_retry():
    case, index = example()
    calls = []
    def model(messages):
        calls.append(messages)
        raise RuntimeError('offline inference failure')
    with pytest.raises(RuntimeError, match='offline inference failure'):
        refine(prepare(case, index, continue_pages=True), model)
    assert len(calls) == 1


def test_partial_native_history_is_not_reported_as_complete_cost():
    from scripts.refine_docs import native_cost
    events = [{'kind': 'ollama_http_response', 'response': {
        'message': {'content': 'one recorded reply'}, 'prompt_eval_count': 20, 'eval_count': 5}}]
    assert native_cost(events, expected_calls=2)['native_prompt_tokens'] is None
    assert native_cost(events, expected_calls=1)['native_prompt_tokens'] == 20


def test_backend_length_stop_is_reported_without_trimming_the_answer():
    from scripts.refine_docs import native_cost
    events = [{'kind': 'ollama_http_response', 'response': {
        'message': {'content': 'Unfinished answer'}, 'done_reason': 'length'}}]
    assert native_cost(events)['output_truncated'] is True


def test_archived_d06_and_controls_obey_same_rule():
    root = Path(__file__).resolve().parents[1]
    from agent_trace.data import Corpus
    index = build_doc_index(Corpus(root / 'datasets/docs', root / '.cache/emails.jsonl').docs())
    source = root / 'studies/d06/record/runs'
    case = observed_case(json.loads((source / 'protocol-after/trace.json').read_text(encoding='utf-8')))
    plan = prepare(case, index, continue_pages=True)
    assert plan['extra_tools'][0]['args'] == {'doc_id': 'gridlens-api-spec', 'start_line': 90}
    assert plan['total_document_tokens_estimate'] <= 6000
    search_only = observed_case(json.loads((source / 'paging-after/trace.json').read_text(encoding='utf-8')))
    assert prepare(search_only, index, continue_pages=True)['extra_tools'] == []
    complete = observed_case(json.loads((root / 'studies/baseline-20/record/d09/trace.json').read_text(encoding='utf-8')))
    assert prepare(complete, index, continue_pages=True)['extra_tools'] == []


def test_study_records_both_outputs_cost_and_native_evidence(tmp_path, monkeypatch):
    from agent_trace.llm_ollama import OllamaClient
    from scripts.refine_docs import main
    root = Path(__file__).resolve().parents[1]
    calls = []
    def request(self, endpoint, payload=None):
        if endpoint == '/api/version':
            return {'version': 'offline-test'}
        if endpoint == '/api/tags':
            return {'models': [{'name': 'qwen3.5:4b-q4_K_M', 'digest': 'offline-test'}]}
        calls.append(deepcopy(payload))
        # Deliberately make treatment worse: it must be kept, not selected by gold.
        text = 'December 31, 2026. [gridlens-api-spec]' if len(calls) == 1 else 'Unknown.'
        return {'message': {'content': text}, 'prompt_eval_count': 100, 'eval_count': 12}
    monkeypatch.setattr(OllamaClient, '_request', request)
    out = tmp_path / 'study'
    assert main(['--source', str(root / 'studies/d06/record/runs/protocol-after'),
                 '--task', 'd06', '--mode', 'live', '--out', str(out)]) == 0
    result = json.loads((out / 'results.json').read_text())
    assert len(calls) == result['actual_fresh_model_calls'] == 2
    assert result['rows'][1]['answer_match'] is True
    assert result['rows'][2]['text'] == 'Unknown.'
    assert result['rows'][2]['answer_match'] is False
    assert result['rows'][2]['native_prompt_tokens'] == 100
    assert 'expected_answers' not in json.dumps(calls)
    assert 'reference_line' not in json.dumps(calls)
    for condition in ('review_only', 'continue_then_review'):
        events = [json.loads(s) for s in (out / condition / 'events.jsonl').read_text().splitlines()]
        assert sum(e['kind'] == 'ollama_http_response' for e in events) == 1
