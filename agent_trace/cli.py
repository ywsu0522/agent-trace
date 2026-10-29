"""Run agents with automatic path reports; optionally curate research studies."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

from agent_trace.paths import asset_root
from agent_trace.execution import execute, plan


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def register(args):
    root = asset_root()
    manifest_path = Path(args.manifest or Path.cwd() / 'studies/d06/manifest.json').resolve()
    manifest = load(manifest_path)
    folder = Path(args.folder).resolve()
    entry = load(folder / 'manifest-entry.json')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', entry['id']):
        raise ValueError('Run ID must contain only letters, numbers, underscores and hyphens')
    if any(r['id'] == entry['id'] for r in manifest['runs']):
        raise ValueError('Run already registered; existing evidence is immutable')
    record = manifest_path.parent / 'record'
    for key, sub, suffix in [('source', 'evidence', '.jsonl'), ('metadata', 'metadata', '.json'), ('result', 'metadata', '.result.json')]:
        source = (folder / entry[key]).resolve()
        if not source.is_relative_to(folder):
            raise ValueError('Evidence paths must stay within the run folder')
        target = record / sub / (entry['id'] + suffix)
        if target.exists():
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        entry[key] = target.relative_to(manifest_path.parents[2]).as_posix()
    if (folder / 'runtime-source').is_dir():
        target = record / 'runtime' / entry['id']
        if target.exists():
            raise FileExistsError(target)
        shutil.copytree(folder / 'runtime-source', target)
        entry['runtime_snapshot'] = target.relative_to(manifest_path.parents[2]).as_posix()
    entry['label'] = args.label or entry['label']
    if not any(s['id'] == 'new-runs' for s in manifest['stages']):
        manifest['stages'].append({'id': 'new-runs', 'title': '新增研究執行', 'hypothesis': '請在實驗前記錄假設。',
                                  'change': '新實驗條件請由研究者填寫。',
                                  'compare': [entry['id'], entry['id']], 'observations': [],
                                  'interpretation': '尚未填寫研究者解讀。', 'pins': []})
    manifest['runs'].append(entry)
    write_json(manifest_path, manifest)
    print(f'Registered {entry["id"]}; rebuild the notebook to inspect it.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('build', help='Rebuild the offline study; no model calls')
    build.add_argument('--manifest', type=Path)
    build.add_argument('--out', type=Path)
    report = commands.add_parser('report', help='Build compact reports from a run folder or raw JSONL; no model calls')
    report.add_argument('source', type=Path)
    report.add_argument('--out', type=Path)
    report.add_argument('--kind', choices=['full', 'probe', 'replay'])
    report.add_argument('--expected-answer', action='append')
    report.add_argument('--batch', action='store_true', help='Import all case logs in an archived batch results.json')
    prepare = commands.add_parser('prepare-data', help='Verify and unpack the optional external email corpus')
    prepare.add_argument('--archive', type=Path)
    prepare.add_argument('--download', action='store_true')
    prepare.add_argument('--destination', type=Path, default=Path('.cache/emails.jsonl'))
    for name in ('run', 'replay', 'reproduce'):
        command = commands.add_parser(name, help='Run a question or named task with automatic reports' if name == 'run' else 'Replay one decision without executing tools')
        if name == 'replay':
            command.add_argument('run_id', nargs='?')
            command.add_argument('--turn', type=int, default=4)
            command.add_argument('--request', type=Path, help='A saved messages JSON; does not need a study manifest')
            command.add_argument('--manifest', type=Path)
        else:
            command.add_argument('question', nargs='?', help='Any user question; omit to use --task (default d06)')
            command.add_argument('--probe', action='store_true')
        command.add_argument('--task', help='Named task d01–d20, or a task JSON file')
        command.add_argument('--expected-answer', action='append', help='Optional exact accepted substring; repeat for alternatives')
        command.add_argument('--agent', choices=['current', 'baseline'], default='current')
        command.add_argument('--env')
        command.add_argument('--system', type=Path)
        command.add_argument('--model')
        command.add_argument('--base-url', default='http://127.0.0.1:11434')
        command.add_argument('--timeout', type=int, default=600)
        command.add_argument('--max-turns', type=int)
        command.add_argument('--docs', type=Path)
        command.add_argument('--emails', type=Path)
        command.add_argument('--out', type=Path)
        command.add_argument('--trace', action='store_true')
        command.add_argument('--dry-run', action='store_true')
    registration = commands.add_parser('register', help='Copy a fresh run into the permanent study evidence')
    registration.add_argument('folder', type=Path)
    registration.add_argument('--manifest', type=Path)
    registration.add_argument('--label')
    args = parser.parse_args(argv)
    try:
        if args.command == 'build':
            from agent_trace.notebook import build as build_notebook
            root = asset_root()
            build_notebook((args.manifest or root / 'studies/d06/manifest.json').resolve(),
                           (args.out or Path.cwd() / 'studies/d06/record').resolve(), repo=root)
        elif args.command == 'prepare-data':
            from agent_trace.data import prepare_email
            print(json.dumps(prepare_email(args.destination, args.archive, args.download), indent=2))
        elif args.command == 'register':
            register(args)
        elif args.command == 'report':
            from agent_trace.reports import report_path, report_batch
            if args.batch:
                report_batch(args.source, args.out)
            else:
                report_path(args.source, args.out, kind=args.kind, expected_answers=args.expected_answer)
        elif args.command == 'reproduce':
            from agent_trace.data import prepare_email
            config = plan(args)
            if not args.dry_run and config['mode'] == 'full':
                prepare_email(config['emails_path'], download=True)
            return execute(args)
        else:
            return execute(args)
        return 0
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
