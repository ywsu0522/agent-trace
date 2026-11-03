"""Run original deterministic cases with persistent pytest evidence."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from agent_trace.paths import asset_root


SOURCES = {
    'bm25': ['pipelines/bm25.py', 'tokenizer.py'],
    'email_qa': ['pipelines/email_qa.py', 'pipelines/email_retrieval.py'],
    'tool_registry': ['agent/registry.py', 'types.py'],
    'agent_loop': ['agent/session.py', 'agent/registry.py', 'agent/protocol.py', 'tokens.py', 'types.py', 'errors.py'],
}


def main(problem, suite, expected, argv=None, *, uses_archive=False):
    root = asset_root()
    parser = argparse.ArgumentParser(description=f'HW1 {problem}: deterministic tests, no model server')
    parser.add_argument('--mode', choices=('deterministic',), default='deterministic')
    parser.add_argument('--out', type=Path, help='New output directory for log, JUnit XML and summary')
    if uses_archive:
        parser.add_argument('--emails', type=Path, default=root / '.cache/emails.jsonl')
    args = parser.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = (args.out or root / 'runs' / f'{problem}-deterministic-{stamp}').resolve()
    out.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-m', 'pytest', str(root / f'tests/test_{suite}.py'),
               '-vv', '--capture=tee-sys', '--junitxml', str(out / 'junit.xml'),
               '-o', 'junit_logging=all', '--basetemp', str(out / 'tmp')]
    sources = [root / 'agent_trace' / name for name in SOURCES[suite]]
    sources += [root / f'scripts/test{problem[1:]}.py', Path(__file__).resolve(),
                root / f'tests/test_{suite}.py', root / 'tests/conftest.py',
                root / 'tests/scripted_lm.py', root / 'tests/fixture_tools.py', root / 'tests/helpers.py']
    if uses_archive:
        command += ['--hw1-emails', str(args.emails.resolve())]
        sources += [root / 'tests/fixtures/bm25_queries.json', root / 'datasets/email-source.json']
    metadata = {'problem': problem, 'mode': 'deterministic', 'expected_cases': expected,
                'command': command, 'started_at': datetime.now(timezone.utc).isoformat(),
                'python': sys.version, 'network': 'blocked by offline_only fixture',
                'source_sha256': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    if uses_archive:
        from agent_trace.data import file_hash
        metadata['emails'] = str(args.emails.resolve())
        metadata['emails_sha256'] = file_hash(args.emails) if args.emails.is_file() else None
    def save(name, value):
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    save('metadata.json', metadata)
    print(f'{problem}: running {expected} deterministic cases; evidence: {out}', flush=True)
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    with (out / 'pytest.log').open('w', encoding='utf-8') as log:
        completed = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
    cases = []
    if (out / 'junit.xml').is_file():
        for case in ET.parse(out / 'junit.xml').iter('testcase'):
            status = next((tag for tag in ('failure', 'error', 'skipped') if case.find(tag) is not None), 'passed')
            cases.append({'name': case.attrib['name'], 'status': status, 'seconds': float(case.get('time', 0))})
    counts = {status: sum(case['status'] == status for case in cases) for status in ('passed', 'failure', 'error', 'skipped')}
    passed = completed.returncode == 0 and len(cases) == expected and counts['passed'] == expected
    result = {'problem': problem, 'passed': passed, 'exit_code': completed.returncode,
              'expected_cases': expected, 'total': len(cases), 'counts': counts, 'cases': cases}
    save('results.json', result)
    print('\n'.join((out / 'pytest.log').read_text(encoding='utf-8').splitlines()[-8:]))
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, indent=2))
    return 0 if passed else 1
