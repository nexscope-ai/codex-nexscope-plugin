#!/usr/bin/env python3
"""Check the Git candidate for accidental local state and untranslated source."""
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
paths = set(filter(None, subprocess.check_output(
    ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root,
).decode().split('\0')))
failures = []
secret = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bnk-[A-Za-z0-9]{32,}\b|\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_]{20,}\b')
for name in sorted(paths):
    path = root / name
    if path.is_symlink():
        failures.append((name, 'symlink'))
        continue
    if path.relative_to(root).parts[0] == 'nexscope' or any(part in {'.venv', '__pycache__', 'build', 'dist'} or part.startswith('.env') for part in path.relative_to(root).parts):
        failures.append((name, 'local-only file'))
    try:
        text = path.read_text(encoding='utf-8')
    except UnicodeError:
        continue
    if re.search(r'[\u3400-\u9fff\uf900-\ufaff]', text):
        failures.append((name, 'untranslated source'))
    if secret.search(text):
        failures.append((name, 'credential pattern; value withheld'))
if failures:
    for name, reason in failures:
        print(f'{name}: {reason}')
    raise SystemExit(1)
print(f'PASS: {len(paths)} publication files; no untranslated source, local state or credential-pattern matches')
