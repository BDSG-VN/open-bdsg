"""Quan sát HTTP polling của SDK thật; chỉ xuất metadata, không lưu body/token."""
import asyncio
import time
from urllib.parse import parse_qs, urlsplit


class QuanSatPolling:
    def __init__(self, record, phase):
        self._record, self._phase = record, phase
        self._rows = {'a': {}, 'c': {}}
        self._paths, self._finished = {}, {}
        self._blocked = {'a': 0, 'c': 0}
        self._tasks, self._errors = set(), []

    @staticmethod
    def _is_poll(request):
        parsed = urlsplit(request.url)
        return '/doc/' in parsed.path and parse_qs(parsed.query).get('transport') == ['polling']

    def attach(self, page, actor):
        if actor not in self._rows:
            raise ValueError('Chỉ nhận hai danh tính thử a/c')

        def started(request):
            if not self._is_poll(request):
                return
            # Giữ request sống trong lần thử để id không bị tái sử dụng.
            # URL/body chỉ ở bộ nhớ của Playwright, không đưa vào summary.
            self._paths[actor] = urlsplit(request.url).path
            self._rows[actor][id(request)] = {'request': request, 'method': request.method, 'status': None}
            if request.method == 'POST' and request.post_data:
                for packet in request.post_data.split('\x1e'):
                    self._record(actor, 'sent', packet)

        def finished(request):
            if self._is_poll(request):
                self._finished.setdefault(id(request), time.monotonic())

        async def consume(response):
            status = response.status
            try:
                row = self._rows[actor].get(id(response.request))
                if row is None:
                    raise ValueError('Thiếu request tương ứng')
                row['status'] = status
                if row['method'] == 'GET':
                    for packet in (await response.body()).decode('utf-8').split('\x1e'):
                        self._record(actor, 'received', packet)
            except Exception as error:
                self._errors.append({'actor': actor, 'status': status,
                    'phase': self._phase(), 'class': type(error).__name__})

        def response_received(response):
            if self._is_poll(response.request):
                task = asyncio.create_task(consume(response))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

        page.on('request', started)
        page.on('requestfinished', finished)
        page.on('requestfailed', finished)
        page.on('response', response_received)

    def blocker(self, actor):
        if actor not in self._blocked:
            raise ValueError('Chỉ nhận hai danh tính thử a/c')

        async def block(route):
            self._blocked[actor] += 1
            # Không connect_to_server: phép thử cần chính SDK tự fallback,
            # không được trộn frame WebSocket vào bằng chứng polling.
            await route.close(code=1008, reason='Synthetic polling transport coverage')
        return block

    def ready(self, actor):
        return all(any(row['method'] == method and row['status'] == 200
            for row in self._rows[actor].values()) for method in ('GET', 'POST'))

    def path(self, actor):
        return self._paths[actor]

    def pending(self, actor):
        return tuple(key for key, row in self._rows[actor].items()
            if row['method'] == 'GET' and key not in self._finished)

    def ended_by(self, pending, deadline):
        # Tập rỗng không phải bằng chứng đã hủy long-poll đang mở.
        return bool(pending) and all(self._finished.get(key, float('inf')) <= deadline for key in pending)

    async def drain(self):
        if self._tasks:
            _, pending = await asyncio.wait(tuple(self._tasks), timeout=2)
            if pending:
                raise TimeoutError('Chưa quan sát xong phản hồi polling')
        if any(error['status'] == 200 for error in self._errors):
            raise ValueError('Không đọc được phản hồi polling thành công')

    def summary(self):
        return {'blocked_websocket_attempts': dict(self._blocked),
            'polling_http_200': {actor: sum(row['status'] == 200 for row in rows.values())
                for actor, rows in self._rows.items()},
            'body_observer_errors': list(self._errors)}

    async def close(self):
        pending = tuple(self._tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
