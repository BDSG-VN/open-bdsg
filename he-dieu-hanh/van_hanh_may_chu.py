"""Giám sát lõi không trả dữ liệu nghiệp vụ hoặc cấu hình bí mật."""

import shutil
import os
import re
import sqlite3
import threading
import time
from contextlib import closing
from http.server import ThreadingHTTPServer


class VanHanhMayChu:
    def __init__(self, app, min_free_bytes=256 * 1024 * 1024):
        self.app = app
        self.started = time.monotonic()
        self.min_free_bytes = min_free_bytes
        self.draining = threading.Event()

    def readiness(self):
        checks = {
            "database": False,
            "storage": False,
            "accepting": not self.draining.is_set(),
        }
        try:
            # Không dùng Kho.ket_noi: probe không được tạo DB mất tích hoặc đổi WAL.
            uri = self.app.kho.db.resolve().as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=1)) as db:
                checks["database"] = (
                    db.execute("SELECT count(*) FROM chu").fetchone()[0] == 1
                )
            checks["storage"] = (
                shutil.disk_usage(self.app.kho.root).free >= self.min_free_bytes
            )
        except (OSError, sqlite3.Error):
            pass
        scheduler = self.app.schedules.thread
        checks["scheduler"] = scheduler is None or scheduler.is_alive()
        return {
            "status": "ready" if all(checks.values()) else "not-ready",
            "checks": checks,
        }

    def report(self):
        result = self.readiness()
        result.update(
            {"release": self.release(), "uptime_seconds": int(time.monotonic() - self.started)}
        )
        try:
            uri = self.app.kho.db.resolve().as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=1)) as db:
                result["tasks"] = dict(
                    db.execute(
                        "SELECT status,count(*) FROM cong_viec_tasks GROUP BY status"
                    )
                )
        except (OSError, sqlite3.Error):
            result["tasks"] = None
        result["capabilities"] = {
            "office": self.app.office_editor.status()["state"],
            "antivirus": "configured"
            if self.app.office.scanner.path
            else "not-configured",
            "google": "configured"
            if self.app.google_office.config and self.app.google_office.aes
            else "not-configured",
            "google_account_access": "requires-per-user-consent",
            "platforms": len(self.app.catalogue),
            "configured_connectors": len(self.app.core.connections.tom_tat()),
        }
        # Cấu hình không chứng minh dịch vụ ngoài sẵn sàng; không gọi mạng ở probe.
        return result

    @staticmethod
    def release():
        value = os.environ.get("BDSG_RELEASE_ID", "")
        return value if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", value) else "unknown"


class MayChuCoGioiHan(ThreadingHTTPServer):
    """Chặn trước khi tạo luồng; nginx vẫn chịu trách nhiệm TLS/rate limit."""

    daemon_threads = False
    block_on_close = True
    request_queue_size = 64

    def __init__(self, address, handler, max_connections=32, socket_timeout=12):
        self._slots = threading.BoundedSemaphore(max_connections)
        self.socket_timeout = socket_timeout
        super().__init__(address, handler)

    def get_request(self):
        connection, address = super().get_request()
        # Đặt trước khi parse request-line/header, kể cả client không gửi byte nào.
        connection.settimeout(self.socket_timeout)
        return connection, address

    def process_request(self, request, address):
        if not self._slots.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\nRetry-After: 1\r\n\r\n"
                )
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self._slots.release()
