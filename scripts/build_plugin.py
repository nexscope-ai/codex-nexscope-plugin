#!/usr/bin/env python3
"""Package the reviewed local wheel with the portable Codex skill."""
from pathlib import Path
import subprocess
import shutil
import zipfile
import hashlib
import re
from companion import verified_wheel
root = Path(__file__).resolve().parents[1]
companion, _ = verified_wheel(root)
with zipfile.ZipFile(companion) as archive:
    allowed_hashes = set(re.findall(r'--hash=sha256:([0-9a-f]{64})', archive.read('nexscope_cli/dependencies.lock').decode()))
dependency_wheels = sorted((root / 'runtime/companion/wheels').glob('*.whl'))
assert dependency_wheels, 'Supply the reviewed offline dependency wheelhouse before packaging.'
assert all(hashlib.sha256(path.read_bytes()).hexdigest() in allowed_hashes for path in dependency_wheels), 'Unverified dependency wheel'
shutil.rmtree(root / 'build', ignore_errors=True)
subprocess.run(['uv', 'build', '--wheel', '--out-dir', str(root / 'runtime')], cwd=root, check=True)
wheel = root / 'runtime/nexscope_cli-0.1.1-py3-none-any.whl'
assert wheel.is_file()
(root / 'dist').mkdir(exist_ok=True)
destination = root / 'dist/codex-nexscope-plugin-0.1.1-companion-candidate.zip'
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as z:
    for folder in ('.codex-plugin', 'skills', 'assets', 'runtime'):
        for path in sorted((root / folder).rglob('*')):
            if path.is_file() and (folder != 'runtime' or path in [wheel, companion, *dependency_wheels]):
                z.write(path, path.relative_to(root))
    for name in ('README.md', 'LICENSE'):
        z.write(root / name, name)
    for name in ('companion.py', 'install_companion.py'):
        z.write(root / 'scripts' / name, 'scripts/' + name)
print(destination)
