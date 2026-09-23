#!/usr/bin/env python3
"""Offline credential handoff, package integrity and CSV safety checks."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cli'))
from nexscope_cli.main import Client, Failure, ROOT, catalog, export, origin

class Store:
    def __init__(self): self.values = {}
    def get_password(self, service, name): return self.values.get(name)
    def set_password(self, service, name, value): self.values[name] = value
    def delete_password(self, service, name): del self.values[name]

client = Client.__new__(Client)
client.service = 'check'
client.store = Store()
secret = 'private-poll-secret'
key = 'nk-offline-check-only'
ack = []
def api(path, body=None, authenticated=False):
    if path == 'auth/start':
        return dict(status='AUTH_REQUIRED', requestId='check', pollSecret=secret, expiresAt=9999999999999, loginUrl='https://example.invalid/connect')
    if path == 'auth/poll':
        assert body['pollSecret'] == secret
        if body.get('acknowledge'):
            assert client.load('credential')['apiKey'] == key, 'credential must be durable before ack'
            ack.append(True)
            return dict(status='CONNECTED')
        return dict(status='READY', apiKey=key, accountId='1')
    if path == 'account': return dict(status='CONNECTED', accountId='1', balance=0)
    if path == 'disconnect': return None
    raise AssertionError(path)
client.api = api
assert secret not in json.dumps(client.auth('login'))
assert client.load('pending')['pollSecret'] == secret
assert key not in json.dumps(client.auth('poll'))
assert ack and client.load('pending') is None
assert client.auth('status')['balance'] == 0
client.auth('logout')
assert client.load('credential') is None
# Failed or ambiguous revocation must never erase the only local credential.
from nexscope_cli.main import AuthRequired
for failure in (Failure('API error 99012'), Failure('Network unavailable'), AuthRequired('Expired')):
    client.save('credential', {'apiKey': key})
    def fail(*args, **kwargs): raise failure
    client.api = fail
    try: client.auth('logout')
    except Failure: pass
    else: raise AssertionError('Revocation was not confirmed')
    assert client.load('credential')['apiKey'] == key
client.api = api
client.auth('logout')

for bad in ['http://example.com', 'https://user:pass@example.com', 'https://example.com/path', 'https://example.com?x=1']:
    try: origin(bad)
    except Failure: pass
    else: raise AssertionError(bad)
assert origin('http://127.0.0.1:8080/') == 'http://127.0.0.1:8080'
for name, skill in catalog().items():
    for path, digest in skill['files'].items():
        file = ROOT / 'skills' / name / path
        assert hashlib.sha256(file.read_bytes()).hexdigest() == digest, file
    assert all(path in skill['files'] for path in skill['scripts'])
with tempfile.TemporaryDirectory() as tmp:
    source, output = Path(tmp) / 'data.json', Path(tmp) / 'data.csv'
    source.write_text(json.dumps({'items': [{'name': '=1+2', 'nested': {'x': 1}}]}))
    assert export(argparse.Namespace(input=str(source), output=str(output), path='items'))['rows'] == 1
    assert "'=1+2" in output.read_text(encoding='utf-8-sig')
    try: export(argparse.Namespace(input=str(source), output=str(output), path='items'))
    except FileExistsError: pass
    else: raise AssertionError('must not overwrite')
print(f'PASS: auth handoff, zero-balance status, logout, origins, CSV and {len(catalog())} skill digests')

# Exercise the real HTTP transport and a bundled script against a loopback mock.
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from nexscope_cli.main import run
calls = []
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path.endswith('/redirect'):
            self.send_response(302)
            self.send_header('Location', '/api/cli/account')
            self.end_headers()
            return
        self.send_response(200); self.end_headers()
        self.wfile.write(json.dumps({'code': 0, 'data': {'status': 'CONNECTED'}}).encode())
    def do_POST(self):
        calls.append(self.path)
        assert self.headers['Authorization'] == 'Bearer ' + key
        self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200); self.end_headers()
        self.wfile.write(json.dumps({'code': 13011, 'msg': 'Insufficient credits'}).encode())
server = HTTPServer(('127.0.0.1', 0), Handler)
thread = Thread(target=server.serve_forever, daemon=True); thread.start()
client.base = 'http://127.0.0.1:' + str(server.server_port)
client.save('credential', {'apiKey': key})
try:
    assert Client.api(client, 'account', authenticated=True)['status'] == 'CONNECTED'
    try: Client.api(client, 'redirect', authenticated=True)
    except Failure: pass
    else: raise AssertionError('redirect accepted')
    client.api = lambda *a, **kw: {'accountId': '1', 'rechargeUrl': 'https://example.invalid/recharge'}
    with tempfile.TemporaryDirectory() as tmp:
        result = run(argparse.Namespace(skill='amazon-search', script=None, output=tmp, arguments=['{}']), client)
        assert result['status'] == 'REVIEW_REQUIRED', result
        assert key not in json.dumps(result)
        assert len(calls) == 1, 'paid request must not be replayed'
    print('PASS: real HTTP transport, redirect rejection, bundled execution and credit-error detection without replay')
finally:
    server.shutdown(); server.server_close(); thread.join()

# Incomplete upstream workflows must not request credentials or execute local scripts.
from nexscope_cli.main import guide
class NoAccount:
    def api(self, *args, **kwargs): raise AssertionError('Unavailable skill reached account API')
for name in ('geo-score-check', 'product-ai-visibility'):
    assert guide(name)['status'] == 'UNAVAILABLE'
    assert name not in guide('core')['skills']
    try: run(argparse.Namespace(skill=name, script=None), NoAccount())
    except Failure as error: assert str(error).startswith('UNAVAILABLE:')
    else: raise AssertionError('Unavailable skill was executed')
assert len(guide('core')['skills']) == 136
print('PASS: 136 routable skills; incomplete workflows fail before credential access or execution')
