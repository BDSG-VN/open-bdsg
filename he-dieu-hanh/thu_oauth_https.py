"""Cookie/PKCE/token và SDK bearer qua TLS thật; discovery/authorize UI còn tiếp."""
import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import ipaddress
import json
from pathlib import Path
import ssl
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit

from may_chu import UngDung, tao_may_chu
from thu_mcp_client_sdk import SDK_AVAILABLE

if SDK_AVAILABLE:
    # Có SDK nhưng thiếu dependency TLS là lỗi môi trường, không lặng lẽ bỏ kiểm.
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client


def tls_contexts(folder):
    """CA chỉ tin trong fixture, leaf chỉ hợp lệ với IP loopback được thử."""
    now = datetime.now(timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'BDSG CA thu tam')])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(hours=1))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .sign(ca_key, hashes.SHA256()))
    key = ec.generate_private_key(ec.SECP256R1())
    leaf = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'BDSG loopback thu')]))
            .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    cert_path, key_path = Path(folder)/'leaf.pem', Path(folder)/'key.pem'
    cert_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_path.chmod(0o600)
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.minimum_version = ssl.TLSVersion.TLSv1_2
    server.load_cert_chain(cert_path, key_path)
    client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client.load_verify_locations(cadata=ca.public_bytes(serialization.Encoding.PEM).decode('ascii'))
    return server, client


class DeferredApp:
    # Bind cổng 0 trước khi tạo authority để audience/origin luôn là URL TLS thật.
    def __getattr__(self, name):
        return getattr(self.instance, name)


@unittest.skipUnless(SDK_AVAILABLE, 'Cần requirements-mcp-test.txt; CI bắt buộc chạy HTTPS/SDK')
class ThuOAuthHTTPS(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        server_context, self.context = tls_contexts(self.tmp.name)
        proxy = DeferredApp()
        self.server = tao_may_chu(proxy, 0)
        self.addCleanup(self.server.server_close)
        self.origin = 'https://127.0.0.1:'+str(self.server.server_port)
        self.app = UngDung(str(Path(self.tmp.name)/'data'), self.origin, True, unit_preview=True)
        self.addCleanup(self.app.core.audit.close)
        self.addCleanup(self.app.tasks.close)
        proxy.instance = self.app
        self.server.socket = server_context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.password = 'synthetic-https-password'
        self.app.kho.tao_chu(self.password)
        root = {'id': 'chu-quan', 'name': 'Chu quan thu', 'role': 'quan-tri'}
        self.app.kho.tao_nguoi_dung(root, {'id': 'nguoi-thu', 'name': 'Nguoi thu', 'password': self.password})
        self.cookies = {}
        for who in ('chu-quan', 'nguoi-thu'):
            status, _, headers = self.request('/api/login', {'username': who, 'password': self.password})
            self.assertEqual(status, 200)
            self.assertIn('Secure', headers['Set-Cookie'])
            self.cookies[who] = headers['Set-Cookie'].split(';')[0]
        status, unit, _ = self.request('/api/units', {'name': 'Don vi TLS', 'admin': 'nguoi-thu'}, 'chu-quan')
        self.assertEqual(status, 200)
        self.unit = unit['id']
        status, body, _ = self.request('/api/tools', {'name': 'du_an.tao', 'arguments': {'name': 'Du an TLS'}},
                                      'nguoi-thu', self.unit)
        self.assertEqual(status, 200)
        self.project = body['ket_qua']['id']
        status, body, _ = self.request('/api/tools', {'name': 'du_an.tao', 'arguments': {'name': 'Du an ngoai consent'}},
                                      'nguoi-thu', self.unit)
        self.assertEqual(status, 200)
        self.other_project = body['ket_qua']['id']
        status, self.client, _ = self.request('/api/oauth/clients', {'name': 'SDK TLS thu',
            'redirect_uris': ['https://client.test/callback'],
            'allowed_tools': ['du_an.danh_sach', 'nen_tang.danh_sach']}, 'chu-quan')
        self.assertEqual(status, 200)

    def stop_server(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive())

    def request(self, path, body=None, who=None, unit=None, *, form=False, context=None, host='127.0.0.1'):
        headers = {'Origin': self.origin, 'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json'}
        if who: headers['Cookie'] = self.cookies[who]
        if unit: headers['X-BDSG-Unit'] = unit
        conn = http.client.HTTPSConnection(host, self.server.server_port, context=context or self.context, timeout=5)
        try:
            raw = (urlencode(body) if form else json.dumps(body)) if body is not None else None
            conn.request('POST' if body is not None else 'GET', path, raw, headers)
            response = conn.getresponse()
            data = response.read()
            return response.status, json.loads(data) if data else None, dict(response.getheaders())
        finally:
            conn.close()

    def code(self):
        self.verifier = 'v'*64
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip('=')
        # Đây là start backend thật; chưa nhận discovery/authorize browser/SDK OAuth đã xong.
        pending = self.app.oauth_mcp.start({'client_id': self.client['id'], 'response_type': 'code',
            'redirect_uri': self.client['redirect_uris'][0], 'resource': self.origin+'/mcp',
            'code_challenge': challenge, 'code_challenge_method': 'S256', 'state': 'synthetic-tls-state'})
        self.assertEqual(self.request('/api/oauth/bind', {'request': pending['request']}, 'nguoi-thu', self.unit)[0], 200)
        status, result, _ = self.request('/api/oauth/decide', {'request': pending['request'], 'approve': True,
            'selection': {'tools': ['du_an.danh_sach'], 'project_ids': [self.project], 'expires_in': 900}},
            'nguoi-thu', self.unit)
        self.assertEqual(status, 200)
        query = parse_qs(urlsplit(result['redirect_uri']).query)
        self.assertEqual(query['iss'], [self.origin])
        self.assertEqual(query['state'], ['synthetic-tls-state'])
        return query['code'][0]

    def exchange(self, code, **extra):
        return self.request('/oauth/token', {'grant_type': 'authorization_code', 'code': code,
            'client_id': self.client['id'], 'redirect_uri': self.client['redirect_uris'][0],
            'code_verifier': self.verifier, 'resource': self.origin+'/mcp', **extra}, form=True)

    def test_tls_rejects_untrusted_ca_and_wrong_hostname(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.request('/api/ready', context=ssl.create_default_context())
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.request('/api/ready', host='localhost')
        self.assertEqual(self.request('/api/ready')[0], 200)

    def test_https_cookie_pkce_exchange_then_sdk_scope_and_revocation(self):
        status, body, _ = self.request('/api/tools', {'name': 'du_an.danh_sach', 'arguments': {}}, 'nguoi-thu', self.unit)
        self.assertEqual(status, 200)
        self.assertCountEqual([row['id'] for row in body['ket_qua']['projects']], [self.project, self.other_project])
        code = self.code()
        self.assertEqual(self.exchange(code, resource='https://other.test/mcp')[0], 400)
        status, token, headers = self.exchange(code)
        self.assertEqual(status, 200)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['Pragma'], 'no-cache')
        statuses = []
        async def record(response): statuses.append(response.status_code)
        async def run():
            async with httpx2.AsyncClient(verify=self.context, trust_env=False, timeout=5,
                    headers={'Authorization': 'Bearer '+token['access_token']}, event_hooks={'response': [record]}) as http:
                transport = streamable_http_client(self.origin+'/mcp', http_client=http)
                async with Client(transport, mode='legacy', cache=None) as client:
                    self.assertEqual(client.protocol_version, '2025-06-18')
                    self.assertEqual([tool.name for tool in (await client.list_tools()).tools], ['du_an.danh_sach'])
                    result = await client.call_tool('du_an.danh_sach', {})
                    self.assertFalse(result.is_error)
                    self.assertEqual([row['id'] for row in json.loads(result.content[0].text)['projects']], [self.project])
                    self.assertEqual(self.request('/api/oauth/clients/disable', {'id': self.client['id']}, 'chu-quan')[0], 200)
                    with self.assertRaises(Exception):
                        await client.call_tool('du_an.danh_sach', {})
                    self.assertEqual(statuses[-1], 401)
        if sys.platform == 'win32':
            # HTTP 401 đóng stream có thể làm Proactor cleanup reset sau khi loop đã đóng.
            with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
                runner.run(run())
        else:
            asyncio.run(run())

    def test_web_logout_before_exchange_invalidates_code(self):
        code = self.code()
        self.assertEqual(self.request('/api/logout', {}, 'nguoi-thu')[0], 200)
        status, body, _ = self.exchange(code)
        self.assertEqual(status, 400)
        self.assertEqual(body['error'], 'invalid_grant')


if __name__ == '__main__': unittest.main()
