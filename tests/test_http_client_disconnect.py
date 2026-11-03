"""A real CLI-launched HTTP process survives a client leaving mid-response."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

import support


class ClientDisconnect(unittest.TestCase):
    def test_cli_server_survives_aborted_reads_and_saved_writes(self):
        with tempfile.TemporaryDirectory(prefix='scholion-disconnect-') as temporary:
            root = Path(temporary).resolve()
            profile = root / 'profile'
            shutil.copytree(support.FIXTURE_PROFILE, profile)
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1', 0))
                port = reserve.getsockname()[1]
            env = support.env()
            env['SCHOLION_PROFILE_DIR'] = str(profile)
            script = '''
import sys,time,webbrowser
from scholion import cli,server
webbrowser.open=lambda *_:None
server._startup_selfcheck=lambda *_:None
server.warm_up=lambda:None
original=server.Handler._json
def slow_response(self,obj,code=200):
 if code==200 and (self.path.startswith('/api/markers') or (self.command=='POST' and self.path=='/api/metrics')):
  time.sleep(.15)
  obj={**obj,'synthetic_padding':'x'*2000000}
 return original(self,obj,code)
server.Handler._json=slow_response
sys.exit(cli.main(['serve','--port',sys.argv[1]]))
'''
            with (root / 'server.log').open('w', encoding='utf-8') as log:
                process = subprocess.Popen([sys.executable, '-c', script, str(port)], env=env,
                                           stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
                try:
                    base = f'http://127.0.0.1:{port}'
                    def get(path, headers=None):
                        with urllib.request.urlopen(urllib.request.Request(base + path, headers=headers or {}), timeout=5) as reply:
                            return json.load(reply)
                    for _ in range(100):
                        try:
                            ping = get('/api/ping')
                            break
                        except OSError:
                            if process.poll() is not None:
                                self.fail((root / 'server.log').read_text(encoding='utf-8'))
                            time.sleep(.05)
                    else:
                        self.fail('server did not become ready')
                    identity = ping['profile_identity']
                    self.assertEqual(64, len(identity))
                    self.assertEqual(identity, get('/api/ping')['profile_identity'])
                    for path, body in [('/api/markers', None), ('/api/metrics', {
                            'metric': 'weight', 'date': '2026-11-03', 'value': 73.25,
                            'name': 'Synthetic recorded weight', 'unit': 'kg'})]:
                        raw = json.dumps(body).encode() if body else b''
                        method = 'POST' if body else 'GET'
                        head = (f'{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n'
                                f'Content-Type: application/json\r\nContent-Length: {len(raw)}\r\n'
                                f'X-Scholion-View-Profile: {identity}\r\nConnection: close\r\n\r\n').encode()
                        with socket.create_connection(('127.0.0.1', port)) as client:
                            client.sendall(head + raw)
                            client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('HH' if os.name == 'nt' else 'ii', 1, 0))
                        time.sleep(.35)
                        self.assertIsNone(process.poll(), (root / 'server.log').read_text(encoding='utf-8'))
                        self.assertTrue(get('/api/ping')['ok'])
                    self.assertIn('73.25', (profile / 'metrics.json').read_text(encoding='utf-8'))
                    # A stale screen must not read or write another profile; legacy
                    # callers without this optional guard remain supported.
                    before = {p.name: p.read_bytes() for p in profile.glob('*.json')}
                    for method in ('GET', 'POST'):
                        req = urllib.request.Request(base + '/api/metrics', method=method,
                            headers={'X-Scholion-View-Profile': 'another-profile', 'Content-Type': 'application/json'},
                            data=b'{}' if method == 'POST' else None)
                        with self.assertRaises(urllib.error.HTTPError) as caught:
                            urllib.request.urlopen(req, timeout=5)
                        with caught.exception as reply:
                            self.assertEqual(409, reply.code)
                            self.assertEqual('profile_changed', json.load(reply)['reason'])
                    self.assertEqual(before, {p.name: p.read_bytes() for p in profile.glob('*.json')})
                    self.assertNotIn('Traceback', (root / 'server.log').read_text(encoding='utf-8'))
                finally:
                    process.terminate()
                    process.wait(timeout=10)

    @unittest.skipUnless(os.name == 'posix', 'POSIX terminal pipe behavior')
    def test_closed_terminal_output_has_no_traceback_and_no_process_signal_change(self):
        process = subprocess.Popen([sys.executable, '-m', 'scholion', 'skill'], env=support.env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        process.stdout.close()
        errors = process.stderr.read().decode('utf-8')
        process.stderr.close()
        self.assertEqual(1, process.wait(timeout=10), errors)
        self.assertNotIn('Traceback', errors)
        check = subprocess.run([sys.executable, '-c',
            "import signal; from scholion import cli; before=signal.getsignal(signal.SIGPIPE); cli.main([]); assert signal.getsignal(signal.SIGPIPE)==before"],
            env=support.env(), capture_output=True, text=True, encoding='utf-8', stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual(0, check.returncode, check.stderr)
