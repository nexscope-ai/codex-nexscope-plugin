"""Independent, OS-keyring-backed Nexscope CLI. Never prints credentials."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from . import __version__

ROOT = Path(__file__).parent


class Failure(Exception):
    pass


class AuthRequired(Failure):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Failure('Redirect refused; check the API origin.')


def origin(value):
    p = urlsplit(value)
    if (p.scheme != 'https' and not (p.scheme == 'http' and p.hostname in ('localhost', '127.0.0.1'))) or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('', '/'):
        raise Failure('Use an HTTPS API origin (HTTP is allowed only on loopback).')
    return value.rstrip('/')


class Client:
    def __init__(self, base):
        self.base = origin(base)
        import keyring
        backend = keyring.get_keyring()
        # Fail closed: do not fall back to plaintext files or inherited API keys.
        module = type(backend).__module__
        if module not in ('keyring.backends.macOS', 'keyring.backends.Windows', 'keyring.backends.SecretService', 'keyring.backends.kwallet'):
            raise Failure('An OS credential store is required. Configure a supported keyring backend.')
        self.store = backend
        self.service = 'nexscope-cli:' + self.base

    def load(self, name):
        raw = self.store.get_password(self.service, name)
        return json.loads(raw) if raw else None

    def save(self, name, value):
        self.store.set_password(self.service, name, json.dumps(value))

    def clear(self, name):
        if self.load(name) is not None:
            self.store.delete_password(self.service, name)

    def api(self, path, body=None, authenticated=False):
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        if authenticated:
            credential = self.load('credential')
            if not credential:
                raise Failure('AUTH_REQUIRED: run nexscope auth login.')
            headers['Authorization'] = 'Bearer ' + credential['apiKey']
        req = Request(self.base + '/api/cli/' + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
        try:
            with build_opener(NoRedirect()).open(req, timeout=30) as response:
                result = json.load(response)
        except HTTPError as e:
            if e.code == 401 and authenticated:
                raise AuthRequired('AUTH_REQUIRED: reconnect with nexscope auth login.') from None
            raise Failure(f'HTTP {e.code}; request not retried.') from None
        except (URLError, TimeoutError):
            raise Failure('Network unavailable; request not retried.') from None
        if not isinstance(result, dict):
            raise Failure('Invalid API response.')
        if result.get('code') in (12001, 12003):
            raise AuthRequired('AUTH_REQUIRED: reconnect with nexscope auth login.')
        if result.get('code') != 0:
            raise Failure(f"API error {result.get('code')}; request not retried.")
        return result.get('data')

    def auth(self, action):
        if action == 'login':
            if self.load('credential'):
                try:
                    return self.api('account', authenticated=True)
                except AuthRequired:
                    self.clear('credential')
            pending = self.load('pending')
            import time
            if not pending or int(pending['expiresAt']) <= time.time() * 1000:
                pending = self.api('auth/start', {})
                self.save('pending', pending)
            return {k: v for k, v in pending.items() if k != 'pollSecret'}
        if action == 'poll':
            pending = self.load('pending')
            if not pending:
                return self.api('account', authenticated=True)
            body = {k: pending[k] for k in ('requestId', 'pollSecret')}
            value = self.api('auth/poll', body)
            if value['status'] == 'READY':
                self.save('credential', value)
                self.api('auth/poll', {**body, 'acknowledge': True})
                self.clear('pending')
                return self.api('account', authenticated=True)
            if value['status'] in ('DENIED', 'AUTH_EXPIRED', 'CONNECTED'):
                self.clear('pending')
            return {k: v for k, v in value.items() if k != 'apiKey'}
        if action == 'logout':
            if self.load('credential'):
                self.api('disconnect', {}, authenticated=True)
            self.clear('credential')
            self.clear('pending')
            return {'status': 'DISCONNECTED'}
        return self.api('account', authenticated=True)


def catalog():
    return json.loads((ROOT / 'catalog.json').read_text())['skills']


def guide(name):
    skills = catalog()
    if name == 'core':
        return {'version': __version__, 'skills': {k: v['description'] for k, v in skills.items() if v.get('available', True)},
                'unavailable': {k: v['unavailable'] for k, v in skills.items() if not v.get('available', True)},
                'execution': 'Read get-skills <name>; use run <name> [--script path] -- <script arguments>. Never run packaged scripts directly. Auth: login, user done, poll. Credits: account, link, user done, account.'}
    if name not in skills:
        raise Failure('Unknown skill; use get-skills core.')
    if not skills[name].get('available', True):
        return {'status': 'UNAVAILABLE', 'skill': name, **skills[name]['unavailable']}
    return {'skill': name, 'resourceDirectory': str(ROOT / 'skills' / name), 'scripts': skills[name]['scripts'], 'instructions': (ROOT / 'skills' / name / 'SKILL.md').read_text(),
            'execution': 'Replace python script.py with nexscope run ' + name + ' --script <listed script> -- . Relative input paths must be absolute because runs use isolated output directories.'}


def run(args, client):
    entry = catalog().get(args.skill)
    if not entry:
        raise Failure('Unknown skill.')
    if not entry.get('available', True):
        raise Failure('UNAVAILABLE: ' + entry['unavailable']['reason'])
    script = args.script or (entry['scripts'][0] if len(entry['scripts']) == 1 else None)
    if script not in entry['scripts']:
        raise Failure('Choose --script from get-skills output.')
    account = client.api('account', authenticated=True)
    credential = client.load('credential')
    folder = Path(args.output).resolve() / str(uuid.uuid4())
    folder.mkdir(parents=True, mode=0o700)
    env = dict(os.environ, NEXSCOPE_API_KEY=credential['apiKey'], NEXSCOPE_PROXY_BASE=client.base)
    env.pop('PYTHONPATH', None)
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    # No automatic replay: scripts may create reports, change ads, or consume credits.
    result = subprocess.run([sys.executable, str(ROOT / 'runner.py'), str(ROOT / 'skills' / args.skill / script), *arguments], cwd=folder, env=env, capture_output=True, text=True)
    output = (result.stdout + result.stderr).replace(credential['apiKey'], '[REDACTED]')
    (folder / 'output.txt').write_text(output)
    files = list(folder.rglob('*.json'))
    failures = []
    for path in files:
        try:
            raw = path.read_text()
            cleaned = raw.replace(credential['apiKey'], '[REDACTED]')
            if raw != cleaned:
                path.write_text(cleaned)
            data = json.loads(cleaned)
            if isinstance(data, dict) and (data.get('error') or data.get('success') is False or data.get('code', 0) not in (0, '0', None) or data.get('errcode', 0) not in (0, '0', None)):
                failures.append(str(path))
        except (ValueError, OSError):
            pass
    summary = {'status': 'REVIEW_REQUIRED' if result.returncode or failures else 'OUTPUT_READY', 'exitCode': result.returncode,
               'accountId': account['accountId'], 'output': str(folder), 'errorFiles': failures,
               'preview': output[:8000], 'rechargeUrl': account['rechargeUrl']}
    (folder / 'result.json').write_text(json.dumps(summary, indent=2))
    return summary


def export(args):
    rows = json.loads(Path(args.input).read_text())
    for key in args.path.split('.') if args.path else []:
        rows = rows[int(key)] if isinstance(rows, list) else rows[key]
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise Failure('CSV input must select a list of objects.')
    fields = list(dict.fromkeys(k for row in rows for k in row))
    def cell(value):
        value = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value if value is not None else '')
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
    with open(args.output, 'x', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([cell(k) for k in fields])
        writer.writerows([cell(row.get(k)) for k in fields] for row in rows)
    return {'status': 'EXPORTED', 'rows': len(rows), 'file': str(Path(args.output).resolve())}


def main():
    parser = argparse.ArgumentParser(prog='nexscope')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--api-base', default='https://api.nexscope.ai')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('get-skills').add_argument('skill', nargs='?', default='core')
    commands.add_parser('auth').add_argument('action', choices=['login', 'poll', 'status', 'logout'])
    commands.add_parser('account')
    r = commands.add_parser('run')
    r.add_argument('skill'); r.add_argument('--script'); r.add_argument('--output', default='nexscope')
    e = commands.add_parser('export')
    e.add_argument('input'); e.add_argument('--path', default=''); e.add_argument('--output', required=True)
    # Split script arguments explicitly so option names cannot change CLI behavior.
    argv = sys.argv[1:]
    tail = argv.index('--') if '--' in argv else len(argv)
    args = parser.parse_args(argv[:tail])
    args.arguments = argv[tail + 1:]
    try:
        if args.command == 'get-skills': value = guide(args.skill)
        elif args.command == 'export': value = export(args)
        else:
            client = Client(args.api_base)
            value = run(args, client) if args.command == 'run' else client.auth(args.action if args.command == 'auth' else 'status')
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 1 if value.get('status') in ('REVIEW_REQUIRED', 'UNAVAILABLE') else 0
    except (Failure, OSError, ValueError, KeyError) as e:
        print(json.dumps({'status': 'ERROR', 'message': str(e)}))
        return 1
    except Exception as e:
        # Backend/keyring exceptions may embed secret-bearing request details.
        print(json.dumps({'status': 'ERROR', 'message': 'Operation failed (' + type(e).__name__ + '). No automatic retry; check the credential store or saved output.'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
