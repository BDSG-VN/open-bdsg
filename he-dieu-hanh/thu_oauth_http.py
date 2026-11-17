"""Authorize/token/consent qua HTTP và cookie thật; discovery còn tiếp."""
import base64
import hashlib
import http.client
import json
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit

import thu_don_vi_http as fixture


class ThuOAuthHTTP(unittest.TestCase):
    request = fixture.ThuDonViHTTP.request
    close = fixture.ThuDonViHTTP.close

    def setUp(self):
        fixture.ThuDonViHTTP.setUp(self)
        status, self.client, _ = self.request('/api/oauth/clients', {
            'name': 'Client HTTP thu', 'redirect_uris': ['https://client.test/callback'],
            'allowed_tools': ['du_an.danh_sach']}, 'chu-quan')
        self.assertEqual(status, 200)
        self.verifier = 'v'*64
        self.challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip('=')
        result = self.request('/api/tools', {'name': 'du_an.tao', 'arguments': {'name': 'Du an OAuth HTTP'}},
                              'nguoi-a', self.units[0])
        self.assertEqual(result[0], 200)
        self.project = result[1]['ket_qua']['id']

    def pending(self):
        status, _, headers = self.request('/oauth/authorize?'+urlencode({'client_id': self.client['id'], 'redirect_uri': self.client['redirect_uris'][0],
            'response_type': 'code', 'resource': self.app.inbound_mcp.resource, 'scope': 'tool:du_an.danh_sach',
            'state': 'synthetic-http-state', 'code_challenge': self.challenge, 'code_challenge_method': 'S256'}))
        self.assertEqual(status, 303)
        target = urlsplit(headers['Location'])
        self.assertEqual(target.path, '/oauth/consent')
        self.assertFalse(target.netloc)
        self.assertEqual(headers['Referrer-Policy'], 'no-referrer')
        return parse_qs(target.fragment)['request'][0]

    def test_authorize_rejects_ambiguous_query_and_unregistered_redirect_locally(self):
        for query in ('client_id=a&client_id=b', 'client_id=%ff', 'client_id=%zz',
                      'client_id=a%00', 'client_id='+('a'*8192), ''):
            status, body, headers = self.request('/oauth/authorize?'+query)
            self.assertEqual(status, 400)
            self.assertNotIn('Location', headers)
            self.assertIn('error', body)
        query = {'client_id': self.client['id'], 'redirect_uri': 'https://unregistered.test/callback',
                 'response_type': 'code', 'resource': self.app.inbound_mcp.resource,
                 'code_challenge': self.challenge, 'code_challenge_method': 'S256'}
        status, body, headers = self.request('/oauth/authorize?'+urlencode(query))
        self.assertEqual(status, 400)
        self.assertEqual(body['error'], 'invalid_redirect_uri')
        self.assertNotIn('Location', headers)
        self.assertEqual(self.request('/oauth/authorize', query)[0], 405)

    def test_consent_assets_fixed_allowlist_and_security_headers(self):
        for path, mime in (('/oauth/consent','text/html'), ('/oauth/consent.js','application/javascript'),
                           ('/oauth/consent.css','text/css'), ('/oauth/don-vi.js','application/javascript')):
            for method in ('GET','HEAD'):
                conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
                conn.request(method, path)
                response = conn.getresponse()
                data = response.read()
                self.assertEqual(response.status, 200)
                self.assertTrue(response.getheader('Content-Type').startswith(mime))
                self.assertEqual(response.getheader('Referrer-Policy'), 'no-referrer')
                self.assertIn("frame-ancestors 'none'", response.getheader('Content-Security-Policy'))
                self.assertEqual(response.getheader('Cache-Control'), 'no-store')
                self.assertTrue(bool(data) if method == 'GET' else not data)
                conn.close()
        self.assertEqual(self.request('/oauth/consent?request=not-in-query')[0], 400)
        self.assertEqual(self.request('/oauth/../../AGENTS.md')[0], 403)

    def approved(self):
        request = self.pending()
        self.assertEqual(self.request('/api/oauth/bind', {'request': request}, 'nguoi-a', self.units[0])[0], 200)
        status, body, _ = self.request('/api/oauth/decide', {'request': request, 'approve': True,
            'selection': {'tools': ['du_an.danh_sach'], 'project_ids': [self.project], 'expires_in': 900}},
            'nguoi-a', self.units[0])
        self.assertEqual(status, 200)
        return parse_qs(urlsplit(body['redirect_uri']).query)['code'][0]

    def token(self, code, *, extra=None, headers=None, raw=None, method='POST', path='/oauth/token'):
        body = {'grant_type': 'authorization_code', 'code': code, 'client_id': self.client['id'],
                'redirect_uri': self.client['redirect_uris'][0], 'code_verifier': self.verifier,
                'resource': self.app.inbound_mcp.resource, **(extra or {})}
        fields = {'Content-Type': 'application/x-www-form-urlencoded'}
        fields.update(headers or {})
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request(method, path, raw if raw is not None else urlencode(body), fields)
        response = conn.getresponse()
        data = response.read()
        result = response.status, json.loads(data) if data else None, dict(response.getheaders())
        conn.close()
        return result

    def test_real_cookie_consent_form_exchange_and_bearer_mcp(self):
        status, token, headers = self.token(self.approved(), headers={
            'Cookie': self.cookies['nguoi-b'], 'X-BDSG-Unit': self.units[1], 'X-BDSG-Actor': 'nguoi-b'})
        self.assertEqual(status, 200)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['Pragma'], 'no-cache')
        status, body, _ = self.request('/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'du_an.danh_sach'}}, headers={'Accept': 'application/json, text/event-stream',
                                                         'Authorization': 'Bearer '+token['access_token']})
        self.assertEqual(status, 200)
        self.assertFalse(body['result']['isError'])
        self.assertEqual([row['id'] for row in json.loads(body['result']['content'][0]['text'])['projects']], [self.project])

    def test_admin_client_registry_is_control_plane_and_no_epoch_leak(self):
        status, body, _ = self.request('/api/oauth/clients', who='chu-quan')
        self.assertEqual(status, 200)
        self.assertEqual(len(body['clients']), 1)
        self.assertNotIn('issuer_epoch', json.dumps(body))
        self.assertEqual(self.request('/api/oauth/clients', who='nguoi-a')[0], 403)
        self.assertEqual(self.request('/api/oauth/clients', who='chu-quan', headers={'X-BDSG-Actor': 'nguoi-a'})[0], 409)

    def test_consent_requires_session_origin_and_unchanged_identity_unit(self):
        request = self.pending()
        body = {'request': request}
        self.assertEqual(self.request('/api/oauth/bind', body, unit=self.units[0])[0], 401)
        self.assertEqual(self.request('/api/oauth/bind', body, 'nguoi-a', self.units[0], headers={'Origin': ''})[0], 403)
        self.assertEqual(self.request('/api/oauth/bind', body, 'nguoi-a', self.units[0])[0], 200)
        self.assertEqual(self.request('/api/oauth/bind', body, 'nguoi-a', self.units[1])[0], 403)
        self.assertEqual(self.request('/api/oauth/bind', body, 'nguoi-b', self.units[0])[0], 403)
        self.assertEqual(self.request('/api/oauth/bind', body, 'nguoi-a', self.units[0],
                                      headers={'X-BDSG-Actor': 'nguoi-b'})[0], 409)

    def test_deny_works_with_write_gate_closed_and_does_not_issue_code(self):
        request = self.pending()
        self.request('/api/oauth/bind', {'request': request}, 'nguoi-a', self.units[0])
        self.app.core.nhan.chinh_sach.cong_ghi.dong()
        status, body, _ = self.request('/api/oauth/decide', {'request': request, 'approve': False}, 'nguoi-a', self.units[0])
        self.assertEqual(status, 200)
        self.assertEqual(parse_qs(urlsplit(body['redirect_uri']).query)['error'], ['access_denied'])
        self.assertNotIn('code=', body['redirect_uri'])

    def test_duplicate_context_headers_are_rejected_before_binding(self):
        request = self.pending()
        raw = json.dumps({'request': request}).encode()
        for key, first, second in (('X-BDSG-Actor', 'nguoi-a', 'nguoi-b'),
                                   ('X-BDSG-Unit', self.units[0], self.units[1]),
                                   ('X-BDSG-Unit-Epoch', '1', '2'), ('X-BDSG-Unit-Revision', '1', '2')):
            with self.subTest(header=key):
                fields = {'Origin': self.app.origin, 'Content-Type': 'application/json',
                          'Content-Length': str(len(raw)), 'Cookie': self.cookies['nguoi-a'],
                          'X-BDSG-Unit': self.units[0], key: first}
                conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
                conn.putrequest('POST', '/api/oauth/bind')
                for name, value in fields.items(): conn.putheader(name, value)
                conn.putheader(key, second)
                conn.endheaders(raw)
                response = conn.getresponse()
                self.assertEqual(response.status, 400)
                self.assertEqual(json.loads(response.read())['error'], 'invalid_request')
                conn.close()
        self.assertEqual(self.request('/api/oauth/bind', {'request': request}, 'nguoi-a', self.units[0])[0], 200)

    def test_token_mismatch_replay_and_client_disable(self):
        code = self.approved()
        self.assertEqual(self.token(code, extra={'resource': 'https://other.test/mcp'})[0], 400)
        status, token, _ = self.token(code)
        self.assertEqual(status, 200)
        self.assertEqual(self.token(code)[1]['error'], 'invalid_grant')
        status, _, _ = self.request('/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            headers={'Accept': 'application/json, text/event-stream', 'Authorization': 'Bearer '+token['access_token']})
        self.assertEqual(status, 401)
        code = self.approved()
        self.assertEqual(self.request('/api/oauth/clients/disable', {'id': self.client['id']}, 'chu-quan')[0], 200)
        self.assertEqual(self.token(code)[1]['error'], 'invalid_client')

    def test_token_rejects_query_origin_authorization_media_duplicates_and_nonfinite_json(self):
        code = self.approved()
        for options in ({'path': '/oauth/token?access_token=synthetic'}, {'headers': {'Origin': 'https://other.test'}},
                        {'headers': {'Authorization': 'Bearer synthetic-placeholder'}},
                        {'headers': {'Content-Type': 'application/json'}}, {'raw': 'grant_type=x&grant_type=y'},
                        {'raw': 'bad=%ff'}, {'headers': {'Transfer-Encoding': 'chunked'}}):
            with self.subTest(kind=list(options)):
                self.assertIn(self.token(code, **options)[0], (400, 403))
        self.assertEqual(self.token(code, method='GET')[0], 405)
        self.assertEqual(self.token(code)[0], 200)
        self.assertEqual(self.request('/api/oauth/decide', {'request': None, 'approve': float('nan')},
                                      'nguoi-a', self.units[0])[0], 400)
        request = self.pending()
        duplicate = '{"request":"'+request+'","request":"'+request+'"}'
        self.assertEqual(self.token(code, path='/api/oauth/bind', raw=duplicate, headers={
            'Cookie': self.cookies['nguoi-a'], 'Origin': self.app.origin,
            'Content-Type': 'application/json', 'X-BDSG-Unit': self.units[0]})[0], 400)
        self.assertEqual(self.request('/api/oauth/bind', {'request': request}, 'nguoi-a', self.units[0])[0], 200)

    def test_manual_grants_are_scoped_return_once_and_revoke_even_when_gate_closed(self):
        settings = {'name': 'Client manual HTTP', 'client_id': 'synthetic-manual',
                    'tools': ['nen_tang.danh_sach'], 'project_ids': [], 'expires_in': 900}
        status, issued, _ = self.request('/api/mcp/grants', settings, 'nguoi-a', self.units[0])
        self.assertEqual(status, 200)
        self.assertTrue('credential' in issued)
        status, listed, _ = self.request('/api/mcp/grants', who='nguoi-a', unit=self.units[0])
        self.assertEqual(status, 200)
        self.assertTrue(issued['credential'] not in json.dumps(listed), 'Danh sách không trả lại credential')
        self.assertEqual(self.request('/api/mcp/grants', who='nguoi-a', unit=self.units[1])[1]['grants'], [])
        self.app.core.nhan.chinh_sach.cong_ghi.dong()
        self.assertEqual(self.request('/api/mcp/grants', settings, 'nguoi-a', self.units[0])[0], 403)
        self.assertEqual(self.request('/api/mcp/grants/revoke', {'id': issued['id']}, 'nguoi-a', self.units[0])[0], 200)

    def test_metadata_fixed_origin_resource_and_only_implemented_capabilities(self):
        headers = {'Host': 'untrusted.test', 'X-Forwarded-Host': 'untrusted.test',
                   'X-Forwarded-Proto': 'http'}
        for path in ('/.well-known/oauth-protected-resource', '/.well-known/oauth-protected-resource/mcp'):
            status, body, response = self.request(path, headers=headers)
            self.assertEqual(status, 200)
            self.assertEqual(body['resource'], self.app.inbound_mcp.resource)
            self.assertEqual(body['authorization_servers'], [self.app.origin])
            self.assertEqual(body['bearer_methods_supported'], ['header'])
            self.assertEqual(response['Cache-Control'], 'no-store')
            self.assertNotIn('issuer_epoch', body)
            conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
            conn.request('HEAD',path)
            result = conn.getresponse()
            self.assertEqual(result.status,200)
            self.assertEqual(result.read(),b'')
            self.assertGreater(int(result.getheader('Content-Length')),0)
            conn.close()
        status, body, _ = self.request('/.well-known/oauth-authorization-server', headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(body['issuer'], self.app.origin)
        self.assertEqual(body['authorization_endpoint'], self.app.origin+'/oauth/authorize')
        self.assertEqual(body['token_endpoint'], self.app.origin+'/oauth/token')
        self.assertEqual(body['code_challenge_methods_supported'], ['S256'])
        self.assertEqual(body['token_endpoint_auth_methods_supported'], ['none'])
        self.assertEqual(body['grant_types_supported'], ['authorization_code'])
        self.assertNotIn('registration_endpoint', body)
        self.assertNotIn('refresh_token', json.dumps(body))
        self.assertEqual(self.request('/.well-known/oauth-authorization-server?issuer=untrusted')[0], 400)
        self.assertEqual(self.request('/.well-known/oauth-authorization-server', {})[0], 405)
        status, _, response = self.request('/mcp', {'jsonrpc':'2.0','id':1,'method':'tools/list'})
        self.assertEqual(status, 401)
        self.assertIn('resource_metadata="'+self.app.origin+'/.well-known/oauth-protected-resource/mcp"', response['WWW-Authenticate'])

    def test_gate_drain_and_bad_shapes(self):
        self.assertEqual(self.request('/api/oauth/bind', {}, 'nguoi-a', self.units[0])[0], 400)
        self.assertEqual(self.request('/api/mcp/grants/revoke', {'id': 'x', 'owner': 'pretend'}, 'nguoi-a', self.units[0])[0], 400)
        self.app.core.nhan.chinh_sach.cong_ghi.dong()
        self.assertEqual(self.token('synthetic-placeholder')[0], 503)
        self.app.operations.draining.set()
        self.assertEqual(self.request('/api/oauth/clients', who='chu-quan')[0], 503)
        self.assertEqual(self.request('/api/oauth/clients', who='chu-quan', headers={'Origin': 'https://other.test'})[0], 403)


if __name__ == '__main__': unittest.main()
