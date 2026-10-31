"""Small shared CLI/report helpers; all live inference uses local Ollama."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse

from agent_trace.llm_ollama import OllamaClient
from agent_trace.paths import asset_root
from agent_trace.pipelines.priority import MODEL_TASK_OPTIONS
from agent_trace.pipeline_run import PipelineRun, request_key

ROOT = asset_root()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contains(text, alias):
    """HW1 matching: lowercase, remove numeric commas, whole token sequence."""
    def normalize(value):
        value = re.sub(r'(?<=\d),(?=\d{3}\b)', '', value.lower())
        return ' '.join(re.findall(r'[a-z0-9]+', value))
    needle = normalize(alias)
    return bool(needle) and f' {needle} ' in f' {normalize(text)} '


def arguments(problem, fixture, argv=None):
    parser = argparse.ArgumentParser(description=f'HW1 {problem}: deterministic and local Ollama live evaluation')
    parser.add_argument('--mode', choices=('all', 'deterministic', 'live'), default='all')
    parser.add_argument('--fixture', type=Path, default=ROOT / 'tests/fixtures' / fixture)
    parser.add_argument('--model', default='qwen3.5:4b-q4_K_M')
    parser.add_argument('--base-url', default='http://127.0.0.1:11434')
    parser.add_argument('--num-ctx', type=int, default=4096)
    parser.add_argument('--num-gpu', type=int, default=12,
                        help='GPU layers; Reserve VRAM headroom with 12 layers (0 = CPU)')
    parser.add_argument('--num-batch', type=int, default=64,
                        help='Ollama prefill batch; P02 defaults to 64 to limit RAM peaks')
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--workers', type=int, default=2, help='Concurrent P02 classification calls')
    parser.add_argument('--emails', type=Path, default=ROOT / '.cache/emails.jsonl')
    parser.add_argument('--reuse-classifications', type=Path,
                        help='P02 only: reuse exact classification requests from a completed run; writing stays live')
    parser.add_argument('--out', type=Path, help='A new, nonexistent output directory')
    args = parser.parse_args(argv)
    url = urlparse(args.base_url)
    if url.scheme != 'http' or url.hostname not in ('localhost', '127.0.0.1', '::1'):
        parser.error('--base-url must point to a local Ollama HTTP server')
    if min(args.num_ctx, args.timeout, args.workers) < 1:
        parser.error('num-ctx, timeout and workers must be positive')
    if args.num_gpu is not None and args.num_gpu < 0:
        parser.error('num-gpu must be nonnegative')
    if args.num_batch is not None and args.num_batch < 1:
        parser.error('num-batch must be positive')
    if args.reuse_classifications and problem != 'p02':
        parser.error('classification reuse is only supported for P02')
    return args


def deterministic(problem):
    # Explicit paths and the project root prevent collecting a parent HW1 repo.
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    return subprocess.run([sys.executable, '-m', 'pytest', str(ROOT / f'tests/test_{problem}.py'),
                           '--basetemp', str(ROOT / '.cache' / ('pytest-' + stamp))], cwd=ROOT).returncode



def classification_replies(source, settings, model_digest):
    source = source.resolve()
    metadata = load(source / 'metadata.json')
    if metadata['settings'] != settings:
        raise ValueError('Classification reuse requires identical model settings')
    source_hashes = {key.replace('\\', '/'): value for key, value in metadata['source_sha256'].items()}
    if source_hashes.get('agent_trace/pipelines/priority.py') != sha256(ROOT / 'agent_trace/pipelines/priority.py'):
        raise ValueError('Priority implementation changed; classifications must run again')
    model = next(m for m in metadata['ollama_models']['models'] if m['name'] == settings['model'])
    if model['digest'] != model_digest:
        raise ValueError('Classification source model digest differs')
    # A completed source run may fail accuracy checks, but must contain all days.
    batch = load(source / 'results.json')
    if any(row['error'] for row in batch['rows']):
        raise ValueError('Cannot reuse classifications from an incomplete or errored run')
    replies = {}
    for row in batch['rows']:
        path = source / row['id'] / 'events.jsonl'
        events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        source_hash = sha256(path)
        requests = {e['call_id']: e for e in events if e['kind'] == 'model_request'}
        for response in events:
            if response['kind'] != 'model_response':
                continue
            request = requests[response['call_id']]
            messages = request['messages']
            try:
                task = json.loads(messages[-1]['content']).get('task')
            except (ValueError, AttributeError):
                continue
            if task != 'classify_priority':
                continue
            # Require a real native model response in the original run.
            if not any(e['kind'] == 'ollama_http_request' and e.get('call_id') == request['call_id'] for e in events):
                raise ValueError('Classification source is not a fresh local inference')
            native = next((e for e in events if e['kind'] == 'ollama_http_response' and e.get('call_id') == request['call_id']), None)
            if native is None or native['response'].get('message', {}).get('content') != response['content']:
                raise ValueError('Classification source lacks matching native response evidence')
            key = request_key(messages)
            saved = {'content': response['content'], 'source': str(path),
                     'source_sha256': source_hash, 'source_call_id': request['call_id']}
            if key in replies and replies[key]['content'] != saved['content']:
                raise ValueError('Conflicting replies for the same classification request')
            replies[key] = saved
    return replies


def run_cases(args, problem, items, generate, evaluate, summarize, *, corpus_path=None):
    out = (args.out or ROOT / 'runs' / (problem + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))).resolve()
    out.mkdir(parents=True, exist_ok=False)
    settings = {'model': args.model, 'base_url': args.base_url, 'timeout': args.timeout,
                'temperature': 0, 'num_ctx': args.num_ctx, 'think': False, 'json_mode': False,
                'task_options': MODEL_TASK_OPTIONS}
    if args.num_gpu is not None:
        settings['num_gpu'] = args.num_gpu
    if args.num_batch is not None:
        settings['num_batch'] = args.num_batch
    sources = [ROOT / 'agent_trace/pipelines/priority.py', ROOT / 'agent_trace/pipelines/daily_digest.py',
               ROOT / 'agent_trace/llm_ollama.py', ROOT / 'agent_trace/pipeline_run.py',
               ROOT / 'scripts/_common.py', ROOT / f'scripts/test{problem[1:]}.py']
    metadata = {'problem': 'HW1 ' + problem, 'backend': 'local Ollama', 'settings': settings,
                'fixture': str(args.fixture.resolve()), 'fixture_sha256': sha256(args.fixture),
                'source_sha256': {p.relative_to(ROOT).as_posix(): sha256(p) for p in sources},
                'workers': args.workers}
    if corpus_path is not None:
        metadata.update(corpus=str(corpus_path.resolve()), corpus_sha256=sha256(corpus_path))
    save(out / 'metadata.json', metadata)
    (out / 'fixture.json').write_bytes(args.fixture.read_bytes())
    print(f'{problem} output: {out}', flush=True)
    # Preflight once; no API keys, external providers or automatic downloads.
    client = OllamaClient(**settings)
    try:
        metadata['ollama_version'] = client._request('/api/version')
        metadata['ollama_models'] = client._request('/api/tags')
        if not any(m['name'] == args.model for m in metadata['ollama_models']['models']):
            raise ValueError(f'Model not installed: {args.model}')
    except Exception as exc:
        metadata['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        save(out / 'metadata.json', metadata)
        print(f'FAIL: {exc}', flush=True)
        return 1
    save(out / 'metadata.json', metadata)
    replies = {}
    if args.reuse_classifications:
        model = next(m for m in metadata['ollama_models']['models'] if m['name'] == args.model)
        replies = classification_replies(args.reuse_classifications, settings, model['digest'])
        metadata['classification_replay'] = {'source': str(args.reuse_classifications.resolve()),
                                             'metadata_sha256': sha256(args.reuse_classifications / 'metadata.json'),
                                             'available_replies': len(replies)}
        save(out / 'metadata.json', metadata)
        print(f'Explicit classification reuse: {len(replies)} exact requests; all writing remains live', flush=True)
    rows = []
    for index, item in enumerate(items, 1):
        case_id = item.get('id', item.get('date'))
        if not isinstance(case_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', case_id):
            raise ValueError(f'Unsafe case ID: {case_id!r}')
        case_out = out / case_id
        output, error = None, None
        try:
            with PipelineRun(case_out, settings=settings, responses=replies) as run:
                output = generate(item, run)
                run.finish(output)
        except Exception as exc:
            error = {'type': type(exc).__name__, 'message': str(exc)}
        result = evaluate(item, output)
        if error:
            result['reasons'].append(f"{error['type']}: {error['message']}")
            result['passed'] = False
        row = {'id': case_id, 'output': output, 'error': error,
               'reused_classifications': run.client.reused, 'fresh_model_calls': run.client.fresh, **result}
        rows.append(row)
        save(case_out / 'evaluation.json', row)
        # Incremental checkpoint survives interruption before the whole batch completes.
        save(out / 'progress.json', {'completed': len(rows), 'total': len(items), 'rows': rows})
        print(f"[{index}/{len(items)}] {'PASS' if row['passed'] else 'FAIL'} {case_id}: "
              + ('; '.join(row['reasons']) or 'all checks passed'), flush=True)
        if isinstance(output, str):
            print(output + '\n', flush=True)
    summary = summarize(rows)
    summary.update(reused_classifications=sum(r['reused_classifications'] for r in rows),
                   fresh_model_calls=sum(r['fresh_model_calls'] for r in rows))
    summary.update(problem='HW1 ' + problem, backend='local Ollama', model=args.model, rows=rows)
    save(out / 'results.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}, ensure_ascii=False, indent=2), flush=True)
    print(f'Results: {out / "results.json"}', flush=True)
    return 0 if summary['passed'] else 1
