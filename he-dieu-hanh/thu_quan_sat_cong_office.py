"""Kiểm bộ đếm/biên xuất hữu hạn, không dùng dữ liệu khách hàng."""
import json
import unittest

from quan_sat_cong_office import QuanSatCongOffice


class ThuQuanSatCongOffice(unittest.TestCase):
    def test_bounded_export_filters_credentials_paths_and_payload(self):
        metrics = QuanSatCongOffice()
        for channel in range(1, 101):
            metrics.record({'event': 'auth', 'channel': channel, 'at': channel,
                'outcome': 'allowed', 'status': 200, 'seconds': .01,
                'cookie': 'private-cookie', 'url': '/private-path'})
            metrics.record({'event': 'channel_end', 'channel': channel, 'at': channel,
                'side': 'engine', 'mode': 'websocket', 'reason': 'eof', 'close_code': 1011,
                'body': 'private-document'})
        metrics.record({'event': 'auth', 'channel': 101, 'at': 101, 'outcome': 'timeout',
                        'seconds': 1.5, 'exception': 'private-exception'})
        result = metrics.snapshot()
        self.assertEqual(result['auth']['allowed'], 100)
        self.assertEqual(result['auth']['timeout'], 1)
        self.assertEqual(result['auth']['max_seconds'], 1.5)
        self.assertEqual(result['channel_end']['eof'], 100)
        self.assertEqual(len(result['recent_ends']), 32)
        self.assertEqual(len(result['recent_auth']), 1)
        raw = json.dumps(result)
        for private in ('private-cookie', '/private-path', 'private-document', 'private-exception'):
            self.assertNotIn(private, raw)

    def test_invalid_dynamic_labels_or_numbers_do_not_expand_export(self):
        metrics = QuanSatCongOffice()
        for index in range(100):
            metrics.record({'event': 'customer-' + str(index), 'channel': index})
        base = {'event': 'auth', 'channel': 1, 'outcome': 'allowed', 'status': 200, 'seconds': .1}
        for changes in ({'seconds': float('nan')}, {'seconds': float('inf')}, {'channel': True},
                        {'status': True}, {'seconds': -1}, {'outcome': 'private-label'},
                        {'outcome': 'timeout'}, {'at': float('nan')}, {'event': []},
                        {'outcome': []}, {'seconds': 2**10000}):
            metrics.record({**base, **changes})
        result = metrics.snapshot()
        self.assertEqual(result['auth']['allowed'], 0)
        self.assertEqual(result['auth']['timeout'], 0)
        self.assertEqual(result['recent_auth'], [])
        self.assertNotIn('customer-', json.dumps(result))

    def test_snapshot_cannot_mutate_future_reports(self):
        metrics = QuanSatCongOffice()
        metrics.record({'event': 'channel_end', 'channel': 1, 'at': 1,
                        'side': 'browser', 'mode': 'websocket', 'reason': 'eof', 'close_code': 1000})
        first = metrics.snapshot()
        first['recent_ends'][0]['reason'] = 'private-replacement'
        first['channel_end']['eof'] = -1
        second = metrics.snapshot()
        self.assertEqual(second['recent_ends'][0]['reason'], 'eof')
        self.assertEqual(second['channel_end']['eof'], 1)


if __name__ == '__main__':
    unittest.main()
