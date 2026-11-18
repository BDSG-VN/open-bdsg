"""Cổng cộng tác thử nghiệm: kiểm quyền lại khi truyền và khi kết nối nhàn rỗi.

Chưa nối production. Chỉ nhận đường cộng tác đã phân loại, không thay proxy
mã tĩnh/cache. Endpoint nội bộ do người vận hành đặt, không lấy từ HTTP.
"""
import asyncio
import contextlib
import re
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout, DummyCookieJar, WSMsgType, web
from yarl import URL

from duong_engine_office import KEY, VERSION, phan_loai


def _loopback(origin):
    parsed = urlsplit(origin)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment or not parsed.port):
        raise ValueError('Endpoint phải là HTTP loopback có cổng cố định')
    return origin.rstrip('/')


def tao_cong(*, engine_origin, auth_origin, public_origin):
    """Tạo ứng dụng riêng; caller phải bind loopback và tắt access log URL/cookie."""
    engine_origin = _loopback(engine_origin)
    auth_origin = _loopback(auth_origin)
    public = urlsplit(public_origin)
    if (public.scheme != 'https' or not public.hostname or public.username or public.password
            or public.path or public.query or public.fragment):
        raise ValueError('Origin công khai phải là HTTPS không có đường dẫn')
    @web.middleware
    async def upstream_error(request, handler):
        try:
            return await handler(request)
        except (ClientError, OSError, asyncio.TimeoutError):
            # Lỗi handshake có thể mang URL/token trong repr; không để
            # middleware mặc định ghi traceback của thư viện vào nhật ký.
            raise web.HTTPBadGateway(text='Kênh cộng tác chưa sẵn sàng') from None

    app = web.Application(client_max_size=8 * 1024 * 1024, middlewares=[upstream_error],
        handler_args={'auto_decompress': False})

    async def sessions(_app):
        # Không chia cookie jar giữa các danh tính hoặc tin biến proxy môi trường.
        async with ClientSession(cookie_jar=DummyCookieJar(), trust_env=False,
                timeout=ClientTimeout(total=60), auto_decompress=False) as session:
            async def handle(request):
                try:
                    kind, _key = phan_loai(request.raw_path)
                    route = request.raw_path.split('?', 1)[0]
                    if kind != 'document' or not re.fullmatch(
                            r'/office-docs/(?:' + VERSION + r'/)?doc/' + KEY + r'/c/?', route):
                        raise ValueError('Chỉ nhận kênh cộng tác')
                except ValueError:
                    raise web.HTTPForbidden()
                origin = request.headers.get('Origin')
                if (origin is not None and origin != public_origin) or (
                        origin is None and (request.method != 'GET' or request.headers.get('Upgrade'))):
                    raise web.HTTPForbidden()
                # Chưa có hợp đồng POST nén với engine: từ chối công khai thay
                # vì để framework giải nén rồi âm thầm thay byte/encoding.
                if request.headers.get('Content-Encoding'):
                    raise web.HTTPUnsupportedMediaType(text='Chưa hỗ trợ body cộng tác nén')

                async def allowed():
                    try:
                        async with session.get(auth_origin + '/api/office-engine-auth',
                                headers={'Cookie': request.headers.get('Cookie', ''),
                                    'X-BDSG-Engine-Path': request.raw_path},
                                timeout=ClientTimeout(total=0.75), allow_redirects=False) as response:
                            return response.status == 200
                    except (ClientError, OSError, asyncio.TimeoutError):
                        return False

                if not await allowed():
                    raise web.HTTPForbidden()
                headers = {'X-Forwarded-Host': public.netloc + '/office-docs',
                    'X-Forwarded-Proto': 'https', 'Origin': public_origin}
                # Cookie chỉ đến bộ kiểm quyền BDSG, không gửi sang engine.
                target = URL(engine_origin + request.raw_path[len('/office-docs'):], encoded=True)

                async def watch():
                    while True:
                        await asyncio.sleep(0.5)
                        if not await allowed():
                            return

                downstream = web.WebSocketResponse(max_msg_size=8 * 1024 * 1024, timeout=0.5)
                if not downstream.can_prepare(request).ok:
                    if request.method not in ('GET', 'POST') or request.headers.get('Upgrade'):
                        raise web.HTTPMethodNotAllowed(request.method, ['GET', 'POST'])

                    async def exchange():
                        body = await request.read()
                        if not await allowed():
                            raise web.HTTPForbidden()
                        if request.headers.get('Content-Type'):
                            headers['Content-Type'] = request.headers['Content-Type']
                        async with session.request(request.method, target, data=body, headers=headers,
                                allow_redirects=False) as response:
                            # Polling giữ nguyên gói byte nhưng chưa gửi header/body
                            # về client trước lần kiểm quyền cuối; không biến proxy
                            # này thành đường tải tệp không giới hạn bộ nhớ.
                            data = bytearray()
                            async for chunk in response.content.iter_chunked(65536):
                                if not await allowed():
                                    raise web.HTTPForbidden()
                                data.extend(chunk)
                                if len(data) > 8 * 1024 * 1024:
                                    raise web.HTTPBadGateway()
                            if not await allowed():
                                raise web.HTTPForbidden()
                            if 300 <= response.status < 400:
                                raise web.HTTPBadGateway()
                            outgoing = {'Cache-Control': 'no-store'}
                            for name in ('Content-Type', 'Content-Encoding'):
                                if name in response.headers:
                                    outgoing[name] = response.headers[name]
                            return web.Response(status=response.status, body=bytes(data), headers=outgoing)

                    pending, watcher = asyncio.create_task(exchange()), asyncio.create_task(watch())
                    try:
                        done, _ = await asyncio.wait((pending, watcher), return_when=asyncio.FIRST_COMPLETED)
                        if watcher in done:
                            raise web.HTTPForbidden()
                        return await pending
                    finally:
                        pending.cancel()
                        watcher.cancel()
                        await asyncio.gather(pending, watcher, return_exceptions=True)
                async with session.ws_connect(target, headers=headers,
                        max_msg_size=8 * 1024 * 1024, compress=0) as upstream:
                    if not await allowed():
                        raise web.HTTPForbidden()
                    await downstream.prepare(request)

                    async def pump(source, destination):
                        async for message in source:
                            if not await allowed():
                                return
                            async with asyncio.timeout(2):
                                if message.type == WSMsgType.TEXT:
                                    await destination.send_str(message.data)
                                elif message.type == WSMsgType.BINARY:
                                    await destination.send_bytes(message.data)
                                else:
                                    return

                    tasks = [asyncio.create_task(pump(downstream, upstream)),
                        asyncio.create_task(pump(upstream, downstream)), asyncio.create_task(watch())]
                    try:
                        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    finally:
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                        # Hủy truyền trước closing handshake: peer chậm không giữ
                        # cửa sổ cấp dữ liệu mở trong lúc chờ close ACK.
                        with contextlib.suppress(Exception):
                            async with asyncio.timeout(1):
                                await asyncio.gather(downstream.close(code=1008), upstream.close())
                    return downstream

            app.router.add_route('*', '/{tail:.*}', handle)
            yield

    app.cleanup_ctx.append(sessions)
    return app
