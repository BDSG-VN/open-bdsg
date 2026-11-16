"""HTTPS cố định theo adapter, chặn redirect/DNS nội bộ và giới hạn phản hồi.

Không đọc proxy môi trường, không nhận URL từ tác vụ và không log payload.
Transport không tự retry POST: adapter quyết định nghiệp vụ nào có thể lặp.
"""

import http.client
import ipaddress
import json
import math
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode, urlsplit


class LoiTichHop(ValueError):
    def __init__(self, code, retry_after=0):
        self.code = code
        self.retry_after = max(0, retry_after)
        super().__init__(
            {
                "configuration_required": "Cần cấu hình hợp lệ trước khi kết nối",
                "authorization_required": "Nhà cung cấp yêu cầu cấp lại quyền",
                "permission_denied": "Tài khoản chưa có quyền cho thao tác này",
                "rate_limited": "Đã tới hạn mức; hãy thử lại sau",
                "provider_unavailable": "Nhà cung cấp tạm không sẵn sàng",
                "invalid_response": "Phản hồi nhà cung cấp chưa đúng hợp đồng",
                "unsafe_destination": "Địa chỉ kết nối không được phép",
                "response_too_large": "Trang dữ liệu vượt giới hạn phản hồi",
                "invalid_arguments": "Tham số tích hợp không hợp lệ",
                "connection_changed": "Kết nối đã thay đổi hoặc bị thu hồi",
                "busy": "Kết nối đang bận; hãy thử lại sau",
                "contract_pending": "Hợp đồng API này cần được nhà cung cấp xác nhận",
            }.get(code, "Không hoàn tất được thao tác tích hợp")
        )


@dataclass(frozen=True)
class PhanHoi:
    status: int
    headers: dict
    data: dict


def retry_after_seconds(value, now=None):
    now = time.time() if now is None else now
    if not isinstance(value, str):
        return 60
    value = value.strip()
    if value.isascii() and value.isdigit():
        # Giá trị lớn không được rút ngắn thành vài phút và gọi lại quá sớm.
        return int(value) if len(value) <= 12 else max(0, math.ceil(253402300799 - now))
    try:
        timestamp = parsedate_to_datetime(value).timestamp()
        return max(0, math.ceil(timestamp - now))
    except (ValueError, TypeError, OverflowError):
        return 60


class KetNoiGhimIP(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        connection = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(connection, server_hostname=self.host)
        except BaseException:
            connection.close()
            raise


class VanChuyenHTTPS:
    MAX_BYTES = 2 * 1024 * 1024

    def __init__(self, resolver=None, connector=None, timeout=12):
        self.resolver = resolver or socket.getaddrinfo
        self.connector = connector or KetNoiGhimIP
        self.timeout = timeout

    def request(
        self, host, method, path, headers=None, body=None, form=False, timeout=None
    ):
        timeout = self.timeout if timeout is None else timeout
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 1 <= timeout <= 60
        ):
            raise LoiTichHop("invalid_arguments")
        if method not in ("GET", "POST") or not isinstance(host, str):
            raise LoiTichHop("unsafe_destination")
        url = urlsplit("https://" + host + path)
        if (
            url.hostname != host
            or url.port not in (None, 443)
            or url.username
            or url.password
            or url.fragment
            or not path.startswith("/")
            or path.startswith("//")
            or "\r" in path
            or "\n" in path
        ):
            raise LoiTichHop("unsafe_destination")
        try:
            addresses = {
                row[4][0] for row in self.resolver(host, 443, type=socket.SOCK_STREAM)
            }
            if not addresses or any(
                not ipaddress.ip_address(address).is_global for address in addresses
            ):
                raise LoiTichHop("unsafe_destination")
            raw = None
            request_headers = {
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                **(headers or {}),
            }
            if body is not None:
                raw = (
                    urlencode(body).encode()
                    if form
                    else json.dumps(body, separators=(",", ":")).encode()
                )
                if len(raw) > 32768:
                    raise LoiTichHop("invalid_arguments")
                request_headers["Content-Type"] = (
                    "application/x-www-form-urlencoded" if form else "application/json"
                )
            connection = self.connector(host, min(addresses), timeout)
            started = time.monotonic()
            expired = threading.Event()

            def abort():
                expired.set()
                stream = getattr(connection, "sock", None)
                if stream:
                    try:
                        stream.shutdown(socket.SHUT_RDWR)
                        stream.close()
                    except OSError:
                        pass

            watchdog = threading.Timer(timeout, abort)
            watchdog.daemon = True
            watchdog.start()
            try:
                connection.request(method, path, body=raw, headers=request_headers)
                response = connection.getresponse()
                # Không dùng read(MAX) một lần: stream chậm có thể giữ thread quá lâu.
                chunks = bytearray()
                while True:
                    if expired.is_set() or time.monotonic() - started > timeout:
                        raise TimeoutError
                    block = response.read1(min(65536, self.MAX_BYTES + 1 - len(chunks)))
                    if not block:
                        break
                    chunks.extend(block)
                    if len(chunks) > self.MAX_BYTES:
                        raise LoiTichHop("response_too_large")
                result_headers = {
                    key.lower(): value for key, value in response.getheaders()
                }
                status = response.status
                if status in (401, 403):
                    raise LoiTichHop(
                        "authorization_required"
                        if status == 401
                        else "permission_denied"
                    )
                if status == 429:
                    raise LoiTichHop(
                        "rate_limited",
                        retry_after_seconds(result_headers.get("retry-after")),
                    )
                if status >= 500:
                    raise LoiTichHop("provider_unavailable", 30)
                if not 200 <= status < 300:
                    raise LoiTichHop("invalid_response")
                if result_headers.get("content-encoding", "identity") not in (
                    "",
                    "identity",
                ):
                    raise LoiTichHop("invalid_response")
                content_type = (
                    result_headers.get("content-type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )
                if content_type != "application/json" and not content_type.endswith(
                    "+json"
                ):
                    raise LoiTichHop("invalid_response")
                try:

                    def invalid_constant(_):
                        raise ValueError

                    data = json.loads(chunks, parse_constant=invalid_constant)
                except (ValueError, UnicodeError):
                    raise LoiTichHop("invalid_response") from None
                if not isinstance(data, dict):
                    raise LoiTichHop("invalid_response")
                return PhanHoi(status, result_headers, data)
            finally:
                watchdog.cancel()
                connection.close()
        except LoiTichHop:
            raise
        except (
            OSError,
            TimeoutError,
            http.client.HTTPException,
            UnicodeError,
            ValueError,
        ):
            raise LoiTichHop("provider_unavailable", 30) from None
