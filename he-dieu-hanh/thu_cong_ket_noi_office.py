"""Kiểm qua HTTP/WebSocket thật; engine ngoài được thay bằng server loopback."""
import asyncio
import gzip
import unittest

try:
    from aiohttp import ClientSession, WSMsgType, web
    from aiohttp.test_utils import TestServer
except ModuleNotFoundError:
    raise unittest.SkipTest('Cần requirements-office-transport.txt cho cổng thử nghiệm')

from cong_ket_noi_office import tao_cong


class ThuCongKetNoiOffice(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.allowed = True
        self.auth_failure = False
        self.path = '/office-docs/doc/bdsg-' + 'a' * 32 + '/c/?EIO=4&transport=websocket'
        self.engine_closed = asyncio.Event()
        self.poll_started = asyncio.Event()
        self.poll_release = asyncio.Event()

        async def auth(request):
            if self.auth_failure:
                return web.Response(status=503)
            return web.Response(status=200 if self.allowed and request.headers.get('Cookie') == 'session=synthetic' else 403)

        async def engine(request):
            if request.query.get('transport') == 'polling':
                if request.method == 'POST':
                    return web.Response(body=await request.read())
                self.poll_started.set()
                await self.poll_release.wait()
                return web.Response(body=b'new-engine-data')
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            try:
                async for message in ws:
                    if message.type == WSMsgType.TEXT:
                        await ws.send_str(message.data)
                    elif message.type == WSMsgType.BINARY:
                        await ws.send_bytes(message.data)
            finally:
                self.engine_closed.set()
            return ws

        auth_app = web.Application()
        auth_app.router.add_get('/api/office-engine-auth', auth)
        engine_app = web.Application()
        engine_app.router.add_route('*', '/{tail:.*}', engine)
        self.auth = TestServer(auth_app)
        self.engine = TestServer(engine_app)
        await self.auth.start_server()
        await self.engine.start_server()
        self.addAsyncCleanup(self.auth.close)
        self.addAsyncCleanup(self.engine.close)
        self.proxy = TestServer(tao_cong(engine_origin=str(self.engine.make_url('')).rstrip('/'),
            auth_origin=str(self.auth.make_url('')).rstrip('/'), public_origin='https://office.example'))
        await self.proxy.start_server()
        self.addAsyncCleanup(self.proxy.close)
        self.client = ClientSession()
        self.addAsyncCleanup(self.client.close)

    async def test_idle_connection_closes_both_ends_after_revocation(self):
        async with self.client.ws_connect(self.proxy.make_url(self.path),
                headers={'Origin': 'https://office.example', 'Cookie': 'session=synthetic'}) as ws:
            await ws.send_str('before-revoke')
            self.assertEqual((await ws.receive(timeout=2)).data, 'before-revoke')
            self.allowed = False
            message = await ws.receive(timeout=5)
            self.assertIn(message.type, (WSMsgType.CLOSE, WSMsgType.CLOSED))
            await asyncio.wait_for(self.engine_closed.wait(), 2)

    async def test_pending_poll_is_cancelled_on_revocation_without_returning_engine_data(self):
        path = self.path.replace('transport=websocket', 'transport=polling')
        async def poll():
            async with self.client.get(self.proxy.make_url(path), headers={
                    'Origin': 'https://office.example', 'Cookie': 'session=synthetic'}) as response:
                return response.status, await response.read()
        task = asyncio.create_task(poll())
        try:
            await asyncio.wait_for(self.poll_started.wait(), 2)
            self.allowed = False
            status, body = await asyncio.wait_for(task, 5)
            self.assertEqual(status, 403)
            self.assertNotIn(b'new-engine-data', body)
        finally:
            self.poll_release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_same_origin_get_poll_works_without_origin_header(self):
        self.poll_release.set()
        async with self.client.get(self.proxy.make_url(self.path.replace('websocket', 'polling')),
                headers={'Cookie': 'session=synthetic'}) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.read(), b'new-engine-data')

    async def test_binary_and_poll_post_keep_exact_bytes_before_revocation(self):
        headers = {'Origin': 'https://office.example', 'Cookie': 'session=synthetic'}
        payload = b'\x00\xff\x01synthetic'
        async with self.client.ws_connect(self.proxy.make_url(self.path), headers=headers) as ws:
            await ws.send_bytes(payload)
            message = await ws.receive(timeout=2)
            self.assertEqual((message.type, message.data), (WSMsgType.BINARY, payload))
        async with self.client.post(self.proxy.make_url(self.path.replace('websocket', 'polling')),
                headers=headers, data=payload) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.read(), payload)

    async def test_auth_service_failure_closes_existing_socket(self):
        async with self.client.ws_connect(self.proxy.make_url(self.path), headers={
                'Origin': 'https://office.example', 'Cookie': 'session=synthetic'}) as ws:
            self.auth_failure = True
            self.assertIn((await ws.receive(timeout=5)).type, (WSMsgType.CLOSE, WSMsgType.CLOSED))

    async def test_new_connections_reject_foreign_origin_missing_cookie_or_mixed_key(self):
        for path, headers in (
                (self.path, {'Origin': 'https://other.example', 'Cookie': 'session=synthetic'}),
                (self.path, {'Origin': 'https://office.example'}),
                (self.path + '&docid=bdsg-' + 'b' * 32,
                    {'Origin': 'https://office.example', 'Cookie': 'session=synthetic'})):
            async with self.client.get(self.proxy.make_url(path), headers=headers) as response:
                self.assertEqual(response.status, 403)

    async def test_compressed_post_is_explicitly_rejected_without_rewriting_payload(self):
        async with self.client.post(self.proxy.make_url(self.path.replace('websocket', 'polling')),
                headers={'Origin': 'https://office.example', 'Cookie': 'session=synthetic',
                    'Content-Encoding': 'gzip'}, data=gzip.compress(b'synthetic-poll-body')) as response:
            self.assertEqual(response.status, 415)


if __name__ == '__main__':
    unittest.main()
