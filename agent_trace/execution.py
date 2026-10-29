"""Task-independent Ollama execution and fixed-request decision replay."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import shutil
import sys

from agent_trace.paths import asset_root

RUNTIME_VERSION = '0.2.0'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def plan(args):
    from agent_trace.data import file_hash
    root = asset_root()
    profile = load(root / 'configs/agents' / f'{args.agent}.json')
    environment = args.env or profile['environment']
    versions = load(root / 'configs/prompts/versions.json')
    declared = next((v for v in versions if v['id'] == environment), None)
    if declared is None and args.system is None:
        raise ValueError(f'Unknown environment: {environment}; use --system for a new condition')
    system_path = args.system or root / 'configs/prompts' / f'{environment}.system.txt'
    system = Path(system_path).read_text(encoding='utf-8')
    system_hash = hashlib.sha256(system.encode('utf-8')).hexdigest()
    if args.system is None and system_hash != declared['sha256']:
        raise ValueError('Archived prompt snapshot changed; create a new --system file')
    if args.system is None and environment == profile['environment'] and system_hash != profile['system_sha256']:
        raise ValueError('Pinned prompt snapshot changed; create a new --system file')
    question = getattr(args, 'question', None)
    if question and args.task:
        raise ValueError('Use a question OR --task; do not score a new question with another task\'s answer')
    task = {}
    standalone_replay = args.command == 'replay' and args.request and not args.task
    if not question and not standalone_replay:
        task_id = args.task or 'd06'  # backward-compatible convenience, not a runtime assumption
        path = Path(task_id)
        if not path.is_file():
            if '/' in task_id or '\\' in task_id or task_id in ('.', '..'):
                raise FileNotFoundError(f'Task file not found: {task_id}')
            path = root / 'configs/tasks' / f'{task_id}.json'
        task = load(path)
        question = task['question']
    expected = args.expected_answer if args.expected_answer is not None else task.get('expected_answers', [])
    history = None
    if args.command == 'replay':
        if args.request:
            history = args.request.resolve()
        else:
            if not args.run_id:
                raise ValueError('replay needs --request FILE or an archived run ID')
            manifest_path = args.manifest or root / 'studies/d06/manifest.json'
            manifest = load(manifest_path)
            if not any(r['id'] == args.run_id for r in manifest['runs']):
                raise ValueError(f'Unknown archived run: {args.run_id}')
            history = manifest_path.parent / 'record/traces' / args.run_id / f'turn-{args.turn:02d}.request.json'
        if args.turn < 1:
            raise ValueError('Turn must be >= 1')
        messages = load(history)
        if not isinstance(messages, list) or not messages or messages[0].get('role') != 'system':
            raise ValueError('Replay request must be a messages list starting with a system message')
        messages[0] = {'role': 'system', 'content': system}
        if standalone_replay:
            saved_metadata = history.parent / 'metadata.json'
            recorded_question = load(saved_metadata).get('run_context', {}).get('question') if saved_metadata.is_file() else None
            question = recorded_question or next((m['content'] for m in messages if m.get('role') == 'user'), '')
        mode = 'replay'
    else:
        messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': question}]
        mode = 'probe' if args.probe else 'full'
    docs_dir = Path(args.docs or root / task.get('docs', profile['documents'])).resolve()
    emails = Path(args.emails or Path.cwd() / '.cache/emails.jsonl').resolve()
    return {'mode': mode, 'system': system, 'messages': messages, 'question': question,
            'task': task.get('id'), 'expected_answers': expected,
            'document_result_budget': task.get('document_result_budget'),
            'system_file': str(Path(system_path).resolve()), 'system_sha256': system_hash,
            'system_file_sha256': file_hash(system_path), 'history_file': str(history) if history else None,
            'docs_dir': str(docs_dir), 'emails_path': str(emails),
            'model': args.model or profile['model'], 'temperature': profile['temperature'],
            'think': profile['think'], 'num_ctx': profile['num_ctx'],
            'max_turns': args.max_turns if args.max_turns is not None else profile['max_turns'],
            'environment': environment if args.system is None else 'custom-' + system_hash[:10],
            'agent_profile': profile, 'runtime_version': RUNTIME_VERSION}


def execute(args):
    from agent_trace.agent.session import AgentSession
    from agent_trace.data import Corpus, file_hash
    from agent_trace.llm_ollama import OllamaClient
    from agent_trace.recording import RecordedClient
    from agent_trace.runtime import build_registry, catalogue_from_system
    from agent_trace.tracing import TraceRun
    from agent_trace.types import AgentConfig

    config = plan(args)
    catalogue = catalogue_from_system(config['system'])
    if args.system is None and config['environment'] == config['agent_profile']['environment']:
        sha = hashlib.sha256(json.dumps(catalogue, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if sha != config['agent_profile']['tool_catalogue_sha256']:
            raise ValueError('Pinned tool descriptions or schemas changed; create a new research condition')
    if config['max_turns'] < 1:
        raise ValueError('max-turns must be >= 1')
    if args.dry_run:
        print(json.dumps({k: v for k, v in config.items() if k not in ('messages', 'system')}, ensure_ascii=False, indent=2))
        return 0
    corpus = Corpus(config['docs_dir'], config['emails_path'])
    if config['mode'] == 'full':
        names = {s['name'] for s in catalogue}
        if names.intersection(('read_doc', 'search_docs')):
            corpus.docs()
        if names.intersection(('search_emails', 'read_email', 'email_qa', 'daily_digest')) and not Path(config['emails_path']).is_file():
            raise FileNotFoundError('Full runs exposing email tools require the email corpus. Run prepare-data or supply --emails.')
    out = Path(args.out or Path.cwd() / 'runs' / ('run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))).resolve()
    settings = {k: v for k, v in config.items() if k not in ('messages', 'system')}
    metadata = {'settings': settings, 'dependency_versions': {'python': sys.version, 'jsonschema': package_version('jsonschema')}}
    options = {'model': config['model'], 'base_url': args.base_url, 'timeout': args.timeout,
               'temperature': config['temperature'], 'num_ctx': config['num_ctx'], 'think': config['think']}
    run = TraceRun(out, question=config['question'], metadata=metadata,
                   expected_answers=config['expected_answers'], kind=config['mode'], environment=config['environment'],
                   document_result_budget=config['document_result_budget'], trace=args.trace)
    try:
        with run:
            package = Path(__file__).resolve().parent
            run.metadata['source_hashes'] = {p.relative_to(package).as_posix(): file_hash(p) for p in sorted(package.rglob('*.py'))}
            run.metadata['dataset_hashes'] = {p.name: file_hash(p) for p in sorted(Path(config['docs_dir']).glob('*.md'))}
            if config['mode'] == 'full' and Path(config['emails_path']).is_file():
                run.metadata['email_sha256'] = file_hash(config['emails_path'])
            for name in run.metadata['source_hashes']:
                target = out / 'runtime-source' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(package / name, target)
            run.metadata['runtime_snapshot'] = 'runtime-source'
            write_json(out / 'agent-profile.json', config['agent_profile'])
            (out / 'system.txt').write_text(config['system'], encoding='utf-8')
            write_json(out / 'initial-request.json', config['messages'])
            client = OllamaClient(**options)
            run.metadata['ollama_version'] = client._request('/api/version')
            run.metadata['ollama_tags'] = client._request('/api/tags')
            if not any(m['name'] == config['model'] for m in run.metadata['ollama_tags']['models']):
                raise ValueError(f'Model not installed: {config["model"]}')
            if args.command == 'reproduce':
                selected = next(m for m in run.metadata['ollama_tags']['models'] if m['name'] == config['model'])
                expected_digest = config['agent_profile']['model_digest']
                if config['model'] != config['agent_profile']['model'] or selected.get('digest') != expected_digest:
                    raise ValueError('Reproduction requires the pinned model name and digest. Pull '
                                     + config['agent_profile']['model'] + '; use run for other model conditions.')
            main = RecordedClient(run.recorder, 'agent', **options, json_mode=False)
            aux = run.observe(RecordedClient(run.recorder, 'aux', **options, json_mode=config['agent_profile']['aux_json_mode']), 'aux')
            if config['mode'] == 'full':
                session = AgentSession(main, build_registry(aux, corpus, config['system']),
                                       AgentConfig(max_turns=config['max_turns'], token_budget=config['agent_profile']['token_budget'], aux_lm=aux))
                session.messages[0]['content'] = config['system']
                run.send(session, config['question'])
            else:
                run.decision(main, deepcopy(config['messages']))
    finally:
        if run.result is not None:
            entry = {'id': out.name, 'label': out.name, 'kind': config['mode'], 'stage': 'new-runs',
                     'source': 'events.jsonl', 'metadata': 'metadata.json', 'result': 'result.json',
                     'notes': f'Independent runtime {RUNTIME_VERSION}; automatic facts in trace.html; research interpretation is separate.'}
            if args.command == 'replay':
                entry.update(source_turn=args.turn if not args.request else None,
                             history_from=args.run_id or config['history_file'])
            write_json(out / 'manifest-entry.json', entry)
            print(json.dumps({'output': str(out), **run.result}, ensure_ascii=False, indent=2))
    return 1 if run.result.get('error') else 0
