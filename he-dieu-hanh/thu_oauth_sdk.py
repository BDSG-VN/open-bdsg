"""SDK tự discovery/S256/token qua HTTPS thật; consent điều khiển bằng cookie API."""
import asyncio
import json
import sys
import unittest
from urllib.parse import parse_qs, urlsplit

from thu_mcp_client_sdk import SDK_AVAILABLE
import thu_oauth_https as fixture

if SDK_AVAILABLE:
    import httpx2
    from mcp import Client
    from mcp.client.auth import OAuthClientProvider
    from mcp.client.auth.exceptions import OAuthFlowError
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared.auth import AuthorizationCodeResult, OAuthClientInformationFull, OAuthClientMetadata
    from oauth_mcp_don_vi import TOOLS


class MemoryStorage:
    def __init__(self, info): self.info, self.tokens = info, None
    async def get_tokens(self): return self.tokens
    async def set_tokens(self, tokens): self.tokens = tokens
    async def get_client_info(self): return self.info
    async def set_client_info(self, info): self.info = info


@unittest.skipUnless(SDK_AVAILABLE, 'Cần requirements-mcp-test.txt; CI bắt buộc chạy OAuth SDK')
class ThuOAuthSDK(unittest.TestCase):
    setUp = fixture.ThuOAuthHTTPS.setUp
    stop_server = fixture.ThuOAuthHTTPS.stop_server
    request = fixture.ThuOAuthHTTPS.request

    def exercise(self, approve):
        # SDK chọn scopes quảng bá; client đã được chủ quản duyệt trần công cụ,
        # consent thật bên dưới vẫn chỉ chọn một công cụ và một dự án.
        status, registered, _ = self.request('/api/oauth/clients', {'name':'SDK OAuth kiem thu',
            'redirect_uris':['https://client.test/callback'], 'allowed_tools':sorted(TOOLS)}, 'chu-quan')
        self.assertEqual(status, 200)
        metadata = OAuthClientMetadata(redirect_uris=registered['redirect_uris'],
            client_name='SDK OAuth kiem thu', grant_types=['authorization_code'],
            response_types=['code'], token_endpoint_auth_method='none')
        storage = MemoryStorage(OAuthClientInformationFull(**metadata.model_dump(),
            client_id=registered['id'], issuer=self.origin))
        callbacks, requests, decisions = [], [], []

        async def redirect(url):
            target = urlsplit(url)
            self.assertEqual(target.scheme+'://'+target.netloc, self.origin)
            self.assertEqual(target.path, '/oauth/authorize')
            params = parse_qs(target.query)
            self.assertEqual(params['resource'], [self.origin+'/mcp'])
            self.assertEqual(params['code_challenge_method'], ['S256'])
            status, _, headers = self.request(target.path+'?'+target.query)
            self.assertEqual(status, 303)
            page = urlsplit(headers['Location'])
            self.assertEqual(page.path, '/oauth/consent')
            nonce = parse_qs(page.fragment)['request'][0]
            self.assertEqual(self.request('/api/oauth/bind', {'request':nonce}, 'nguoi-thu', self.unit)[0], 200)
            decision = {'request':nonce,'approve':approve}
            if approve:
                decision['selection'] = {'tools':['du_an.danh_sach'], 'project_ids':[self.project], 'expires_in':900}
            status, result, _ = self.request('/api/oauth/decide', decision, 'nguoi-thu', self.unit)
            self.assertEqual(status, 200)
            query = parse_qs(urlsplit(result['redirect_uri']).query)
            self.assertEqual(query['state'], params['state'])
            self.assertEqual(query['iss'], [self.origin])
            decisions.append('approved' if approve else 'denied')
            if not approve:
                self.assertEqual(query['error'], ['access_denied'])
                self.assertNotIn('code',query)
                raise OAuthFlowError('Nguoi dung tu choi trong kiem thu')
            callbacks.append(AuthorizationCodeResult(code=query['code'][0], state=query['state'][0], iss=query['iss'][0]))

        async def callback():
            self.assertEqual(len(callbacks),1)
            return callbacks[0]

        async def record(response):
            # Chỉ metadata vận chuyển; không ghi code/verifier/Authorization/token.
            requests.append((response.request.method,response.request.url.path,response.status_code))

        async def run():
            provider = OAuthClientProvider(self.origin+'/mcp', metadata, storage, redirect, callback)
            async with httpx2.AsyncClient(auth=provider, verify=self.context, timeout=8, trust_env=False,
                                          event_hooks={'response':[record]}) as http:
                transport = streamable_http_client(self.origin+'/mcp', http_client=http)
                async with Client(transport,mode='legacy',cache=None) as client:
                    self.assertEqual(client.protocol_version,'2025-06-18')
                    self.assertEqual([tool.name for tool in (await client.list_tools()).tools], ['du_an.danh_sach'])
                    result = await client.call_tool('du_an.danh_sach',{})
                    self.assertFalse(result.is_error)
                    self.assertEqual([row['id'] for row in json.loads(result.content[0].text)['projects']], [self.project])

        def execute():
            if sys.platform == 'win32':
                with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner: runner.run(run())
            else: asyncio.run(run())

        if approve:
            execute()
            self.assertIsNotNone(storage.tokens)
            self.assertEqual(storage.tokens.scope,'tool:du_an.danh_sach')
            self.assertIsNone(storage.tokens.refresh_token)
            self.assertIn(('POST','/oauth/token',200),requests)
        else:
            with self.assertLogs('mcp.client.auth.oauth2',level='ERROR'):
                with self.assertRaises(Exception): execute()
            self.assertIsNone(storage.tokens)
            self.assertFalse(callbacks)
            self.assertFalse(any(path == '/oauth/token' for _,path,_ in requests))
            self.assertEqual(sum(path == '/mcp' for _,path,_ in requests),1)
            with self.app.kho.ket_noi() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM unit_mcp_grants').fetchone()[0],0)
        self.assertEqual(decisions,['approved' if approve else 'denied'])
        self.assertIn(('POST','/mcp',401),requests)
        self.assertIn(('GET','/.well-known/oauth-protected-resource/mcp',200),requests)
        self.assertIn(('GET','/.well-known/oauth-authorization-server',200),requests)
        self.assertFalse(any(path == '/register' for _,path,_ in requests))

    def test_sdk_discovers_authorizes_and_exchanges_pkce_without_preset_token(self):
        self.exercise(True)

    def test_sdk_denial_does_not_exchange_token_or_call_tool(self):
        self.exercise(False)


if __name__ == '__main__': unittest.main()
