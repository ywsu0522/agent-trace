"""Inspect the actual Git index before publishing; never print secret values."""

import ast
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def audit():
    entries = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).split(b'\0')
    names = [os.fsdecode(p) for p in entries if p]
    failures, total = [], 0
    forbidden_parts = {'.git', '.cache', '.venv', '__pycache__', 'legacy', 'node_modules', 'dist', 'cs329z_hw1', 'agent_trace_lab'}
    patterns = [rb'gh[pousr]_[A-Za-z0-9]{30,}', rb'sk-[A-Za-z0-9]{30,}',
                rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----']
    for name in names:
        path = Path(name)
        if (any(p in forbidden_parts for p in path.parts) or path.suffix.lower() in {'.pdf', '.zip', '.gz', '.tar', '.pyc'}
                or path.name in {'.env', 'test_legacy_profile.py', 'legacy_profile.py', 'rerun_legacy_doc_qa.py', 'package_repo.py'}):
            failures.append({'path': name, 'reason': 'excluded publication material'})
        payload = (ROOT / path).read_bytes()
        total += len(payload)
        if any(re.search(pattern, payload) for pattern in patterns):
            failures.append({'path': name, 'reason': 'possible credential; value withheld'})
        if name.startswith('agent_trace/') and path.suffix == '.py':
            for node in ast.walk(ast.parse(payload.decode('utf-8'))):
                imports = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) else []
                if any(n.startswith(('cs329z_hw1', 'agent_trace_lab')) for n in imports):
                    failures.append({'path': name, 'reason': 'non-independent import'})
    report = {'files': len(names), 'bytes': total, 'failures': failures}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures or not names:
        raise SystemExit(1)
    return report


if __name__ == '__main__':
    audit()
