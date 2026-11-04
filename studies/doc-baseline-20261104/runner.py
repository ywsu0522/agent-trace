"""Run all 20 document questions through the current CLI/AgentSession, once.

No prompt variants, sampling overrides, repair or response reuse are applied.
"""

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from agent_trace.cli import main as run_agent
from agent_trace.data import file_hash
from agent_trace.paths import asset_root
from scripts._common import contains


ROOT = asset_root()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def evaluate(item, folder, error=None):
    result = load(folder / 'result.json') if (folder / 'result.json').is_file() else {}
    trace = load(folder / 'trace.json') if (folder / 'trace.json').is_file() else {}
    text = result.get('text', '')
    finished = result.get('status') == 'done' and not error and not result.get('error')
    tools = [tool for turn in trace.get('turns', []) for tool in turn['tools']]
    cost = trace.get('document_result_tokens_estimate')
    events_path = folder / 'events.jsonl'
    events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()] if events_path.is_file() else []
    requests = [e for e in events if e['kind'] == 'ollama_http_request' and e.get('endpoint') == '/api/chat']
    responses = [e['response'] for e in events if e['kind'] == 'ollama_http_response' and 'message' in e.get('response', {})]
    def native_total(key):
        return sum(r[key] for r in responses) if len(responses) == len(requests) and responses and all(key in r for r in responses) else None
    read_reference = any(
        t['name'] == 'read_doc' and t['status'] == 'ok' and isinstance(t.get('value'), dict)
        and t['value'].get('doc_id') == item['doc_id']
        and t['value'].get('start_line', 0) <= item['line'] <= t['value'].get('end_line', 0)
        for t in tools)
    return {'id': item['id'], 'question': item['question'], 'kind': item['kind'],
            'status': result.get('status', 'not_completed'), 'text': text,
            'error': error or result.get('error'), 'answer_match': finished and any(contains(text, a) for a in item['answers']),
            'answer_match_method': 'HW1 normalized whole-token aliases; not semantic grading',
            'runtime_substring_match': result.get('answer_match'),
            'document_result_tokens_estimate': cost, 'within_document_budget': cost is not None and cost <= 6000,
            'reference_line_read': read_reference, 'evidence_support': 'not_reviewed',
            'stale_alias_mentioned': any(contains(text, a) for a in item.get('stale', [])),
            'agent_requests': trace.get('main_count', 0), 'aux_requests': trace.get('aux_count', 0),
            'http_model_requests': len(requests), 'http_model_responses': len(responses),
            'native_prompt_tokens': native_total('prompt_eval_count'),
            'native_completion_tokens': native_total('eval_count'),
            'output_truncated': any(r.get('done_reason') == 'length' for r in responses),
            'seconds': result.get('seconds'), 'trace': item['id'] + '/trace.md'}


def summarize(rows):
    hits = sum(row['answer_match'] for row in rows)
    return {'completed': len(rows), 'total': 20, 'answer_matches': hits,
            'matched_within_document_budget': sum(row['answer_match'] and row['within_document_budget'] for row in rows),
            'within_document_budget': sum(row['within_document_budget'] for row in rows),
            'errors': sum(row['error'] is not None for row in rows),
            'agent_requests': sum(row['agent_requests'] for row in rows),
            'aux_requests': sum(row['aux_requests'] for row in rows),
            'http_model_requests': sum(row['http_model_requests'] for row in rows),
            'passed': len(rows) == 20 and hits >= 15 and all(row['within_document_budget'] and not row['error'] for row in rows),
            'evidence_support': 'not_reviewed', 'rows': rows}


def run_batch(out):
    fixture = ROOT / 'tests/fixtures/doc_questions.json'
    items = load(fixture)
    if [x['id'] for x in items] != [f'd{i:02d}' for i in range(1, 21)]:
        raise ValueError('This baseline requires the original d01-d20 fixture in order')
    profile = ROOT / 'configs/agents/current.json'
    prompt = ROOT / load(profile)['system_prompt']
    frozen = {p: file_hash(p) for p in [profile, prompt, fixture, *sorted((ROOT / 'agent_trace').rglob('*.py')),
                                        *sorted((ROOT / 'datasets/docs').glob('*.md'))]}
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(fixture, out / 'fixture.json')
    shutil.copyfile(prompt, out / 'system.txt')
    shutil.copyfile(profile, out / 'agent-profile.json')
    shutil.copyfile(Path(__file__), out / 'runner.py')
    metadata = {'study': 'current agent document QA baseline', 'started_at': datetime.now(timezone.utc).isoformat(),
                'all_questions': 20, 'order': [x['id'] for x in items], 'fresh_session_per_question': True,
                'repair': False, 'response_reuse': False, 'settings': load(profile),
                'file_sha256': {p.relative_to(ROOT).as_posix(): sha for p, sha in frozen.items()},
                'runner_sha256': file_hash(Path(__file__)),
                'notes': ['Generation uses the existing CLI unchanged; only each question enters user content.',
                          'Reference answers and locations are used only for post-hoc evaluation.',
                          '6000 document-result tokens are evaluated, not enforced by the current agent loop.',
                          'Reference-line reading and stale-alias mentions are diagnostics, not semantic support checks.']}
    save(out / 'metadata.json', metadata)
    rows = []
    print(f'Baseline output: {out}', flush=True)
    try:
        for item in items:
            if any(file_hash(p) != sha for p, sha in frozen.items()):
                raise RuntimeError('Source, configuration, fixture or documents changed during the baseline')
            save(out / 'progress.json', {**summarize(rows), 'running': item['id']})
            print(f'[{len(rows)+1}/20] START {item["id"]}: {item["question"]}', flush=True)
            folder = out / item['id']
            error = None
            with (out / (item['id'] + '.log')).open('w', encoding='utf-8') as log:
                try:
                    with redirect_stdout(log), redirect_stderr(log):
                        code = run_agent(['run', '--task', item['id'], '--out', str(folder)])
                    if code:
                        error = {'type': 'ExecutionFailed', 'message': f'CLI returned {code}; see {item["id"]}.log and trace'}
                except Exception as exc:
                    error = {'type': type(exc).__name__, 'message': str(exc)}
            row = evaluate(item, folder, error)
            rows.append(row)
            save(folder / 'evaluation.json' if folder.is_dir() else out / (item['id'] + '.evaluation.json'), row)
            save(out / 'progress.json', {**summarize(rows), 'running': None})
            print(f'[{len(rows)}/20] END {item["id"]}: match={row["answer_match"]}, status={row["status"]}, '
                  f'doc_tokens={row["document_result_tokens_estimate"]}, calls={row["http_model_requests"]}', flush=True)
    finally:
        summary = summarize(rows)
        summary['finished_at'] = datetime.now(timezone.utc).isoformat()
        save(out / 'results.json', summary)
        lines = ['# Current agent: 20-question document QA baseline', '',
                 f'Completed: {len(rows)}/20; answer matches: {summary["answer_matches"]}/20; '
                 f'within document budget: {summary["within_document_budget"]}/20; errors: {summary["errors"]}.', '',
                 'Evidence support has not been semantically reviewed. No repair or response reuse.', '',
                 '| ID | Answer match | Status | Document tokens | Main / aux |', '|---|---|---|---:|---:|']
        for row in rows:
            lines.append(f'| [{row["id"]}]({row["trace"]}) | {row["answer_match"]} | {row["status"]} | '
                         f'{row["document_result_tokens_estimate"]} | {row["agent_requests"]} / {row["aux_requests"]} |')
        (out / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}, indent=2), flush=True)
    return 0 if summary['passed'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    return run_batch(args.out or ROOT / 'runs' / ('doc-baseline-20-' + stamp))


if __name__ == '__main__':
    raise SystemExit(main())
