"""Nghiệm thu lệnh vận hành pilot qua tiến trình và HTTP thật, dữ liệu tạm."""
import json
import os
import http.client
from pathlib import Path
import subprocess
import sys
import socket
import tempfile
import time
import unittest


GATEWAY = Path(__file__).with_name('may_chu.py')


class ThuGatewayPilot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root/'pilot'
        self.credentials = self.root/'credentials.json'

    def command(self, action, *extra):
        env = {key: value for key, value in os.environ.items() if not key.startswith('BDSG_')}
        return subprocess.run([sys.executable, '-X', 'utf8', str(GATEWAY), action, '--data', str(self.data),
                               *extra], capture_output=True, timeout=15, env=env)

    def test_init_requires_new_data_and_legacy_cannot_reopen_pilot(self):
        result = self.command('init', '--unit-preview', '--output', str(self.credentials))
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertTrue(self.credentials.is_file())
        before = self.credentials.read_bytes()
        refused = self.command('init', '--unit-preview', '--output', str(self.root/'other.json'))
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(self.credentials.read_bytes(), before)
        self.assertNotEqual(self.command('serve', '--port', '0').returncode, 0)

    def test_pilot_serves_units_over_http_and_restarts_without_resetting_password(self):
        result = self.command('init', '--unit-preview', '--output', str(self.credentials))
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        credentials = json.loads(self.credentials.read_text())
        for _ in range(2):
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            env = {key: value for key, value in os.environ.items() if not key.startswith('BDSG_')}
            with tempfile.TemporaryFile() as log:
                process = subprocess.Popen([sys.executable, '-X', 'utf8', str(GATEWAY),
                    'serve', '--unit-preview', '--data', str(self.data), '--port', str(port),
                    '--origin', 'https://pilot.test'], env=env, stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 12
                    while True:
                        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
                        try:
                            conn.request('GET', '/api/me')
                            response = conn.getresponse()
                            self.assertEqual(response.status, 200)
                            self.assertEqual(json.loads(response.read())['workspace']['mode'], 'units')
                            break
                        except OSError:
                            if process.poll() is not None or time.monotonic() > deadline:
                                self.fail('Pilot không khởi động; không in log có thể chứa chứng thư')
                            time.sleep(.05)
                        finally:
                            conn.close()
                    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                    try:
                        conn.request('POST', '/api/login', json.dumps({
                            'username': credentials['username'], 'password': credentials['password']}),
                            {'Origin': 'https://pilot.test', 'Content-Type': 'application/json'})
                        response = conn.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertIn('HttpOnly', response.getheader('Set-Cookie'))
                        response.read()
                    finally:
                        conn.close()
                finally:
                    process.terminate()
                    process.wait(timeout=10)

    def test_preview_requires_explicit_data_even_when_environment_supplies_it(self):
        env = dict(os.environ, BDSG_DATA_DIR=str(self.data))
        result = subprocess.run([sys.executable, '-X', 'utf8', str(GATEWAY), 'init',
            '--unit-preview', '--output', str(self.credentials)], env=env,
            capture_output=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.data.exists())

    def test_existing_legacy_store_is_unchanged_when_preview_is_refused(self):
        self.assertEqual(self.command('init', '--output', str(self.credentials)).returncode, 0)
        before = {p.name: p.read_bytes() for p in self.data.iterdir() if p.is_file()}
        self.assertNotEqual(self.command('serve', '--unit-preview', '--port', '0').returncode, 0)
        self.assertNotEqual(self.command('init', '--unit-preview', '--output',
                            str(self.root/'other.json')).returncode, 0)
        self.assertEqual({p.name: p.read_bytes() for p in self.data.iterdir() if p.is_file()}, before)
        self.assertFalse((self.root/'other.json').exists())

    def test_preview_refuses_legacy_agent_credentials_and_bad_marker(self):
        self.assertEqual(self.command('init', '--unit-preview', '--output',
                                     str(self.credentials)).returncode, 0)
        self.assertNotEqual(self.command('create-agent', '--unit-preview', '--id', 'agent-test',
                            '--name', 'Test', '--output', str(self.root/'agent.json')).returncode, 0)
        self.assertFalse((self.root/'agent.json').exists())
        (self.data/'unit-preview.mode').write_text('invalid', encoding='utf-8')
        self.assertNotEqual(self.command('serve', '--unit-preview', '--port', '0').returncode, 0)


if __name__ == '__main__':
    unittest.main()
