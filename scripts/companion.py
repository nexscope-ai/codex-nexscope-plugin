#!/usr/bin/env python3
"""Launch only the reviewed standalone CLI in this plugin's private environment."""
import email
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'b78bcf460113eacdfa5af2f5d5489d4ad8665254'
GUIDANCE = ('Companion unavailable or unverified. Keep the original nexscope installation. '
            'Restore the reviewed wheel listed in .codex-plugin/companion.json, then run '
            'python -I <plugin-root>/scripts/install_companion.py --wheelhouse <absolute-offline-wheelhouse>. '
            'No package is downloaded automatically.')


def verified_wheel(root=ROOT):
    manifest = json.loads((root / '.codex-plugin/companion.json').read_text(encoding='utf-8'))
    expected = dict(schemaVersion=1, distribution='nexscope-cli', module='nexscope_cli',
                    version='0.1.1', license='Apache-2.0', sourceRevision=REVISION,
                    repository='https://github.com/nexscope-ai/nexscope-cli',
                    wheel='runtime/companion/nexscope_cli-0.1.1-py3-none-any.whl')
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError('Manifest identity mismatch')
    wheel = root / expected['wheel']
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != manifest['sha256']:
        raise ValueError('Wheel digest mismatch')
    with zipfile.ZipFile(wheel) as archive:
        metadata = email.message_from_bytes(archive.read('nexscope_cli-0.1.1.dist-info/METADATA'))
        if (metadata['Name'], metadata['Version'], metadata['License-Expression']) != ('nexscope-cli', '0.1.1', 'Apache-2.0'):
            raise ValueError('Wheel distribution/license mismatch')
        for path in ('nexscope_cli/workflows/compare.py', 'nexscope_cli/workflows/product-comparison.md',
                     'nexscope_cli/core/auth.py', 'nexscope_cli-0.1.1.dist-info/licenses/LICENSE'):
            archive.getinfo(path)
    return wheel, manifest


def environment_python(root=ROOT):
    return (root / 'runtime/companion/.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')).absolute()


# Verify installed bytes before importing the same-named module; -I ignores host source paths.
CHECK_AND_RUN = r'''
import email, hashlib, json, pathlib, sys, sysconfig, zipfile
wheel, digest, prefix = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
args = sys.argv[4:]
try:
    if pathlib.Path(sys.prefix).resolve() != prefix.resolve(): raise ValueError()
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != digest: raise ValueError()
    site = pathlib.Path(sysconfig.get_paths()['purelib'])
    with zipfile.ZipFile(wheel) as archive:
        names = {n for n in archive.namelist() if n.startswith('nexscope_cli/') and not n.endswith('/')}
        for name in names:
            if (site / name).read_bytes() != archive.read(name): raise ValueError()
        installed = {p.relative_to(site).as_posix() for p in (site / 'nexscope_cli').rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
        if installed != names: raise ValueError()
        metadata = site / 'nexscope_cli-0.1.1.dist-info/METADATA'
        if metadata.read_bytes() != archive.read('nexscope_cli-0.1.1.dist-info/METADATA'): raise ValueError()
    if args == ['--verify-companion']:
        print(json.dumps({'status':'VERIFIED','sourceRevision':'b78bcf460113eacdfa5af2f5d5489d4ad8665254','sha256':digest}))
    else:
        from nexscope_cli.main import main
        sys.argv = ['nexscope', *args]
        sys.exit(main())
except (OSError, ValueError, KeyError, zipfile.BadZipFile):
    print(json.dumps({'status':'ERROR','message':'Companion installed identity mismatch. Restore the reviewed offline environment; no fallback was attempted.'}))
    sys.exit(1)
'''


def source_arguments(arguments):
    args = list(arguments)
    command = 2 if args[:1] == ['--api-base'] else 1 if args and args[0].startswith('--api-base=') else 0
    if args[command:command + 2] == ['auth', 'login']:
        for option, value in [('--source-client', 'codex-plugin'), ('--source-channel', 'marketplace'), ('--source-entrypoint', 'plugin')]:
            if not any(arg == option or arg.startswith(option + '=') for arg in args):
                args += [option, value]
    return args


def launch(arguments, root=ROOT):
    try:
        wheel, manifest = verified_wheel(root)
        python = environment_python(root)
        if not python.is_file():
            raise ValueError('No companion environment')
        return subprocess.run([str(python), '-I', '-c', CHECK_AND_RUN, str(wheel), manifest['sha256'],
                               str(python.parent.parent), *source_arguments(arguments)], check=False).returncode
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        print(json.dumps({'status': 'ERROR', 'message': GUIDANCE}))
        return 1


if __name__ == '__main__':
    sys.exit(launch(sys.argv[1:]))
