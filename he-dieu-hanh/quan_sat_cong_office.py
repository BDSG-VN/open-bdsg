"""Bộ đếm chẩn đoán hữu hạn; chỉ nhận nhãn và số đã biết, không giữ request."""
import math
import time
from collections import deque
from datetime import datetime, timezone


class QuanSatCongOffice:
    def __init__(self):
        self._auth = dict.fromkeys(('allowed', 'denied', 'unavailable', 'timeout', 'network_error'), 0)
        self._ends = dict.fromkeys(('eof', 'auth_failed', 'frame_error', 'send_timeout', 'network_error'), 0)
        self._transport = dict.fromkeys(('timeout', 'network_error'), 0)
        self._max_seconds = 0
        self._recent_auth = deque(maxlen=32)
        self._recent_ends = deque(maxlen=32)

    @staticmethod
    def _number(value, maximum):
        return type(value) in (int, float) and 0 <= value <= maximum and math.isfinite(value)

    def record(self, value):
        if type(value) is not dict:
            return
        event, channel = value.get('event'), value.get('channel')
        at = value.get('at', time.monotonic())
        if (type(event) is not str or type(channel) is not int
                or not 0 <= channel <= 2**31 - 1 or not self._number(at, 10**12)):
            return
        entry = {'event': event, 'channel': channel, 'at': round(at, 4)}
        if event == 'auth':
            outcome, seconds, status = value.get('outcome'), value.get('seconds'), value.get('status')
            if channel == 0 or type(outcome) is not str or outcome not in self._auth or not self._number(seconds, 3600):
                return
            if outcome in ('timeout', 'network_error'):
                if 'status' in value:
                    return
            elif (type(status) is not int or not 100 <= status <= 599
                    or (outcome == 'allowed') != (status == 200)
                    or (outcome == 'denied') != (status in (401, 403))):
                return
            entry.update(outcome=outcome, seconds=round(seconds, 4))
            if status is not None:
                entry['status'] = status
            self._auth[outcome] += 1
            self._max_seconds = max(self._max_seconds, seconds)
            # Lưu riêng lỗi/chậm để kết nối còn chạy không đẩy mất bằng chứng đóng.
            if outcome != 'allowed' or seconds >= .5:
                self._recent_auth.append(entry)
        elif event == 'channel_end':
            reason, side, mode = value.get('reason'), value.get('side'), value.get('mode')
            code = value.get('close_code')
            if (channel == 0 or type(reason) is not str or reason not in self._ends or side not in ('browser', 'engine', 'auth')
                    or mode not in ('websocket', 'polling')
                    or (code is not None and (type(code) is not int or not 1000 <= code <= 4999))):
                return
            entry.update(reason=reason, side=side, mode=mode, close_code=code)
            self._ends[reason] += 1
            self._recent_ends.append(entry)
        elif event == 'transport_error':
            reason = value.get('reason')
            if type(reason) is not str or reason not in self._transport:
                return
            entry['reason'] = reason
            self._transport[reason] += 1
            self._recent_ends.append(entry)

    def snapshot(self):
        return {'schema': 1, 'checked_at': datetime.now(timezone.utc).isoformat(),
            'auth': {**self._auth, 'max_seconds': round(self._max_seconds, 4)},
            'channel_end': dict(self._ends), 'transport_error': dict(self._transport),
            'recent_auth': [dict(entry) for entry in self._recent_auth],
            'recent_ends': [dict(entry) for entry in self._recent_ends]}
