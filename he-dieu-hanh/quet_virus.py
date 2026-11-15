"""Quét bytes bằng clamd Unix socket; không đưa đường dẫn hoặc lệnh shell ra ngoài.

Chưa cấu hình khác với sạch. Khi đã bật, mất dịch vụ, quá hạn chữ ký hoặc
vượt giới hạn đều chặn xuất bản; không biến lỗi quét thành kết quả an toàn.
"""

import datetime
import hashlib
import os
import socket
import struct
import threading
import time


class LoiChuaQuetVirus(ValueError):
    """Không có bằng chứng quét hợp lệ, có thể thử lại khi dịch vụ phục hồi."""


class LoiPhatHienVirus(ValueError):
    """Tệp bị từ chối, không đưa tên nhận diện do bên ngoài cung cấp vào UI."""


class QuetVirus:
    MAX_BYTES = 8 * 1024 * 1024

    def __init__(self, path=None, timeout=12):
        self.path = (
            path if path is not None else os.environ.get("BDSG_CLAMAV_SOCKET", "")
        )
        self.timeout = timeout
        self._slots = threading.BoundedSemaphore(2)

    def _socket(self):
        if not self.path or not self.path.startswith("/"):
            raise LoiChuaQuetVirus("Chưa cấu hình quét virus")
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(self.timeout)
        try:
            connection.connect(self.path)
        except OSError:
            connection.close()
            raise LoiChuaQuetVirus("Bộ quét chưa sẵn sàng") from None
        return connection

    @staticmethod
    def _reply(connection):
        response = bytearray()
        while b"\0" not in response:
            part = connection.recv(1024)
            if not part or len(response) + len(part) > 4096:
                raise LoiChuaQuetVirus("Phản hồi bộ quét không hợp lệ")
            response.extend(part)
        return bytes(response).split(b"\0", 1)[0].decode("ascii", errors="strict")

    def _version(self):
        with self._socket() as connection:
            connection.sendall(b"zVERSION\0")
            version = self._reply(connection)
        try:
            engine, number, timestamp = version.split("/", 2)
            updated = (
                datetime.datetime.strptime(timestamp, "%a %b %d %H:%M:%S %Y")
                .replace(tzinfo=datetime.UTC)
                .timestamp()
            )
            if not engine.startswith("ClamAV ") or not number.isdigit():
                raise ValueError
            # VERSION biểu diễn giờ cục bộ daemon; vận hành đặt TZ=UTC.
            if not -3600 <= time.time() - updated <= 7 * 86400:
                raise ValueError
        except ValueError:
            raise LoiChuaQuetVirus("Chữ ký quét chưa hợp lệ hoặc quá hạn") from None
        return {
            "engine": engine,
            "signature_version": int(number),
            "signature_updated": updated,
        }

    def status(self):
        if not self.path:
            return {"state": "chua-cau-hinh"}
        try:
            return {"state": "san-sang", **self._version()}
        except (OSError, UnicodeError, LoiChuaQuetVirus):
            return {"state": "tam-khong-san-sang"}

    def scan(self, raw):
        digest = hashlib.sha256(raw).hexdigest()
        if not self.path:
            return {"virus_state": "chua-quet", "sha256": digest}
        if not isinstance(raw, bytes) or len(raw) > self.MAX_BYTES:
            raise LoiChuaQuetVirus("Tệp vượt giới hạn quét")
        if not self._slots.acquire(timeout=1):
            raise LoiChuaQuetVirus("Bộ quét đang bận")
        try:
            version = self._version()
            with self._socket() as connection:
                connection.sendall(b"zINSTREAM\0")
                for offset in range(0, len(raw), 65536):
                    part = raw[offset : offset + 65536]
                    connection.sendall(struct.pack("!I", len(part)) + part)
                connection.sendall(struct.pack("!I", 0))
                reply = self._reply(connection)
            if reply.endswith(" FOUND"):
                raise LoiPhatHienVirus("Tệp bị bộ quét từ chối")
            if reply != "stream: OK":
                raise LoiChuaQuetVirus("Bộ quét không xác nhận sạch")
            return {
                "virus_state": "khong-phat-hien",
                "sha256": digest,
                "scanned_at": time.time(),
                **version,
            }
        except (OSError, UnicodeError):
            raise LoiChuaQuetVirus("Không hoàn tất quét virus") from None
        finally:
            self._slots.release()
