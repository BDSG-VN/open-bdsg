"""Cổng cộng tác thử nghiệm: kiểm quyền lại khi truyền và khi kết nối nhàn rỗi.

Chưa nối production. Chỉ nhận đường cộng tác đã phân loại, không thay proxy
mã tĩnh/cache. Endpoint nội bộ do người vận hành đặt, không lấy từ HTTP.
"""
import asyncio
import argparse
import contextlib
import re
from urllib.parse import urlsplit

from aiohttp import (ClientError, ClientSession, ClientTimeout, ClientWSTimeout, DummyCookieJar,
                     TraceConfig, WSMsgType, web)
from yarl import URL

from duong_engine_office import KEY, VERSION, phan_loai


def _loopback(origin):
    parsed = urlsplit(origin)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment or not parsed.port):
        raise ValueError('Endpoint phải là HTTP loopback có cổng cố định')
    return origin.rstrip('/')


def tao_cong(*, engine_origin, auth_origin, public_origin, max_connections=64):
    """Tạo ứng dụng riêng; caller phải bind loopback và tắt access log URL/cookie."""
    engine_origin = _loopback(engine_origin)
    auth_origin = _loopback(auth_origin)
    if type(max_connections) is not int or not 1 <= max_connections <= 64:
        raise ValueError('Giới hạn kết nối phải từ 1 đến 64')
    public = urlsplit(public_origin)
    if (public.scheme != 'https' or not public.hostname or public.username or public.password
            or public.path or public.query or public.fragment):
        raise ValueError('Origin công khai phải là HTTPS không có đường dẫn')
    active = {}
    stopping = False

    @web.middleware
    async def upstream_error(request, handler):
        if stopping or len(active) >= max_connections:
            raise web.HTTPServiceUnavailable(text='Cổng cộng tác đang đầy', headers={'Retry-After': '1'})
        task = asyncio.current_task()
        active[task] = request.transport
        try:
            return await handler(request)
        except (ClientError, OSError, asyncio.TimeoutError):
            # Lỗi handshake có thể mang URL/token trong repr; không để
            # middleware mặc định ghi traceback của thư viện vào nhật ký.
            raise web.HTTPBadGateway(text='Kênh cộng tác chưa sẵn sàng') from None
        finally:
            active.pop(task, None)

    app = web.Application(client_max_size=8 * 1024 * 1024, middlewares=[upstream_error],
        handler_args={'auto_decompress': False})

    async def shutdown(_app):
        nonlocal stopping
        stopping = True
        pending = dict(active)
        for task in pending:
            task.cancel()
        if pending:
            # Hủy handler đi qua finally của hai transport. Chặn nhận mới
            # trước await đầu tiên để không tạo phiên ngoài tập đang dừng.
            await asyncio.wait(pending, timeout=2)
            for task, transport in pending.items():
                if transport is not None:
                    transport.close()

    app.on_shutdown.append(shutdown)

    async def sessions(_app):
        trace = TraceConfig()

        async def deny_redirect(_session, _context, _params):
            # ws_connect không có allow_redirects=False; hook chạy trước
            # request tiếp theo, kể cả redirect rời loopback hoặc đổi route.
            raise ClientError('Engine không được chuyển hướng')

        trace.on_request_redirect.append(deny_redirect)
        # Không chia cookie jar giữa các danh tính hoặc tin biến proxy môi trường.
        async with ClientSession(cookie_jar=DummyCookieJar(), trust_env=False,
                timeout=ClientTimeout(total=60), auto_decompress=False, trace_configs=[trace]) as session:
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
                                # Đo 18/11/2026: tải hai editor có lần auth
                                # vượt 750 ms dù quyền còn hợp lệ. Giữ deadline
                                # hữu hạn và chặn khi lỗi; không cache quyền.
                                timeout=ClientTimeout(total=1.5), allow_redirects=False) as response:
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
                        done, _ = await asyncio.wait((pending, watcher), timeout=60,
                            return_when=asyncio.FIRST_COMPLETED)
                        if not done:
                            raise web.HTTPGatewayTimeout()
                        if watcher in done:
                            raise web.HTTPForbidden()
                        return await pending
                    finally:
                        pending.cancel()
                        watcher.cancel()
                        await asyncio.gather(pending, watcher, return_exceptions=True)
                async with asyncio.timeout(3):
                    upstream = await session.ws_connect(target, headers=headers,
                        max_msg_size=8 * 1024 * 1024, compress=0, timeout=ClientWSTimeout(ws_close=0.5))
                async with upstream:
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


def main():
    parser = argparse.ArgumentParser(description='Cổng cộng tác Office thử nghiệm, chỉ nghe loopback')
    parser.add_argument('--listen-port', type=int, required=True)
    parser.add_argument('--engine-port', type=int, required=True)
    parser.add_argument('--auth-port', type=int, required=True)
    parser.add_argument('--public-origin', required=True)
    parser.add_argument('--max-connections', type=int, default=64)
    parser.add_argument('--check', action='store_true', help='Chỉ kiểm cấu hình, không mở cổng')
    args = parser.parse_args()
    ports = (args.listen_port, args.engine_port, args.auth_port)
    if any(not 1 <= port <= 65535 for port in ports) or len(set(ports)) != 3:
        parser.error('Ba cổng phải hợp lệ và khác nhau')
    try:
        app = tao_cong(engine_origin=f'http://127.0.0.1:{args.engine_port}',
            auth_origin=f'http://127.0.0.1:{args.auth_port}', public_origin=args.public_origin,
            max_connections=args.max_connections)
    except ValueError:
        parser.error('Cấu hình cổng cộng tác không hợp lệ')
    if not args.check:
        web.run_app(app, host='127.0.0.1', port=args.listen_port, access_log=None,
            print=None, shutdown_timeout=3, handler_cancellation=True)


if __name__ == '__main__':
    main()
