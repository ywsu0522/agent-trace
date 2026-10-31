"""Check evaluation boundaries and pipeline evidence without model calls."""

import json

import pytest

from agent_trace.pipeline_run import PipelineRun
from agent_trace.pipelines.daily_digest import generate_digest
from scripts.test01 import evaluate_priority, summarize as priority_summary
from scripts.test02 import evaluate_digest, summarize as digest_summary


def day():
    return {'urgent': [{'id': 'u', 'must_mention': [['Orion Works', 'Orion'], ['1,800']]}],
            'ignore': [{'id': 'i', 'must_not_mention': ['Sale']} ]}


def test_digest_requires_each_group_but_accepts_normalized_aliases():
    assert evaluate_digest(day(), 'ORION: budget $1800.')['passed']
    result = evaluate_digest(day(), 'Orion update.')
    assert not result['passed'] and result['missing'][0]['aliases'] == ['1,800']


def test_forbidden_terms_use_whole_tokens_not_substrings():
    assert evaluate_digest(day(), 'Orion 1800 wholesale update.')['passed']
    assert not evaluate_digest(day(), 'Orion 1800 SALE!')['passed']


def test_length_is_measured_on_the_unmodified_completion():
    text = 'Orion 1800 ' + 'word ' * 299
    result = evaluate_digest(day(), text)
    assert result['words'] == 301 and not result['length_ok']
    assert not evaluate_digest(day(), '')['passed']
    assert not evaluate_digest(day(), None)['passed']


def test_priority_batch_requires_accuracy_contract_and_no_unknown():
    good = {**evaluate_priority({'category': 'normal'}, {'category': 'normal', 'reason': 'FYI.'}), 'error': None}
    wrong = {**evaluate_priority({'category': 'normal'}, {'category': 'urgent', 'reason': 'Today.'}), 'error': None}
    assert priority_summary([good] * 51 + [wrong] * 9)['passed']
    unknown = {**evaluate_priority({'category': 'normal'}, {'category': 'unknown', 'reason': 'Missing.'}), 'error': None}
    assert not priority_summary([good] * 59 + [unknown])['passed']
    bad = {**evaluate_priority({'category': 'normal'}, {'category': 'normal', 'reason': ''}), 'error': None}
    assert not priority_summary([good] * 59 + [bad])['passed']


def test_digest_batch_requires_all_three_checks_on_all_days():
    good = {**evaluate_digest(day(), 'Orion 1800'), 'error': None}
    bad = {**evaluate_digest(day(), 'Orion 1800 Sale'), 'error': None}
    result = digest_summary([good, bad])
    assert not result['passed'] and result['days_passed'] == 1
    assert result['must_not_mention_ok'] == 1


def test_pipeline_trace_records_raw_completion_without_agent_protocol(tmp_path):
    out = tmp_path / 'pipeline'
    with PipelineRun(out, settings={'model': 'offline'}, lm=lambda messages: 'raw output') as run:
        output = run.lm([{'role': 'user', 'content': 'input'}])
        run.finish({'parsed': output})
    events = [json.loads(line) for line in (out / 'events.jsonl').read_text().splitlines()]
    assert [e['content'] for e in events if e['kind'] == 'model_response'] == ['raw output']
    assert not any(e['kind'] == 'parse_result' for e in events)
    assert json.loads((out / 'output.json').read_text())['output'] == {'parsed': 'raw output'}


def test_pipeline_failure_leaves_recorded_evidence(tmp_path):
    out = tmp_path / 'pipeline'
    with pytest.raises(RuntimeError, match='offline error'):
        with PipelineRun(out, settings={}, lm=lambda messages: ''):
            raise RuntimeError('offline error')
    assert json.loads((out / 'output.json').read_text())['error']['type'] == 'RuntimeError'


def test_digest_keeps_urgent_evidence_filters_ignore_and_never_trims():
    emails = [{'id': i, 'thread_id': t, 'body': body} for i, t, body in [
        ('normal', 'b', 'Review later ' * 100), ('urgent1', 'a', 'Orion'),
        ('ad', 'a', 'IGNORE_SENTINEL'), ('urgent2', 'a', 'Cedar'), ('unknown', 'c', 'Personal')]]
    calls, stages = [], []
    long_output = 'word ' * 500
    def lm(messages):
        request = json.loads(messages[-1]['content'])
        calls.append(request)
        if request['task'] == 'classify_priority':
            label = {'normal': 'normal', 'urgent1': 'urgent', 'ad': 'ignore', 'urgent2': 'urgent', 'unknown': None}[request['email']['id']]
            return json.dumps({'category': label, 'reason': 'Fixture.'}) if label else '???'
        return long_output
    output = generate_digest(emails, lm, observer=lambda name, **data: stages.append((name, data)))
    assert output == long_output and len(calls) == len(emails) + 1
    writing = calls[-1]
    assert 'IGNORE_SENTINEL' not in json.dumps(writing)
    assert [g['thread_id'] for g in writing['threads']] == ['a', 'b', 'c']
    assert [e['email']['id'] for e in writing['threads'][0]['emails']] == ['urgent1', 'urgent2']
    assert writing['threads'][-1]['emails'][0]['priority'] == 'normal'
    assert [name for name, _ in stages] == ['prepared', 'written']
    normal = writing['threads'][1]['emails'][0]['email']
    assert len(normal['body']) <= 250 and normal['body_is_excerpt']
    assert stages[0][1]['threads'][1]['emails'][0]['email']['body'] == 'Review later ' * 100


@pytest.mark.parametrize('batch', [None, 64])
def test_ollama_prefill_batch_is_optional_and_preserves_raw_output(monkeypatch, batch):
    from agent_trace.llm_ollama import OllamaClient
    payloads = []
    def request(self, endpoint, payload=None):
        payloads.append(payload)
        return {'message': {'content': 'raw digest'}}
    monkeypatch.setattr(OllamaClient, '_request', request)
    lm = OllamaClient(num_batch=batch, json_mode=False)
    assert lm([{'role': 'user', 'content': 'input'}]) == 'raw digest'
    assert ('num_batch' in payloads[0]['options']) == (batch is not None)
    if batch is not None:
        assert payloads[0]['options']['num_batch'] == batch



def test_exact_classification_reuse_is_explicit_and_writer_stays_live(tmp_path):
    from agent_trace.pipeline_run import request_key
    messages = [{'role': 'user', 'content': '{"task":"classify_priority","email":{"id":"a"}}'}]
    cached = {request_key(messages): {'content': 'normal', 'source': 'original/events.jsonl',
                                     'source_sha256': 'a' * 64, 'source_call_id': 'old-call'}}
    called = []
    def live(request):
        called.append(request)
        return 'fresh digest'
    out = tmp_path / 'reused'
    with PipelineRun(out, settings={}, lm=live, responses=cached) as run:
        assert run.lm(messages) == 'normal'
        assert run.lm([{'role': 'user', 'content': '{"task":"write_daily_digest"}'}]) == 'fresh digest'
        run.finish('fresh digest')
    assert len(called) == 1
    events = [json.loads(s) for s in (out / 'events.jsonl').read_text().splitlines()]
    reused = [e for e in events if e['kind'] == 'classification_replay']
    assert len(reused) == 1 and reused[0]['source_call_id'] == 'old-call'
    assert reused[0]['call_id']
    result = json.loads((out / 'output.json').read_text())
    assert result['reused_classifications'] == result['fresh_model_calls'] == 1


def make_classification_source(tmp_path):
    from scripts._common import ROOT, sha256, save
    from agent_trace.pipeline_run import request_key
    settings = {'model': 'offline'}
    metadata = {'settings': settings,
                'source_sha256': {'agent_trace/pipelines/priority.py': sha256(ROOT / 'agent_trace/pipelines/priority.py')},
                'ollama_models': {'models': [{'name': 'offline', 'digest': 'pinned'}]}}
    save(tmp_path / 'metadata.json', metadata)
    save(tmp_path / 'results.json', {'rows': [{'id': 'day', 'error': None}]})
    folder = tmp_path / 'day'
    folder.mkdir()
    events = []
    for call_id, task, content in [('classification', 'classify_priority', 'normal'), ('writing', 'write_daily_digest', 'old digest')]:
        messages = [{'role': 'user', 'content': json.dumps({'task': task})}]
        events += [{'kind': 'model_request', 'call_id': call_id, 'messages': messages},
                   {'kind': 'ollama_http_request', 'call_id': call_id},
                   {'kind': 'ollama_http_response', 'call_id': call_id, 'response': {'message': {'content': content}}},
                   {'kind': 'model_response', 'call_id': call_id, 'content': content}]
    (folder / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events), encoding='utf-8')
    return settings, metadata


def test_classification_source_never_reuses_a_writer_completion(tmp_path):
    from scripts._common import classification_replies
    settings, _ = make_classification_source(tmp_path)
    replies = classification_replies(tmp_path, settings, 'pinned')
    assert len(replies) == 1 and next(iter(replies.values()))['content'] == 'normal'


@pytest.mark.parametrize('change', ['settings', 'digest', 'priority', 'native'])
def test_classification_source_rejects_changed_conditions_or_missing_evidence(tmp_path, change):
    from scripts._common import classification_replies, save
    settings, metadata = make_classification_source(tmp_path)
    digest = 'pinned'
    if change == 'settings':
        settings = {'model': 'other'}
    elif change == 'digest':
        digest = 'changed'
    elif change == 'priority':
        metadata['source_sha256']['agent_trace/pipelines/priority.py'] = 'changed'
        save(tmp_path / 'metadata.json', metadata)
    else:
        path = tmp_path / 'day/events.jsonl'
        events = [json.loads(s) for s in path.read_text().splitlines()]
        events = [e for e in events if e['kind'] != 'ollama_http_response']
        path.write_text('\n'.join(json.dumps(e) for e in events), encoding='utf-8')
    with pytest.raises(ValueError):
        classification_replies(tmp_path, settings, digest)



def test_writer_budget_keeps_all_urgent_subjects_and_only_three_normal_threads():
    from agent_trace.pipelines.daily_digest import write_digest
    def group(priority, name):
        return {'thread_id': name, 'priority': priority, 'emails': [
            {'priority': priority, 'email': {'id': name, 'subject': name, 'body': 'Source details.'}}]}
    threads = [group('urgent', 'Maple plant'), group('urgent', 'Cedar migration')]
    threads += [group('normal', str(i)) for i in range(5)]
    messages = []
    def lm(request):
        messages.extend(request)
        return 'Unmodified model completion.'
    assert write_digest(threads, lm) == 'Unmodified model completion.'
    value = json.loads(messages[-1]['content'])
    assert value['urgent_subjects'] == ['Maple plant', 'Cedar migration']
    assert len(value['threads']) == 5
    assert len(threads) == 7



@pytest.mark.parametrize('gpu', [None, 16])
def test_gpu_layer_limit_is_optional_and_forwarded(monkeypatch, gpu):
    from agent_trace.llm_ollama import OllamaClient
    payloads = []
    def request(self, endpoint, payload=None):
        payloads.append(payload)
        return {'message': {'content': 'raw'}}
    monkeypatch.setattr(OllamaClient, '_request', request)
    assert OllamaClient(num_gpu=gpu)([{'role': 'user', 'content': 'input'}]) == 'raw'
    assert ('num_gpu' in payloads[0]['options']) == (gpu is not None)
    if gpu is not None:
        assert payloads[0]['options']['num_gpu'] == gpu








def test_classification_schema_and_token_limit_do_not_affect_writing(monkeypatch, tmp_path):
    from agent_trace.llm_ollama import OllamaClient
    from agent_trace.pipelines.priority import MODEL_TASK_OPTIONS
    payloads = []
    long_text = 'word ' * 500
    def request(self, endpoint, payload=None):
        payloads.append(payload)
        return {'message': {'content': long_text}}
    monkeypatch.setattr(OllamaClient, '_request', request)
    with PipelineRun(tmp_path / 'modes', settings={'json_mode': False, 'task_options': MODEL_TASK_OPTIONS}) as run:
        for task in ('classify_priority', 'write_daily_digest'):
            assert run.lm([{'role': 'user', 'content': json.dumps({'task': task})}]) == long_text
        run.finish(long_text)
    assert payloads[0]['format'] == MODEL_TASK_OPTIONS['classify_priority']['format']
    assert payloads[0]['options']['num_predict'] == MODEL_TASK_OPTIONS['classify_priority']['num_predict']
    assert 'format' not in payloads[1] and 'num_predict' not in payloads[1]['options']
    es = [json.loads(s) for s in (run.out / 'events.jsonl').read_text().splitlines()]
    assert [e['json_mode'] for e in es if e['kind'] == 'model_request'] == [True, False]



def test_classification_source_accepts_windows_hash_paths(tmp_path):
    from scripts._common import classification_replies, save
    settings, metadata = make_classification_source(tmp_path)
    value = metadata['source_sha256'].pop('agent_trace/pipelines/priority.py')
    metadata['source_sha256'][r'agent_trace\pipelines\priority.py'] = value
    save(tmp_path / 'metadata.json', metadata)
    assert len(classification_replies(tmp_path, settings, 'pinned')) == 1
