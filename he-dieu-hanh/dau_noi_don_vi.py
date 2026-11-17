"""Cấu hình đầu nối thuộc đơn vị, không thay adapter hoặc cấu hình toàn cổng."""
import copy
import json
import re
import secrets
import time
from urllib.parse import urlsplit

from mcp_truyen_tai import TruyenTaiMCP, endpoint_https_bdsg


class DauNoiDonVi:
    def __init__(self, kho, units, catalogue, *, origin, transport=None):
        self.kho, self.units = kho, units
        self.ids = frozenset(product["id"] for product in catalogue)
        self.own_host = urlsplit(origin).hostname
        self.transport = transport if transport is not None else TruyenTaiMCP()
        with kho.ket_noi() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS unit_connectors(
                unit_id TEXT NOT NULL REFERENCES don_vi(id),platform_id TEXT NOT NULL,
                revision TEXT NOT NULL,document TEXT NOT NULL,
                PRIMARY KEY(unit_id,platform_id))""")

    def _scope(self, actor, db, admin=False):
        scope = self.units.require(actor, db)
        if admin and scope.role != "admin":
            raise PermissionError("Chỉ quản trị đơn vị được cấu hình đầu nối")
        return scope

    @staticmethod
    def _read(db, unit_id, platform_id):
        row = db.execute("SELECT document FROM unit_connectors WHERE unit_id=? AND platform_id=?",
                         (unit_id, platform_id)).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def _public(config):
        return {key: config[key] for key in (
            "platform_id", "url", "enabled", "revision", "state", "read_tools",
            "read_roles", "checked_at", "discovered_tools", "tools_complete")} | {
                "has_token": bool(config["token"]), "write_tools": []}

    def list(self, actor):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN")
            scope = self._scope(actor, db, True)
            rows = db.execute("SELECT document FROM unit_connectors WHERE unit_id=? ORDER BY platform_id",
                              (scope.unit_id,)).fetchall()
            return {"connections": [self._public(json.loads(row[0])) for row in rows]}

    def summary(self, actor):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN")
            scope = self._scope(actor, db)
            rows = db.execute("SELECT document FROM unit_connectors WHERE unit_id=? ORDER BY platform_id",
                              (scope.unit_id,)).fetchall()
            result = []
            for row in rows:
                config = json.loads(row[0])
                allowed = config["enabled"] and config["state"] == "da-xac-minh" and scope.role in config["read_roles"]
                result.append({key: config[key] for key in ("platform_id", "state", "checked_at", "revision")} | {
                    "read_tools": [name for name in config["read_tools"] if name in config["discovered_tools"]] if allowed else [],
                    "write_tools": []})
            return result

    def _candidate(self, data, previous):
        if not isinstance(data, dict) or set(data) - {
                "platform_id", "url", "token", "read_tools", "read_roles", "write_tools", "allow_writes"}:
            raise ValueError("Cấu hình đầu nối đơn vị không hợp lệ")
        if (not isinstance(data.get("write_tools", []), list) or data.get("write_tools")
                or data.get("allow_writes", False) is not False):
            raise ValueError("Công cụ ghi cần cơ chế phê duyệt theo đơn vị trước khi được bật")
        platform, url = data.get("platform_id"), data.get("url")
        if not isinstance(platform, str) or platform not in self.ids or not isinstance(url, str) or len(url) > 1000:
            raise ValueError("Cần chọn nền tảng và endpoint hợp lệ")
        host, _path = endpoint_https_bdsg(url)
        if host == self.own_host:
            raise ValueError("Không nối ngược chính cổng Thanh Hoá")
        tools, roles = data.get("read_tools", []), data.get("read_roles", ["admin"])
        if (not isinstance(tools, list) or len(tools) > 50 or any(
                not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", name) for name in tools)
                or len(set(tools)) != len(tools)):
            raise ValueError("Danh sách công cụ đọc không hợp lệ")
        if (not isinstance(roles, list) or not roles or len(roles) > 2
                or any(role not in ("admin", "member") for role in roles) or len(set(roles)) != len(roles)):
            raise ValueError("Vai trò đọc phải được cấp rõ trong đơn vị")
        token = data.get("token", "")
        if not isinstance(token, str) or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise ValueError("Chứng thư đầu nối không hợp lệ")
        if not token:
            if not previous or not previous["enabled"] or previous["url"] != url:
                raise ValueError("Cần chứng thư mới khi khai báo, đổi endpoint hoặc kết nối lại")
            token = previous["token"]
        return {"platform_id": platform, "url": url, "token": token, "enabled": True,
                "read_tools": list(tools), "read_roles": list(roles), "revision": secrets.token_hex(16),
                "state": "da-khai-bao", "checked_at": None, "discovered_tools": [], "tools_complete": False}

    def save(self, actor, data):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            scope = self._scope(actor, db, True)
            platform = data.get("platform_id") if isinstance(data, dict) else None
            previous = self._read(db, scope.unit_id, platform) if isinstance(platform, str) else None
            candidate = self._candidate(data, previous)
            db.execute("INSERT INTO unit_connectors VALUES(?,?,?,?) ON CONFLICT(unit_id,platform_id) DO UPDATE SET revision=excluded.revision,document=excluded.document",
                       (scope.unit_id, candidate["platform_id"], candidate["revision"], json.dumps(candidate, ensure_ascii=False)))
            self.units._audit(db, actor["id"], "khai-bao-dau-noi-don-vi", scope.unit_id+":"+candidate["platform_id"])
            return self._public(candidate)

    def disconnect(self, actor, platform_id):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            scope = self._scope(actor, db, True)
            current = self._read(db, scope.unit_id, platform_id)
            if current is None:
                raise ValueError("Chưa khai báo đầu nối trong đơn vị")
            current.update(enabled=False, token="", state="da-ngat", read_tools=[],
                           discovered_tools=[], tools_complete=False, checked_at=None,
                           revision=secrets.token_hex(16))
            db.execute("UPDATE unit_connectors SET revision=?,document=? WHERE unit_id=? AND platform_id=?",
                       (current["revision"], json.dumps(current, ensure_ascii=False), scope.unit_id, platform_id))
            self.units._audit(db, actor["id"], "ngat-dau-noi-don-vi", scope.unit_id+":"+platform_id)
            return self._public(current)

    def _capture(self, actor, platform_id, *, admin=False, tool=None):
        if not isinstance(platform_id, str) or platform_id not in self.ids:
            raise ValueError("Nền tảng không hợp lệ")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN")
            scope = self._scope(actor, db, admin)
            config = self._read(db, scope.unit_id, platform_id)
            if not config or not config["enabled"]:
                raise PermissionError("Chưa có đầu nối còn hiệu lực trong đơn vị")
            if tool is not None and (config["state"] != "da-xac-minh"
                    or scope.role not in config["read_roles"] or tool not in config["read_tools"]
                    or tool not in config["discovered_tools"]):
                raise PermissionError("Công cụ đọc chưa được cấp và xác minh cho vai trò này")
        return scope, config

    def _check(self, db, actor, scope, config, *, admin=False):
        current_scope = self._scope(actor, db, admin)
        current = self._read(db, current_scope.unit_id, config["platform_id"])
        if (current_scope != scope or not current or not current["enabled"]
                or current["revision"] != config["revision"]):
            raise PermissionError("Phạm vi hoặc cấu hình đầu nối đã thay đổi")

    def _guard(self, actor, scope, config, *, admin=False):
        def guard():
            with self.kho.ket_noi() as db:
                db.execute("BEGIN")
                self._check(db, actor, scope, config, admin=admin)
        return guard

    def _send(self, config, method, parameters, guard):
        if self.transport is None:
            raise ValueError("Transport đầu nối chưa sẵn sàng")
        guard()
        return self.transport.goi(copy.deepcopy(config), method, parameters, guard)

    def probe(self, actor, platform_id):
        scope, config = self._capture(actor, platform_id, admin=True)
        guard = self._guard(actor, scope, config, admin=True)
        state, names, complete = "loi-ket-noi", [], False
        try:
            result = self._send(config, "tools/list", {}, guard)
            tools = result.get("tools")
            if not isinstance(tools, list) or len(tools) > 1000:
                raise ValueError("Danh mục công cụ không hợp lệ")
            for tool in tools:
                name = tool.get("name") if isinstance(tool, dict) else None
                if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", name)
                        or config["token"] in name):
                    raise ValueError("Tên công cụ không hợp lệ")
                names.append(name)
            complete = not result.get("nextCursor") and len(names) <= 100
            names, state = list(dict.fromkeys(names))[:100], "da-xac-minh"
        except Exception:
            # Phản hồi/ngoại lệ upstream có thể chứa chứng thư, không lưu nguyên văn.
            names, complete = [], False
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check(db, actor, scope, config, admin=True)
            config.update(state=state, checked_at=time.time(), discovered_tools=names,
                          tools_complete=complete, revision=secrets.token_hex(16))
            db.execute("UPDATE unit_connectors SET revision=?,document=? WHERE unit_id=? AND platform_id=?",
                       (config["revision"], json.dumps(config, ensure_ascii=False), scope.unit_id, platform_id))
            self.units._audit(db, actor["id"], "kiem-tra-dau-noi-don-vi", scope.unit_id+":"+platform_id)
            return self._public(config)

    @staticmethod
    def _redact(value, token):
        if isinstance(value, str):
            return value.replace(token, "<CHUNG-THU-DA-CHE>")
        if isinstance(value, list):
            return [DauNoiDonVi._redact(item, token) for item in value]
        if isinstance(value, dict):
            return {DauNoiDonVi._redact(key, token): DauNoiDonVi._redact(item, token)
                    for key, item in value.items()}
        return value

    def call(self, actor, platform_id, tool, arguments, ghi=False, *, expected_revision=None, guard=None):
        if ghi:
            raise PermissionError("Chưa mở công cụ ghi khi phê duyệt đơn vị chưa sẵn sàng")
        if not isinstance(tool, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", tool):
            raise ValueError("Cần tên công cụ cụ thể")
        if not isinstance(arguments, dict) or len(json.dumps(arguments, allow_nan=False).encode()) > 48*1024:
            raise ValueError("Tham số công cụ phải là object giới hạn 48 KiB")
        scope, config = self._capture(actor, platform_id, tool=tool)
        if expected_revision is not None and expected_revision != config['revision']:
            raise PermissionError('Cấu hình đầu nối khác bản đã giao cho tác vụ')
        connector_guard = self._guard(actor, scope, config)
        task_guard = guard
        def guard():
            if task_guard is not None: task_guard()
            connector_guard()
        try:
            result = self._send(config, "tools/call", {"name": tool, "arguments": arguments}, guard)
        except Exception:
            guard()
            raise ValueError("Đầu nối chưa hoàn tất yêu cầu. Không tự thử lại công cụ.") from None
        guard()
        return self._redact(result, config["token"])
