"""Kiểm qua HTTP/WebSocket thật; engine ngoài được thay bằng server loopback."""
import asyncio
import gzip
import unittest

try:
    from aiohttp import ClientSession, WSServerHandshakeError, WSMsgType, web
    from aiohttp.test_utils import TestServer
except ModuleNotFoundError:
    raise unittest.SkipTest('Cần requirements-office-transport.txt cho cổng thử nghiệm')

from cong_ket_noi_office import tao_cong


class ThuCongKetNoiOffice(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.allowed = True
        self.auth_failure = False
        self.auth_slow = False
        self.auth_release = asyncio.Event()
        self.handshake_release = asyncio.Event()
        self.path = '/office-docs/doc/bdsg-' + 'a' * 32 + '/c/?EIO=4&transport=websocket'
        self.engine_closed = asyncio.Event()
        self.poll_started = asyncio.Event()
        self.poll_release = asyncio.Event()
        self.publish = asyncio.Queue()
        received = []

        async def auth(request):
            if self.auth_slow:
                await self.auth_release.wait()
            if self.auth_failure:
                return web.Response(status=503)
            return web.Response(status=200 if self.allowed and request.headers.get('Cookie') == 'session=synthetic' else 403)

        async def engine(request):
            if request.path == '/messages':
                return web.json_response(received)
            if request.query.get('redirect') == '1':
                raise web.HTTPFound('/unexpected')
            if request.query.get('slow') == '1':
                await self.handshake_release.wait()
                return web.Response(status=503)
            if request.query.get('transport') == 'polling':
                if request.method == 'POST':
                    return web.Response(body=await request.read())
                self.poll_started.set()
                await self.poll_release.wait()
                return web.Response(body=b'new-engine-data')
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            async def publish():
                while True:
                    await ws.send_str(await self.publish.get())
            sender = asyncio.create_task(publish())
            try:
                async for message in ws:
                    if message.type == WSMsgType.TEXT:
                        received.append(message.data)
                        await ws.send_str(message.data)
                    elif message.type == WSMsgType.BINARY:
                        await ws.send_bytes(message.data)
            finally:
                # Ghi nhận iterator socket đã kết thúc trước await dọn sender:
                # aiohttp có thể hủy handler khi peer đóng transport sau ACK.
                self.engine_closed.set()
                sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)
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

    async def test_stopped_app_refuses_new_channels(self):
        await self.proxy.app.shutdown()
        async with self.client.get(self.proxy.make_url(self.path), headers={
                'Origin': 'https://office.example', 'Cookie': 'session=synthetic'}) as response:
            self.assertEqual(response.status, 503)

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

    async def test_capacity_refuses_new_connection_without_interrupting_existing_one(self):
        proxy = TestServer(tao_cong(engine_origin=str(self.engine.make_url('')).rstrip('/'),
            auth_origin=str(self.auth.make_url('')).rstrip('/'), public_origin='https://office.example',
            max_connections=1))
        await proxy.start_server()
        self.addAsyncCleanup(proxy.close)
        headers = {'Origin': 'https://office.example', 'Cookie': 'session=synthetic'}
        async with self.client.ws_connect(proxy.make_url(self.path), headers=headers) as ws:
            async with self.client.get(proxy.make_url(self.path), headers=headers) as response:
                self.assertEqual(response.status, 503)
            await ws.send_str('still-authorized')
            self.assertEqual((await ws.receive(timeout=2)).data, 'still-authorized')

    async def test_shutdown_closes_live_channel_at_both_ends(self):
        async with self.client.ws_connect(self.proxy.make_url(self.path), headers={
                'Origin': 'https://office.example', 'Cookie': 'session=synthetic'}) as ws:
            await asyncio.wait_for(self.proxy.app.shutdown(), 3)
            self.assertIn((await ws.receive(timeout=2)).type,
                (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR))
            await asyncio.wait_for(self.engine_closed.wait(), 2)

    async def test_revocation_blocks_new_engine_message_before_idle_watch(self):
        async with self.client.ws_connect(self.proxy.make_url(self.path), headers={
                'Origin': 'https://office.example', 'Cookie': 'session=synthetic'}) as ws:
            self.allowed = False
            await self.publish.put('new-confidential-content')
            message = await ws.receive(timeout=5)
            self.assertIn(message.type, (WSMsgType.CLOSE, WSMsgType.CLOSED))

    async def test_revocation_blocks_client_edit_before_engine_receives_it(self):
        async with self.client.ws_connect(self.proxy.make_url(self.path), headers={
                'Origin': 'https://office.example', 'Cookie': 'session=synthetic'}) as ws:
            await ws.send_str('authorized-edit')
            self.assertEqual((await ws.receive(timeout=2)).data, 'authorized-edit')
            self.allowed = False
            await ws.send_str('revoked-edit')
            self.assertIn((await ws.receive(timeout=5)).type, (WSMsgType.CLOSE, WSMsgType.CLOSED))
            await asyncio.wait_for(self.engine_closed.wait(), 2)
            async with self.client.get(self.engine.make_url('/messages')) as response:
                self.assertEqual(await response.json(), ['authorized-edit'])

    async def test_websocket_upstream_redirect_is_not_followed(self):
        with self.assertRaises(WSServerHandshakeError) as raised:
            async with self.client.ws_connect(self.proxy.make_url(self.path + '&redirect=1'),
                    headers={'Origin': 'https://office.example', 'Cookie': 'session=synthetic'}):
                pass
        self.assertEqual(raised.exception.status, 502)

    async def test_slow_upstream_handshake_is_bounded(self):
        try:
            async with asyncio.timeout(5):
                with self.assertRaises(WSServerHandshakeError) as raised:
                    async with self.client.ws_connect(self.proxy.make_url(self.path + '&slow=1'),
                            headers={'Origin': 'https://office.example', 'Cookie': 'session=synthetic'}):
                        pass
                self.assertEqual(raised.exception.status, 502)
        finally:
            self.handshake_release.set()

    async def test_slow_auth_fails_closed_without_opening_channel(self):
        self.auth_slow = True
        try:
            async with asyncio.timeout(2):
                with self.assertRaises(WSServerHandshakeError) as raised:
                    async with self.client.ws_connect(self.proxy.make_url(self.path), headers={
                            'Origin': 'https://office.example', 'Cookie': 'session=synthetic'}):
                        pass
                self.assertEqual(raised.exception.status, 403)
        finally:
            self.auth_release.set()


if __name__ == '__main__':
    unittest.main()
