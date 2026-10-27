#!/usr/bin/env python3
"""Explicit offline setup. Never replace a global CLI or an existing environment."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from companion import ROOT, GUIDANCE, environment_python, launch, verified_wheel


def install(wheelhouse):
    wheel, _ = verified_wheel()
    target = ROOT / 'runtime/companion/.venv'
    if target.exists():
        raise ValueError('Companion environment already exists; preserve it before an explicit offline upgrade or rollback.')
    if not wheelhouse.is_dir() or not list(wheelhouse.glob('*.whl')):
        raise ValueError('Supply an existing offline wheelhouse for this Python/platform, matching the wheel dependencies.lock.')
    uv = shutil.which('uv')
    if not uv:
        raise ValueError('Install the documented uv prerequisite separately; setup never downloads an installer.')
    venv.EnvBuilder(with_pip=False, symlinks=os.name != 'nt').create(target)
    python = environment_python()
    environment = dict(os.environ, UV_OFFLINE='1', UV_PYTHON_DOWNLOADS='never')
    with tempfile.TemporaryDirectory(prefix='nexscope-companion-') as temporary:
        requirements = Path(temporary) / 'dependencies.lock'
        with zipfile.ZipFile(wheel) as archive:
            requirements.write_bytes(archive.read('nexscope_cli/dependencies.lock'))
        base = [uv, 'pip', 'install', '--offline', '--no-index', '--python', str(python)]
        subprocess.run([*base, '--find-links', str(wheelhouse), '--require-hashes', '-r', str(requirements)], env=environment, check=True)
        subprocess.run([*base, '--no-deps', str(wheel)], env=environment, check=True)
    if launch(['--verify-companion']):
        raise ValueError('Installed companion failed verification.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheelhouse', type=Path, required=True)
    args = parser.parse_args()
    try:
        install(args.wheelhouse.resolve(strict=True))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        print(str(error) if isinstance(error, ValueError) else 'Offline companion setup failed.')
        print(GUIDANCE)
        sys.exit(1)
