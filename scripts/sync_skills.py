"""Vendor declared skill resources from a reviewed checkout; never run upstream code."""
import ast
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from public_copy import clean


def sync(source, target, selected=None):
    previous = json.loads((target / 'catalog.json').read_text(encoding='utf-8')) if selected else {}
    catalog = dict(previous.get('skills', {}))
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    seen = set()
    translations = json.loads(Path(__file__).with_name("english_reference_replacements.json").read_text())
    availability = json.loads(Path(__file__).with_name("skill_availability.json").read_text())
    for guide in sorted(source.glob('ecommerce-*/SKILL.md')):
        folder = guide.parent
        name = folder.name.removeprefix('ecommerce-')
        if selected and name not in selected:
            continue
        seen.add(name)
        manifest_path = folder / 'manifest.json'
        if not manifest_path.exists():
            manifest_path = folder / '.nexscope-manifest.json'
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        files = {'SKILL.md'}
        declared = manifest.get('files', [])
        if not isinstance(declared, list):
            raise ValueError(f'Invalid file list: {folder.name}')
        for item in declared:
            if isinstance(item, dict):
                item = item.get('path', '')
            f = (folder / item).resolve()
            if not f.is_relative_to(folder.resolve()):
                raise ValueError(f'Unsafe file: {folder.name}')
            if f.is_dir():
                files.update(x.relative_to(folder.resolve()).as_posix() for x in f.rglob('*') if x.is_file())
            elif f.is_file():
                files.add(f.relative_to(folder.resolve()).as_posix())
        # Older manifests omit companion scripts. Include source/resources, not run data.
        for dirname in ['scripts', 'references', 'assets']:
            for f in (folder / dirname).rglob('*'):
                if f.is_file(): files.add(f.relative_to(folder).as_posix())
        if (folder / 'requirements.txt').is_file(): files.add('requirements.txt')
        dest = target / 'skills' / name
        if not dest.resolve().is_relative_to((target / 'skills').resolve()):
            raise ValueError('Destination escapes the bundled skills directory')
        if dest.exists(): shutil.rmtree(dest)
        entrypoints = []
        hashes = {}
        for relative in sorted(files):
            f = folder / relative
            if f.is_symlink() or not f.resolve().is_relative_to(folder.resolve()):
                raise ValueError(f'Unsafe resource: {f.name}')
            if any(x in {'__pycache__', 'node_modules', '.git', '.cache', 'runs', 'output', 'outputs'} or x.startswith('tmp-') for x in f.parts): continue
            if f.suffix in {'.pyc', '.log', '.zip'} or f.name.startswith('.env'): continue
            data = f.read_bytes()
            if f.suffix == '.md':
                text = data.decode('utf-8')
                original = text
                for term, replacement in sorted(translations.items(), key=lambda item: -len(item[0])):
                    text = text.replace(term, replacement)
                if text != original:
                    text += '\n> Localization note: Example response strings and observed messages are translated into English. Actual provider responses may use their original locale. Request enums shown as JSON Unicode escapes must be sent with their decoded values.\n'
                text = clean(text)
                text = '\n'.join(line.rstrip() for line in text.splitlines()).rstrip() + '\n'
                data = text.encode('utf-8')
            if f.suffix == '.py':
                data = ('\n'.join(line.rstrip() for line in data.decode('utf-8').splitlines()).rstrip() + '\n').encode('utf-8')
                tree = ast.parse(data)
                if any(isinstance(x, ast.If) and '__name__' in ast.unparse(x.test) for x in tree.body):
                    entrypoints.append(relative)
            output = dest / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
            hashes[relative] = hashlib.sha256(data).hexdigest()
        blocked = availability.get(name)
        if not entrypoints and not blocked:
            raise ValueError(f'Missing runnable entrypoint: {name}; declare its prerequisites before packaging')
        catalog[name] = {'source': folder.name, 'description': clean(manifest.get('description', name)),
                         'scripts': entrypoints, 'files': hashes, 'available': blocked is None,
                         'version': manifest.get('version'), 'sourceRevision': revision}
        if blocked:
            catalog[name]['unavailable'] = blocked
    if selected and seen != set(selected):
        raise ValueError('Missing requested skills: ' + ', '.join(sorted(set(selected) - seen)))
    result = {'source': 'https://github.com/nexscope-ai/nexscope-ecommerce-skills',
              'revision': previous.get('revision', revision), 'skills': catalog}
    if selected:
        update = {'revision': revision, 'skills': sorted(seen)}
        result['scopedUpdates'] = [item for item in previous.get('scopedUpdates', []) if item != update] + [update]
    (target / 'catalog.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'Vendored {len(seen)} selected skills at {revision}; catalog contains {len(catalog)} skills')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--skills', nargs='+', help='Update only these published skill names; preserve other entries')
    args = parser.parse_args()
    sync(Path(args.source).resolve(), Path(__file__).resolve().parents[1] / 'cli/nexscope_cli', args.skills)
