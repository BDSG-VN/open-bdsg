"""Phát lại interface sự kiện Playwright, không cần browser hoặc dữ liệu thật."""
import asyncio
import json
import time
import unittest
from types import SimpleNamespace

from quan_sat_office_polling import QuanSatPolling
from v29_thu_office_ws import frame_types, chot_bao_cao


class TrangThu:
    def __init__(self):
        self.handlers = {}

    def on(self, event, handler):
        self.handlers[event] = handler

    def emit(self, event, value):
        self.handlers[event](value)


class PhanHoiThu:
    def __init__(self, request, body, error=False):
        self.request, self.status, self.data, self.error = request, 200, body, error

    async def body(self):
        if self.error:
            raise RuntimeError('SYNTHETIC_SECRET không được xuất trong lỗi')
        return self.data


class ThuQuanSatPolling(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events = []
        def record(actor, direction, packet):
            self.events.extend({'actor': actor, 'direction': direction, 'type': kind, 'time': time.monotonic()}
                for kind in frame_types(packet))
        self.observer = QuanSatPolling(record, lambda: 'before-revoke')
        self.addAsyncCleanup(self.observer.close)
        self.page = TrangThu()
        self.observer.attach(self.page, 'c')

    def request(self, method='GET'):
        return SimpleNamespace(method=method, post_data='40{"token":"SYNTHETIC_SECRET"}',
            url='https://office-qa.example/office-docs/doc/bdsg-'+'a'*32+'/c/?transport=polling&token=SYNTHETIC_SECRET')

    async def test_coalesced_packets_and_http_lifecycle_are_observed_without_exporting_tokens(self):
        request = self.request()
        self.page.emit('request', request)
        pending = self.observer.pending('c')
        self.assertEqual(len(pending), 1)
        self.assertFalse(self.observer.ended_by(pending, time.monotonic()))
        self.page.emit('response', PhanHoiThu(request,
            b'42["message",{"type":"auth","token":"SYNTHETIC_SECRET"}]\x1e42["message",{"type":"saveChanges"}]'))
        self.page.emit('requestfinished', request)
        await self.observer.drain()
        self.assertEqual([(e['actor'], e['direction'], e['type']) for e in self.events],
            [('c', 'received', 'auth'), ('c', 'received', 'saveChanges')])
        self.assertTrue(self.observer.ended_by(pending, time.monotonic()+1))
        self.assertFalse(self.observer.ended_by((), time.monotonic()+1))
        self.assertFalse(self.observer.ready('c'))
        post = self.request('POST')
        self.page.emit('request', post)
        self.page.emit('response', PhanHoiThu(post, b'ok'))
        self.page.emit('requestfinished', post)
        await self.observer.drain()
        self.assertTrue(self.observer.ready('c'))
        self.assertFalse(self.observer.ready('a'))
        self.assertNotIn('SYNTHETIC_SECRET', json.dumps(self.observer.summary()))
        self.assertNotIn('office-qa.example', json.dumps(self.observer.summary()))

    async def test_unread_success_body_cannot_be_counted_as_security_pass_or_leak_error_text(self):
        request = self.request()
        self.page.emit('request', request)
        self.page.emit('response', PhanHoiThu(request, b'', error=True))
        with self.assertRaises(ValueError):
            await self.observer.drain()
        summary = self.observer.summary()
        self.assertEqual(summary['body_observer_errors'][0]['class'], 'RuntimeError')
        self.assertNotIn('SYNTHETIC_SECRET', json.dumps(summary))

    async def test_final_report_includes_late_changes_consumed_during_final_drain(self):
        request = self.request()
        self.page.emit('request', request)
        self.page.emit('response', PhanHoiThu(request, b'42["message",{"type":"saveChanges"}]'))
        self.assertEqual(self.events, [])
        result = await chot_bao_cao(self.events, time.monotonic()-1, True,
            polling=self.observer, new_status=403)
        self.assertEqual(result['revoked_actor_change_events_after_5s'], 1)
        self.assertFalse(result['secure_baseline'])


if __name__ == '__main__':
    unittest.main()
