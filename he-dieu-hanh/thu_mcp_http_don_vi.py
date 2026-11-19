"""MCP qua socket HTTP thật; chỉ dữ liệu tổng hợp và credential tạm."""
import http.client
import json
import threading
import unittest

import thu_mcp_uy_quyen_don_vi as fixture
from may_chu import tao_may_chu


class ThuMCPHTTPDonVi(unittest.TestCase):
    def setUp(self):
        fixture.ThuUyQuyenMCPDonVi.setUp(self)
        self.issued = fixture.ThuUyQuyenMCPDonVi.grant(self)
        self.server = tao_may_chu(self.app, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()

    def request(self, payload=None, *, method='POST', headers=None, raw=None, path='/mcp', authenticated=True,
                duplicate=None):
        fields = {'Origin': self.app.origin, 'Accept': 'application/json, text/event-stream',
                  'Content-Type': 'application/json'}
        if authenticated: fields['Authorization'] = 'Bearer '+self.issued['credential']
        fields.update(headers or {})
        fields = {key: value for key, value in fields.items() if value is not None}
        if method == 'POST':
            raw = raw if raw is not None else json.dumps(payload if payload is not None else
                {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}).encode()
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        if duplicate:
            conn.putrequest(method, path)
            if raw is not None: fields.setdefault('Content-Length', str(len(raw)))
            for key, value in fields.items(): conn.putheader(key, value)
            conn.putheader(*duplicate)
            conn.endheaders(raw)
        else:
            conn.request(method, path, raw, fields)
        response = conn.getresponse()
        data = response.read()
        result = response.status, json.loads(data) if data else None, dict(response.getheaders()), data
        conn.close()
        return result

    def test_initialize_version_negotiation_and_notification_zero_body(self):
        result = self.request({'jsonrpc': '2.0', 'id': 'init', 'method': 'initialize', 'params': {
            'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'Test', 'version': '1'}}})
        self.assertEqual(result[0], 200)
        self.assertEqual(result[1]['result']['protocolVersion'], '2025-06-18')
        self.assertNotIn('Mcp-Session-Id', result[2])
        result = self.request({'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                              headers={'MCP-Protocol-Version': '2025-06-18'})
        self.assertEqual((result[0], result[1], result[3]), (202, None, b''))
        self.assertEqual(result[2]['Content-Length'], '0')

    def test_tools_list_call_scope_and_no_identity_from_headers(self):
        status, body, _, _ = self.request(headers={'X-BDSG-Unit': self.units[1], 'Mcp-Session-Id': 'invented'})
        self.assertEqual(status, 200)
        self.assertCountEqual([tool['name'] for tool in body['result']['tools']], self.issued['tools'])
        result = self.request({'jsonrpc': '2.0', 'id': 0, 'method': 'tools/call',
                              'params': {'name': 'du_an.danh_sach', 'arguments': {}}})
        self.assertEqual(result[0], 200)
        tool = result[1]['result']
        self.assertFalse(tool['isError'])
        self.assertEqual([row['id'] for row in json.loads(tool['content'][0]['text'])['projects']], [self.project])
        self.assertNotIn('OUTSIDE-PROJECT', json.dumps(result[1]))

    def test_get_delete_options_no_stream_and_origin_checked(self):
        for method in ('GET', 'DELETE', 'OPTIONS', 'HEAD', 'PUT', 'PATCH'):
            with self.subTest(method=method):
                result = self.request(method=method)
                self.assertEqual(result[0], 405)
                self.assertEqual(result[2]['Allow'], 'POST')
                self.assertNotIn('Access-Control-Allow-Origin', result[2])
                if method == 'HEAD': self.assertEqual(result[3], b'')
                self.assertEqual(self.request(method=method, headers={'Origin': 'https://other.test'})[0], 403)

    def test_bearer_required_cookie_legacy_query_and_fake_session_do_not_authenticate(self):
        legacy = self.app.kho.tao_agent('legacy-only', 'Synthetic legacy', 'operator')
        for headers in ({'Authorization': 'Bearer '+legacy}, {'Mcp-Session-Id': 'invented'},
                        {'Cookie': 'bdsg_session=invented', 'X-BDSG-Unit': self.units[0]}):
            with self.subTest(kind=list(headers)):
                result = self.request(headers=headers, authenticated=False)
                self.assertEqual(result[0], 401)
                self.assertIn('WWW-Authenticate', result[2])
        self.assertEqual(self.request(path='/mcp?access_token=synthetic-placeholder')[0], 400)

    def test_invalid_origin_duplicate_headers_and_accept_quality(self):
        for header in ('Authorization', 'Origin', 'Content-Length', 'MCP-Protocol-Version', 'Accept'):
            with self.subTest(header=header):
                value = {'Authorization': 'Bearer synthetic-placeholder', 'Origin': self.app.origin,
                         'Content-Length': '1', 'MCP-Protocol-Version': '2025-06-18', 'Accept': 'application/json'}[header]
                self.assertEqual(self.request(duplicate=(header, value),
                    headers={'MCP-Protocol-Version': '2025-06-18'})[0], 400)
        for accept in ('application/json', '*/*', 'application/json;q=0, text/event-stream',
                       'application/json, text/event-stream;q=0', 'application/json;q=nan, text/event-stream'):
            with self.subTest(accept=accept): self.assertEqual(self.request(headers={'Accept': accept})[0], 406)
        self.assertEqual(self.request(headers={'Origin': 'null'})[0], 403)

    def test_content_type_length_transfer_version_and_parse_errors(self):
        for headers, expected in (({'Content-Type': 'text/plain'}, 415),
                                  ({'Content-Length': '70000'}, 413), ({'Content-Length': '-1'}, 400),
                                  ({'Transfer-Encoding': 'chunked'}, 400),
                                  ({'MCP-Protocol-Version': '2099-01-01'}, 400)):
            with self.subTest(headers=headers): self.assertEqual(self.request(headers=headers)[0], expected)
        for raw in (b'{', b'{"jsonrpc":"2.0","jsonrpc":"2.0"}', b'{"a":NaN}', b'\xff', b'{"id":"\\ud800"}',
                    b'{"jsonrpc":"2.0","id":1,"method":"ping","params":{"_meta":{"n":1e9999}}}',
                    b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18",'
                    b'"capabilities":{"n":1e9999},"clientInfo":{"name":"Test","version":"1"}}}'):
            with self.subTest(raw=raw):
                result = self.request(raw=raw)
                self.assertEqual(result[0], 400)
                self.assertEqual(result[1]['error']['code'], -32700)

    def test_invalid_rpc_envelopes_ids_and_params(self):
        for payload in ([], None, {'jsonrpc': '2.0', 'id': True, 'method': 'ping'},
                        {'jsonrpc': '2.0', 'id': 1.5, 'method': 'ping'},
                        {'jsonrpc': '2.0', 'id': None, 'method': 'ping'},
                        {'jsonrpc': '2.0', 'id': {}, 'method': 'ping'},
                        {'jsonrpc': '2.0', 'id': 1, 'method': 'ping', 'actor': 'pretend'}):
            raw = json.dumps(payload).encode()
            with self.subTest(payload=payload): self.assertEqual(self.request(raw=raw)[1]['error']['code'], -32600)
        result = self.request({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {'unit_id': self.units[1]}})
        self.assertEqual(result[1]['error']['code'], -32602)
        result = self.request({'jsonrpc': '2.0', 'id': 1, 'method': 'ping', 'params': []})
        self.assertEqual((result[0], result[1]['error']['code']), (200, -32602))

    def test_unknown_method_tool_and_tool_execution_errors_are_distinct(self):
        result = self.request({'jsonrpc': '2.0', 'id': 1, 'method': 'unknown'})
        self.assertEqual((result[0], result[1]['error']['code']), (200, -32601))
        result = self.request({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'hanh_dong.duyet'}})
        self.assertEqual(result[1]['error']['code'], -32602)
        result = self.request({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'du_an.danh_sach', 'arguments': {'unit_id': self.units[1]}}})
        self.assertTrue(result[1]['result']['isError'])
        self.assertNotIn(self.units[1], json.dumps(result[1]))

    def test_notification_cannot_execute_tool_and_cancel_is_only_advisory(self):
        result = self.request({'jsonrpc': '2.0', 'method': 'tools/call', 'params': {'name': 'du_an.danh_sach'}})
        self.assertEqual(result[0], 400)
        result = self.request({'jsonrpc': '2.0', 'method': 'notifications/cancelled', 'params': {'requestId': 1}})
        self.assertEqual((result[0], result[3]), (202, b''))
        result = self.request({'jsonrpc': '2.0', 'method': 'notifications/initialized', 'params': {'grant': 'pretend'}})
        self.assertEqual(result[0], 400)

    def test_revoke_after_read_drops_response_and_fake_session_does_not_keep_actor(self):
        original = self.app.projects.list
        def revoke_during_read(actor):
            result = original(actor)
            self.service.revoke(self.actor, self.issued['id'])
            return result
        self.app.projects.list = revoke_during_read
        response = self.request({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'du_an.danh_sach'}})
        self.assertEqual(response[0], 401)
        self.assertNotIn('ONLY-GRANTED-CONTEXT', json.dumps(response[1]))
        self.assertEqual(self.request(headers={'Mcp-Session-Id': 'pretend'})[0], 401)

    def test_native_without_origin_expiry_and_draining(self):
        self.assertEqual(self.request(headers={'Origin': None})[0], 200)
        self.now += 901
        self.assertEqual(self.request()[0], 401)
        self.app.operations.draining.set()
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(self.request(headers={'Origin': 'https://other.test'})[0], 403)


if __name__ == '__main__': unittest.main()
