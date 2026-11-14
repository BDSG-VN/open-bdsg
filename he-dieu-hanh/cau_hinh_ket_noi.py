"""Quản lý đầu nối bằng cấu hình riêng; không xuất chứng thư qua API."""

import copy
import json
import os
import re
import secrets
import time
import threading
from functools import wraps
from urllib.parse import urlsplit


def serial(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)

    return call


class CauHinhKetNoi:
    def __init__(self, kho, client, catalogue, origin=None):
        self.kho, self.client = kho, client
        self.lock = threading.RLock()
        self.ids = {p["id"] for p in catalogue}
        self.own_host = urlsplit(origin).hostname if origin else None
        self.path = kho.root / "connections-private.json"
        self.base = copy.deepcopy(client.config)
        self.records = (
            json.loads(self.path.read_text(encoding="utf-8"))
            if self.path.is_file()
            else []
        )
        self._apply()

    def _auth(self, actor):
        if not actor or actor.get("role") != "quan-tri":
            raise PermissionError("Chỉ chủ quản được quản lý đầu nối")

    def _all(self):
        result = {c["platform_id"]: c for c in self.base}
        result.update({c["platform_id"]: c for c in self.records})
        return result

    def _apply(self):
        self.client.config = [
            copy.deepcopy(c) for c in self._all().values() if c.get("enabled", True)
        ]

    def _write(self, candidate):
        tmp = self.path.with_name("connections-" + secrets.token_hex(8) + ".tmp")
        try:
            fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(candidate, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
            self.records = candidate
            self._apply()
        finally:
            tmp.unlink(missing_ok=True)

    def _put(self, config):
        self._write(
            [c for c in self.records if c["platform_id"] != config["platform_id"]]
            + [config]
        )

    @staticmethod
    def _public(c):
        return {
            "platform_id": c["platform_id"],
            "url": c["url"],
            "enabled": c.get("enabled", True),
            "has_token": bool(c.get("token") or c.get("token_env")),
            "state": c.get("state", "da-khai-bao"),
            "read_tools": c.get("read_tools", []),
            "write_tools": c.get("write_tools", []),
            "checked_at": c.get("checked_at"),
            "discovered_tools": c.get("discovered_tools", []),
            "tools_complete": c.get("tools_complete", False),
        }

    def list(self, actor):
        self._auth(actor)
        return {"connections": [self._public(c) for c in self._all().values()]}

    @serial
    def save(self, actor, data):
        self._auth(actor)
        if not isinstance(data, dict) or set(data) - {
            "platform_id",
            "url",
            "token",
            "read_tools",
            "write_tools",
            "allow_writes",
        }:
            raise ValueError("Cấu hình đầu nối không hợp lệ")
        platform_id, url = data.get("platform_id"), data.get("url")
        if (
            not isinstance(platform_id, str)
            or platform_id not in self.ids
            or not isinstance(url, str)
            or len(url) > 1000
        ):
            raise ValueError("Cần chọn nền tảng và địa chỉ MCP hợp lệ")
        u = urlsplit(url)
        if (
            u.scheme != "https"
            or not u.hostname
            or not u.hostname.endswith(".bdsg.vn")
            or u.port not in (None, 443)
            or u.username
            or u.password
            or u.query
            or u.fragment
            or any(ord(x) < 33 for x in url)
        ):
            raise ValueError(
                "Chỉ nhận endpoint HTTPS trong miền con BDSG, không kèm mật khẩu hoặc query"
            )
        if u.hostname == self.own_host:
            raise ValueError(
                "Không nối cổng Thanh Hoá ngược vào chính nó; hãy chọn endpoint của nền tảng gốc"
            )
        names = data.get("read_tools", [])
        if (
            not isinstance(names, list)
            or len(names) > 50
            or any(
                not isinstance(n, str)
                or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", n)
                for n in names
            )
            or len(set(names)) != len(names)
        ):
            raise ValueError("Danh sách công cụ đọc không hợp lệ")
        writes = data.get("write_tools", [])
        if (
            not isinstance(writes, list)
            or len(writes) > 20
            or any(
                not isinstance(n, str)
                or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", n)
                for n in writes
            )
            or len(set(writes)) != len(writes)
            or set(writes) & set(names)
        ):
            raise ValueError("Danh sách công cụ ghi không hợp lệ")
        if writes and data.get("allow_writes") is not True:
            raise ValueError("Cần chủ quản xác nhận cấp tên công cụ ghi cụ thể")
        previous = self._all().get(platform_id, {})
        token = data.get("token", "")
        if (
            not isinstance(token, str)
            or len(token) > 4096
            or any(ord(x) < 33 or ord(x) > 126 for x in token)
        ):
            raise ValueError("Chứng thư không hợp lệ")
        if not token:
            if previous.get("url") != url or not previous.get("enabled", True):
                raise ValueError("Cần chứng thư mới khi khai báo hoặc đổi endpoint")
            token = previous.get("token", "")
        token_env = (
            previous.get("token_env", "")
            if previous.get("url") == url and not token
            else ""
        )
        if not token and not token_env:
            raise ValueError("Cần chứng thư đầu nối")
        config = {
            "platform_id": platform_id,
            "url": url,
            "token": token,
            "token_env": token_env,
            "read_tools": names,
            "write_tools": writes,
            "roles": ["quan-tri"],
            "enabled": True,
            "state": "da-khai-bao",
            "checked_at": None,
            "discovered_tools": [],
            "tools_complete": False,
        }
        self._put(config)
        self.kho.su_kien(actor["id"], "khai-bao-dau-noi", platform_id)
        return self._public(config)

    @serial
    def probe(self, actor, platform_id):
        self._auth(actor)
        config = copy.deepcopy(self._all().get(platform_id))
        if not config or not config.get("enabled", True):
            raise ValueError("Đầu nối chưa khai báo hoặc đã ngắt")
        config["checked_at"] = time.time()
        try:
            result = self.client.kiem_tra(config)
            tools = result.get("tools")
            if not isinstance(tools, list) or len(tools) > 1000:
                raise ValueError("Danh mục công cụ không hợp lệ")
            names = [t.get("name") for t in tools if isinstance(t, dict)]
            if len(names) != len(tools) or any(
                not isinstance(n, str)
                or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", n)
                for n in names
            ):
                raise ValueError("Tên công cụ không hợp lệ")
            config.update(
                state="da-xac-minh",
                discovered_tools=list(dict.fromkeys(names))[:100],
                tools_complete=not result.get("nextCursor") and len(names) <= 100,
            )
        except Exception:
            config.update(
                state="loi-ket-noi", discovered_tools=[], tools_complete=False
            )
        self._put(config)
        self.kho.su_kien(actor["id"], "kiem-tra-dau-noi", platform_id)
        return self._public(config)

    @serial
    def disconnect(self, actor, platform_id):
        self._auth(actor)
        config = copy.deepcopy(self._all().get(platform_id))
        if not config:
            raise ValueError("Chưa có đầu nối cho nền tảng này")
        config.update(
            enabled=False,
            token="",
            token_env="",
            state="da-ngat",
            read_tools=[],
            write_tools=[],
            discovered_tools=[],
            checked_at=None,
        )
        self._put(config)
        self.kho.su_kien(actor["id"], "ngat-dau-noi", platform_id)
        return self._public(config)
