#!/usr/bin/env python3
"""Offline regression of the packaged companion and unchanged legacy entry."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch
import venv

from companion import ROOT, environment_python, launch, source_arguments, verified_wheel


def run(command, expected=0, environment=None):
    result = subprocess.run(list(map(str, command)), env=environment, capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
    assert result.returncode == expected, result.stdout + result.stderr
    return result.stdout


def cli(*arguments, expected=0, environment=None):
    return json.loads(run([sys.executable, '-I', ROOT / 'scripts/companion.py', *arguments], expected, environment))


wheel, manifest = verified_wheel()
assert cli('--verify-companion')['sha256'] == manifest['sha256']
assert cli('get-skills', 'product-comparison')['ruleSource'] == 'nexscope_cli.workflows.compare'
assert source_arguments(['auth', 'login'])[-6:] == ['--source-client', 'codex-plugin', '--source-channel', 'marketplace', '--source-entrypoint', 'plugin']
assert source_arguments(['auth', 'login', '--source-client', 'claude-code']).count('--source-client') == 1
assert '--source-client' not in source_arguments(['auth', 'login', '--source-client=claude-code'])
assert source_arguments(['--api-base=https://fixture.invalid', 'auth', 'login'])[-6:] == source_arguments(['auth', 'login'])[-6:]
refused = run([sys.executable, '-I', ROOT / 'scripts/install_companion.py', '--wheelhouse', ROOT / 'runtime/companion/wheels'], expected=1)
assert 'already exists' in refused

with tempfile.TemporaryDirectory(prefix='nexscope-companion-check-') as temporary:
    work = Path(temporary)
    # A same-named/versioned proprietary wheel must fail even if its digest is supplied.
    fake = work / 'fake'
    (fake / '.codex-plugin').mkdir(parents=True)
    fake_wheel = fake / manifest['wheel']
    fake_wheel.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / 'runtime/nexscope_cli-0.1.1-py3-none-any.whl', fake_wheel)
    tampered = dict(manifest, sha256=hashlib.sha256(fake_wheel.read_bytes()).hexdigest())
    (fake / '.codex-plugin/companion.json').write_text(json.dumps(tampered))
    with patch('companion.subprocess.run', side_effect=AssertionError('Unverified code launched')):
        assert launch(['--version'], fake) == 1
        shutil.copyfile(wheel, fake_wheel)
        assert launch(['--version'], fake) == 1  # Stale digest.
        tampered = dict(manifest, sourceRevision='0' * 40)
        (fake / '.codex-plugin/companion.json').write_text(json.dumps(tampered))
        assert launch(['--version'], fake) == 1
        (fake / '.codex-plugin/companion.json').write_text(json.dumps(manifest))
        assert launch(['--version'], fake) == 1  # No private environment: no fallback.

    uv = shutil.which('uv')
    assert uv, 'The documented uv prerequisite is needed for the isolated legacy install check.'
    legacy = fake / 'runtime/companion/.venv'
    venv.EnvBuilder(with_pip=False, symlinks=os.name != 'nt').create(legacy)
    legacy_python = legacy / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    run([uv, 'pip', 'install', '--offline', '--no-index', '--no-deps', '--python', legacy_python,
         ROOT / 'runtime/nexscope_cli-0.1.1-py3-none-any.whl'])
    assert launch(['--version'], fake) == 1  # Valid wheel, wrong same-version installed package.
    legacy_guide = [legacy_python, '-I', '-c', 'from nexscope_cli.main import guide; import json; print(json.dumps(guide("core")))']
    before = run(legacy_guide)
    assert 'product-comparison' not in json.loads(before).get('workflows', {})
    # Both installation orders coexist: neither execution changes the other package.
    hostile = dict(os.environ, PYTHONPATH=str(ROOT / 'cli'), PYTHONHOME=str(legacy), NEXSCOPE_API_KEY='fixture-env-B')
    assert cli('get-skills', 'product-comparison', environment=hostile)['ruleSource'].endswith('workflows.compare')
    assert run(legacy_guide) == before
    assert cli('doctor', '--offline')['status'] == 'READY_LOCAL'
    assert run(legacy_guide) == before

    plan = cli('workflow', 'compare', '--asins', 'B000000001,B000000002,B000000003', '--dry-run')
    assert plan['status'] == 'PLANNED'
    direct = work / 'direct'
    complete = cli('workflow', 'compare', '--asins', 'B000000001,B000000002,B000000003',
                   '--execute', '--mock', 'complete', '--format', 'all', '--out', str(direct))
    assert complete['status'] == 'COMPLETE' and complete['budget']['requestsSent'] == 3
    partial = cli('workflow', 'compare', '--asins', 'B000000001,B000000002,B000000003',
                  '--execute', '--mock', 'partial', '--out', str(work / 'partial'), expected=1)
    assert partial['status'] == 'PARTIAL' and partial['budget']['automaticRetries'] == 0
    candidates = work / 'candidates'
    selection = cli('workflow', 'compare', '--keyword', 'lamp', '--max-calls', '3', '--execute',
                    '--mock', 'complete', '--out', str(candidates))
    assert selection['status'] == 'CANDIDATES_READY'
    resumed = cli('workflow', 'compare', '--resume', str(candidates), '--select-asins', 'B000000001,B000000002',
                  '--execute', '--mock', 'complete', '--out', str(work / 'resumed'))
    assert resumed['status'] == 'COMPLETE'
    assert resumed['budget']['requestsSent'] == 3 and resumed['budget']['importedRequests'] == 1
    rows = [{'product_id': 'one', 'title': 'Fictional one'}, {'product_id': 'two', 'title': 'Fictional two'}]
    source_json, source_csv = work / 'input.json', work / 'input.csv'
    source_json.write_text(json.dumps(rows))
    source_csv.write_text('product_id,title\none,Fictional one\ntwo,Fictional two\n')
    for source in (source_json, source_csv):
        result = cli('report', 'compare', '--input', str(source), '--format', 'csv',
                     '--out', str(work / (source.suffix[1:] + '-report.csv')))
        assert result['rows'] == 2 and result['sourceType'] == 'user_import'

# Test the selected auth source with fictional in-memory identities; never open keyring.
run([environment_python(), '-I', '-c', '''
from nexscope_cli.core.auth import resolve_auth
from nexscope_cli.core.errors import AuthRequired
env={'NEXSCOPE_API_KEY':'fixture-B','NEXSCOPE_PROXY_BASE':'https://fixture.invalid'}
def forbidden(): raise AssertionError('Read browser credentials')
b=resolve_auth('env-api-key',environment=env,credential_loader=forbidden)
assert b.authorization()=='Bearer fixture-B'
a=resolve_auth('browser-account',environment=env,credential_loader=lambda:{'apiKey':'fixture-A'})
assert a.authorization()=='Bearer fixture-A' and a.cache_partition!=b.cache_partition
for mode,environment,loader in [('env-api-key',{},forbidden),('browser-account',env,lambda:None)]:
    try: resolve_auth(mode,environment=environment,credential_loader=loader)
    except AuthRequired: pass
    else: raise AssertionError('Unexpected fallback')
'''])
print('PASS: companion identity/tamper/legacy-install isolation, dry-run, direct/partial/resume, CSV/JSON local reports, auth-source no fallback')
