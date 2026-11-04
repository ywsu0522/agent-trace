"""Retrospective review-only versus evidence-continuation experiment.

Example: python -m scripts.refine_docs --source studies/d06/record/runs/protocol-after
         --task d06 --mode live
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time
from urllib.parse import urlparse

from agent_trace.data import Corpus, file_hash
from agent_trace.llm_ollama import OllamaClient
from agent_trace.paths import asset_root
from agent_trace.pipeline_run import PipelineRun
from agent_trace.pipelines.doc_retrieval import build_doc_index
from agent_trace.refinement import observed_case, prepare, refine
from agent_trace.tokens import count_message_tokens, count_tokens
from scripts._common import contains


ROOT = asset_root()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def score(text, item):
    # Evaluation only. Neither this item nor its source location enters prepare/refine.
    return {'answer_match': any(contains(text, alias) for alias in item['answers']),
            'stale_match': any(contains(text, alias) for alias in item.get('stale', [])),
            'method': 'HW1 normalized whole-token aliases; not semantic support verification'}


def native_cost(events, expected_calls=None):
    responses = [e['response'] for e in events if e['kind'] == 'ollama_http_response'
                 and isinstance(e.get('response'), dict) and 'message' in e['response']]
    complete = expected_calls is None or len(responses) == expected_calls
    def total(key):
        return sum(r[key] for r in responses) if complete and responses and all(key in r for r in responses) else None
    return {'native_prompt_tokens': total('prompt_eval_count'),
            'native_completion_tokens': total('eval_count'),
            'native_total_duration_ns': total('total_duration'),
            'output_truncated': (any(r['done_reason'] == 'length' for r in responses)
                                 if complete and responses and all('done_reason' in r for r in responses) else None)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Saved full-run directory with trace.json and events.jsonl')
    parser.add_argument('--task', required=True, help='Fixture ID used ONLY for post-hoc scoring')
    parser.add_argument('--mode', choices=('prepare', 'live'), default='prepare')
    parser.add_argument('--model', default='qwen3.5:4b-q4_K_M')
    parser.add_argument('--base-url', default='http://127.0.0.1:11434')
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--num-ctx', type=int, default=8192)
    parser.add_argument('--num-gpu', type=int, default=12)
    parser.add_argument('--num-batch', type=int, default=64)
    parser.add_argument('--max-output-tokens', type=int, default=384)
    parser.add_argument('--prompt-budget', type=int, default=7600)
    parser.add_argument('--max-extra-reads', type=int, choices=(0, 1, 2), default=1)
    parser.add_argument('--document-budget', type=int, default=6000)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    url = urlparse(args.base_url)
    if url.scheme != 'http' or url.hostname not in ('localhost', '127.0.0.1', '::1'):
        parser.error('Use a local Ollama HTTP server')
    if (min(args.timeout, args.num_ctx, args.num_batch, args.max_output_tokens, args.prompt_budget,
            args.document_budget) < 1 or args.num_gpu < 0
            or args.prompt_budget + args.max_output_tokens > args.num_ctx):
        parser.error('Invalid budgets: reserve output space within num-ctx')
    trace_path, events_path = args.source / 'trace.json', args.source / 'events.jsonl'
    trace = load(trace_path)
    if file_hash(events_path) != trace['raw_sha256']:
        raise ValueError('Source events checksum differs from the saved report')
    case = observed_case(trace)
    fixture_path = ROOT / 'tests/fixtures/doc_questions.json'
    item = next((x for x in load(fixture_path) if x['id'] == args.task), None)
    if item is None or item['question'] != case['question']:
        raise ValueError('Scoring task must match the saved question exactly')
    index = build_doc_index(Corpus(ROOT / 'datasets/docs', ROOT / '.cache/emails.jsonl').docs())
    plans = {}
    for name, continuation in (('review_only', False), ('continue_then_review', True)):
        started = time.monotonic()
        plans[name] = prepare(case, index, continue_pages=continuation,
                              max_extra_reads=args.max_extra_reads, document_budget=args.document_budget)
        plans[name]['preparation_seconds'] = time.monotonic() - started
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = (args.out or ROOT / 'runs' / ('refine-docs-' + stamp)).resolve()
    out.mkdir(parents=True, exist_ok=False)
    settings = {'model': args.model, 'base_url': args.base_url, 'timeout': args.timeout,
                'temperature': 0, 'think': False, 'json_mode': False, 'num_ctx': args.num_ctx,
                'num_gpu': args.num_gpu, 'num_batch': args.num_batch,
                'task_options': {'refine_document_answer': {'num_predict': args.max_output_tokens}}}
    # The adapter selects output settings by task, without changing the model-visible question.
    for plan in plans.values():
        payload = json.loads(plan['messages'][-1]['content'])
        plan['messages'][-1]['content'] = json.dumps({'task': 'refine_document_answer', **payload}, ensure_ascii=False)
        plan['prompt_tokens_estimate'] = count_message_tokens(plan['messages'])
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    baseline_events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()]
    baseline_calls = [(t['messages'], t['completion']) for t in trace['turns']]
    baseline_calls += [(a['messages'], a['completion']) for t in trace['turns'] for a in t['aux']]
    metadata = {'study': 'retrospective bounded evidence refinement', 'mode': args.mode,
                'settings': settings, 'source': str(args.source.resolve()),
                'source_trace_sha256': file_hash(trace_path), 'source_events_sha256': file_hash(events_path),
                'fixture_sha256': file_hash(fixture_path), 'task': args.task, 'commit': commit,
                'source_environment': trace['environment'], 'source_settings': trace['settings'],
                'max_extra_model_calls_per_condition': 1, 'max_extra_reads_per_condition': args.max_extra_reads,
                'prompt_budget_estimate': args.prompt_budget, 'document_budget_estimate': args.document_budget,
                'baseline_requests': trace['main_count'] + trace['aux_count'],
                'baseline_model_tokens_estimate': sum(count_message_tokens(m) + count_tokens(c) for m, c in baseline_calls),
                'baseline_native_cost': native_cost(baseline_events, trace['main_count'] + trace['aux_count']),
                'documents_sha256': {p.name: file_hash(p) for p in sorted((ROOT / 'datasets/docs').glob('*.md'))},
                'limitations': ['Archived baseline is reused, not rerun; this is not a fresh current-agent benchmark.',
                                'Both treatments use one additional model call; the baseline cost is shared.',
                                'All variants are retained; gold never chooses which answer to return.',
                                'Token estimates use ceil(characters/4), not the backend tokenizer.',
                                'Reading a reference line or naming a document is not proof of semantic support.']}
    sources = list((ROOT / 'agent_trace').rglob('*.py')) + [Path(__file__).resolve(), ROOT / 'scripts/_common.py']
    metadata['source_sha256'] = {p.relative_to(ROOT).as_posix(): file_hash(p) for p in sources}
    for path in sources:
        target = out / 'source' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    for path in (trace_path, events_path):
        shutil.copyfile(path, out / ('baseline-' + path.name))
    for filename in ('metadata.json', 'result.json'):
        path = args.source / filename
        if path.is_file():
            shutil.copyfile(path, out / ('baseline-' + filename))
            metadata['baseline_' + filename + '_sha256'] = file_hash(path)
    save(out / 'metadata.json', metadata)
    save(out / 'plans.json', plans)
    print(f'Study: {out}', flush=True)
    if args.mode == 'prepare':
        print('Prepared only; no inference. Reference answers are absent from plans.json.', flush=True)
        return 0
    client = OllamaClient(**settings)
    try:
        metadata['ollama_version'] = client._request('/api/version')
        metadata['ollama_models'] = client._request('/api/tags')
        selected = next(m for m in metadata['ollama_models']['models'] if m['name'] == args.model)
        metadata['selected_model_digest'] = selected['digest']
    except Exception as exc:
        metadata['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        save(out / 'metadata.json', metadata)
        print(f'Preflight failed: {exc}', flush=True)
        return 1
    save(out / 'metadata.json', metadata)
    rows = [{'condition': 'archived_baseline', 'text': case['draft'], 'fresh_calls': 0,
             'extra_reads': 0, 'total_requests_for_policy': metadata['baseline_requests'],
             'total_model_tokens_estimate': metadata['baseline_model_tokens_estimate'],
             **score(case['draft'], item)}]
    for name, plan in plans.items():
        if name == 'continue_then_review' and not plan['extra_tools']:
            rows.append({'condition': name, 'skipped': True, 'reason': plan['stop'], 'fresh_calls': 0,
                         'extra_reads': 0, 'text': None, 'answer_match': None})
            save(out / 'progress.json', rows)
            continue
        text, error = None, None
        run = None
        started = time.monotonic()
        try:
            with PipelineRun(out / name, settings=settings) as run:
                run.stage('preparation', **plan)
                text = refine(plan, run.lm, prompt_budget=args.prompt_budget)
                run.finish(text)
        except Exception as exc:
            error = {'type': type(exc).__name__, 'message': str(exc)}
        events = [json.loads(line) for line in run.recorder.events_path.read_text(encoding='utf-8').splitlines()] if run else []
        fresh = sum(e['kind'] == 'ollama_http_request' for e in events)
        row = {'condition': name, 'text': text, 'error': error, 'fresh_calls': fresh,
               'extra_reads': len(plan['extra_tools']), 'read_attempts': plan['read_attempts'],
               'incremental_seconds': round(time.monotonic() - started + plan['preparation_seconds'], 3),
               'total_document_tokens_estimate': plan['total_document_tokens_estimate'],
               'total_requests_for_policy': metadata['baseline_requests'] + fresh,
               'total_model_tokens_estimate': (metadata['baseline_model_tokens_estimate'] +
                                               plan['prompt_tokens_estimate'] + count_tokens(text or '')),
               **native_cost(events), **score(text or '', item)}
        if error is not None:
            row['answer_match'] = row['stale_match'] = None
        # Reference-line exposure is a diagnostic computed only AFTER generation.
        row['reference_line_in_extra_read'] = any(
            (v := json.loads(t['content']))['doc_id'] == item['doc_id']
            and v['start_line'] <= item['line'] <= v['end_line'] for t in plan['extra_tools'])
        rows.append(row)
        save(out / 'progress.json', rows)
        print(f'{name}: answer_match={row["answer_match"]}, calls={fresh}, extra_reads={row["extra_reads"]}, error={error}', flush=True)
    result = {'task': args.task, 'retrospective': True, 'not_full_benchmark': True,
              'actual_fresh_model_calls': sum(r['fresh_calls'] for r in rows), 'rows': rows}
    save(out / 'results.json', result)
    lines = ['# Bounded document refinement', '', 'Retrospective diagnostic; not a fresh current-agent benchmark.', '',
             '| Condition | Answer alias match | Fresh calls | Extra reads |', '|---|---|---:|---:|']
    for row in rows:
        lines.append(f'| {row["condition"]} | {row["answer_match"]} | {row["fresh_calls"]} | {row["extra_reads"]} |')
    for row in rows:
        lines += ['', f'## {row["condition"]}', '', row['text'] or str(row.get('error') or row.get('reason'))]
    lines += ['', '## Limits', ''] + ['- ' + note for note in metadata['limitations']]
    (out / 'study.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return 1 if any(r.get('error') for r in rows) else 0


if __name__ == '__main__':
    raise SystemExit(main())
