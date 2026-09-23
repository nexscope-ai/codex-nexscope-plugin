#!/usr/bin/env python3
"""Package the reviewed local wheel with the portable Codex skill."""
from pathlib import Path
import subprocess
import shutil
import zipfile
root = Path(__file__).resolve().parents[1]
shutil.rmtree(root / 'build', ignore_errors=True)
subprocess.run(['uv', 'build', '--wheel', '--out-dir', str(root / 'runtime')], cwd=root, check=True)
wheel = root / 'runtime/nexscope_cli-0.1.0-py3-none-any.whl'
assert wheel.is_file()
(root / 'dist').mkdir(exist_ok=True)
with zipfile.ZipFile(root / 'dist/codex-nexscope-plugin-0.1.0.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for folder in ('.codex-plugin', 'skills', 'assets', 'runtime'):
        for path in sorted((root / folder).rglob('*')):
            if path.is_file() and (folder != 'runtime' or path == wheel):
                z.write(path, path.relative_to(root))
    for name in ('README.md', 'LICENSE'):
        z.write(root / name, name)
print(root / 'dist/codex-nexscope-plugin-0.1.0.zip')
