"""Đồng bộ đọc theo từng trang, checkpoint bền và không tự chạy lại sau sự cố.

Mỗi bước là một lời gọi có danh tính qua nhân. Chưa có cron hoặc tự ghi dữ
liệu vào CRM/kế toán: snapshot trỏ tới ledger đã lọc của adapter. Cùng giao
dịch SQLite kiểm revision và chốt trang để thu hồi không lọt qua checkpoint.
"""

import hashlib
import json
import re
import secrets

from vn_transport import LoiTichHop


class DongBoVietNam:
    MAX_PAGES = 100
    MAX_RECORDS = 10000
    MAX_BYTES = 5 * 1024 * 1024

    def __init__(self, integrations):
        self.integrations = integrations
        self.kho = integrations.kho
        self.clock = integrations.clock
        with self.kho.ket_noi() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS vn_sync_jobs(
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL,
                    connection_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    operation TEXT NOT NULL, label TEXT NOT NULL,
                    request_key TEXT NOT NULL, config_hash TEXT NOT NULL,
                    state TEXT NOT NULL, arguments TEXT NOT NULL,
                    pages INTEGER NOT NULL DEFAULT 0, records INTEGER NOT NULL DEFAULT 0,
                    bytes INTEGER NOT NULL DEFAULT 0, attempt INTEGER NOT NULL DEFAULT 0,
                    max_pages INTEGER NOT NULL, error_code TEXT, retry_at REAL,
                    created REAL NOT NULL, updated REAL NOT NULL,
                    UNIQUE(owner,request_key));
                CREATE INDEX IF NOT EXISTS vn_sync_owner ON vn_sync_jobs(owner,updated);
                CREATE TABLE IF NOT EXISTS vn_sync_pages(
                    job_id TEXT NOT NULL, page INTEGER NOT NULL, run_id TEXT NOT NULL,
                    cursor_hash TEXT NOT NULL, records INTEGER NOT NULL,
                    PRIMARY KEY(job_id,page), UNIQUE(job_id,cursor_hash));
            """)
            db.execute(
                "UPDATE vn_sync_jobs SET state='paused',error_code='interrupted',updated=? WHERE state='running'",
                (self.clock(),),
            )

    @staticmethod
    def _check(actor, arguments, allowed):
        if not actor or actor.get("role") != "quan-tri":
            raise PermissionError("Chỉ chủ quản quản lý đồng bộ")
        if not isinstance(arguments, dict) or set(arguments) - set(allowed):
            raise LoiTichHop("invalid_arguments")

    @staticmethod
    def _encode(value):
        try:
            encoded = json.dumps(
                value, sort_keys=True, ensure_ascii=False, allow_nan=False
            )
        except (TypeError, ValueError):
            raise LoiTichHop("invalid_arguments") from None
        if len(encoded.encode()) > 16384:
            raise LoiTichHop("invalid_arguments")
        return encoded

    @staticmethod
    def _hash(encoded):
        return hashlib.sha256(encoded.encode()).hexdigest()

    @staticmethod
    def _row(db, actor, identifier):
        if not isinstance(identifier, str):
            raise LoiTichHop("invalid_arguments")
        row = db.execute(
            "SELECT * FROM vn_sync_jobs WHERE id=? AND owner=?",
            (identifier, actor["id"]),
        ).fetchone()
        if not row:
            raise PermissionError("Không có quyền với phiên đồng bộ")
        return dict(row)

    def _connection(self, db, actor, row):
        current = db.execute(
            "SELECT revision,enabled,operations,expires,state FROM vn_connections WHERE id=? AND owner=?",
            (row["connection_id"], actor["id"]),
        ).fetchone()
        if (
            not current
            or not current["enabled"]
            or current["revision"] != row["revision"]
        ):
            raise LoiTichHop("connection_changed")
        if current["expires"] is not None and current["expires"] <= self.clock():
            raise LoiTichHop("authorization_required")
        if current["state"] in ("authorization_required", "permission_denied", "configuration_required"):
            raise LoiTichHop(current["state"])
        if row["operation"] not in json.loads(current["operations"]):
            raise LoiTichHop("permission_denied")

    @staticmethod
    def _public(row):
        # Không phát cursor, token, arguments hoặc dữ liệu nghiệp vụ trong danh sách.
        return {
            key: row[key]
            for key in (
                "id",
                "connection_id",
                "revision",
                "operation",
                "label",
                "state",
                "pages",
                "records",
                "bytes",
                "max_pages",
                "error_code",
                "retry_at",
                "created",
                "updated",
            )
        }

    def create(self, actor, arguments):
        self._check(
            actor,
            arguments,
            (
                "connection_id",
                "operation",
                "label",
                "arguments",
                "max_pages",
                "request_key",
            ),
        )
        label = arguments.get("label")
        key = arguments.get("request_key")
        maximum = arguments.get("max_pages", 20)
        params = arguments.get("arguments", {})
        if (
            not isinstance(label, str)
            or not 1 <= len(label.strip()) <= 120
            or any(c in label for c in "\0\r\n")
            or not isinstance(key, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", key)
            or type(maximum) is not int
            or not 1 <= maximum <= self.MAX_PAGES
            or not isinstance(params, dict)
        ):
            raise LoiTichHop("invalid_arguments")
        encoded = self._encode(params)
        revision = self.integrations.validate_read(
            actor, arguments.get("connection_id"), arguments.get("operation"), params
        )
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            connection = db.execute(
                "SELECT * FROM vn_connections WHERE id=? AND owner=?",
                (arguments.get("connection_id"), actor["id"]),
            ).fetchone()
            if not connection or not connection["enabled"]:
                raise PermissionError("Kết nối không được cấp")
            if connection["revision"] != revision:
                raise LoiTichHop("connection_changed")
            operation = arguments.get("operation")
            if not isinstance(operation, str) or operation not in json.loads(
                connection["operations"]
            ):
                raise LoiTichHop("permission_denied")
            config_hash = self._hash(
                self._encode(
                    {
                        "connection_id": connection["id"],
                        "revision": connection["revision"],
                        "operation": operation,
                        "arguments": params,
                        "max_pages": maximum,
                        "label": label.strip(),
                    }
                )
            )
            existing = db.execute(
                "SELECT * FROM vn_sync_jobs WHERE owner=? AND request_key=?",
                (actor["id"], key),
            ).fetchone()
            if existing:
                if existing["config_hash"] != config_hash:
                    raise LoiTichHop("invalid_arguments")
                return self._public(existing)
            count = db.execute(
                "SELECT count(*) FROM vn_sync_jobs WHERE owner=?", (actor["id"],)
            ).fetchone()[0]
            if count >= 200:
                raise LoiTichHop("rate_limited")
            identifier, now = "sync-" + secrets.token_hex(16), self.clock()
            db.execute(
                "INSERT INTO vn_sync_jobs(id,owner,connection_id,revision,operation,label,request_key,config_hash,state,arguments,max_pages,created,updated) VALUES (?,?,?,?,?,?,?,?,'ready',?,?,?,?)",
                (
                    identifier,
                    actor["id"],
                    connection["id"],
                    connection["revision"],
                    operation,
                    label.strip(),
                    key,
                    config_hash,
                    encoded,
                    maximum,
                    now,
                    now,
                ),
            )
            return self._public(self._row(db, actor, identifier))

    def list(self, actor, arguments=None):
        self._check(actor, arguments or {}, ())
        with self.kho.ket_noi() as db:
            rows = db.execute(
                "SELECT * FROM vn_sync_jobs WHERE owner=? ORDER BY updated DESC LIMIT 200",
                (actor["id"],),
            ).fetchall()
        return {
            "jobs": [self._public(row) for row in rows],
            "automatic_execution": False,
        }

    def control(self, actor, arguments):
        self._check(actor, arguments, ("id", "action"))
        action = arguments.get("action")
        if action not in ("pause", "resume", "cancel"):
            raise LoiTichHop("invalid_arguments")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, actor, arguments.get("id"))
            if row["state"] in ("completed", "cancelled"):
                raise LoiTichHop("invalid_arguments")
            if action == "resume":
                self._connection(db, actor, row)
                if row["state"] != "paused":
                    raise LoiTichHop("busy")
                if row["pages"] >= row["max_pages"]:
                    raise LoiTichHop("invalid_arguments")
                if row["retry_at"] and row["retry_at"] > self.clock():
                    raise LoiTichHop(
                        "rate_limited", int(row["retry_at"] - self.clock()) + 1
                    )
                state = "ready"
            else:
                if action == "pause" and row["state"] == "paused":
                    return self._public(row)
                state = "paused" if action == "pause" else "cancelled"
            # attempt còn là generation: vô hiệu hóa kết quả đang bay khi pause/resume.
            db.execute(
                "UPDATE vn_sync_jobs SET state=?,attempt=attempt+1,error_code=NULL,retry_at=NULL,updated=? WHERE id=?",
                (state, self.clock(), row["id"]),
            )
            return self._public(self._row(db, actor, row["id"]))

    def step(self, actor, arguments):
        self._check(actor, arguments, ("id",))
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, actor, arguments.get("id"))
            if row["state"] == "completed":
                return self._public(row)
            if row["state"] != "ready":
                raise LoiTichHop("busy")
            self._connection(db, actor, row)
            db.execute(
                "UPDATE vn_sync_jobs SET state='running',updated=? WHERE id=?",
                (self.clock(), row["id"]),
            )
        try:
            result = self.integrations.read(
                actor,
                {
                    "id": row["connection_id"],
                    "expected_revision": row["revision"],
                    "operation": row["operation"],
                    "arguments": json.loads(row["arguments"]),
                    "request_key": row["id"]
                    + "-"
                    + str(row["pages"])
                    + "-"
                    + str(row["attempt"]),
                },
            )
            next_args = result["next_arguments"]
            next_encoded = self._encode(next_args) if next_args is not None else "null"
            size = len(json.dumps(result, ensure_ascii=False).encode())
            records = len(result["items"])
            with self.kho.ket_noi() as db:
                db.execute("BEGIN IMMEDIATE")
                current = self._row(db, actor, row["id"])
                self._connection(db, actor, row)
                if (
                    current["state"] != "running"
                    or current["attempt"] != row["attempt"]
                ):
                    raise LoiTichHop("connection_changed")
                cursor_hash = self._hash(row["arguments"])
                seen = db.execute(
                    "SELECT 1 FROM vn_sync_pages WHERE job_id=? AND cursor_hash=?",
                    (row["id"], cursor_hash),
                ).fetchone()
                if seen or (
                    next_args is not None
                    and (
                        next_encoded == row["arguments"]
                        or db.execute(
                            "SELECT 1 FROM vn_sync_pages WHERE job_id=? AND cursor_hash=?",
                            (row["id"], self._hash(next_encoded)),
                        ).fetchone()
                    )
                ):
                    raise LoiTichHop("invalid_response")
                if (
                    row["records"] + records > self.MAX_RECORDS
                    or row["bytes"] + size > self.MAX_BYTES
                ):
                    raise LoiTichHop("response_too_large")
                state = "completed" if next_args is None else "ready"
                error = None
                if next_args is not None and row["pages"] + 1 >= row["max_pages"]:
                    state, error = "paused", "page_limit"
                db.execute(
                    "INSERT INTO vn_sync_pages(job_id,page,run_id,cursor_hash,records) VALUES (?,?,?,?,?)",
                    (
                        row["id"],
                        row["pages"] + 1,
                        result["run_id"],
                        cursor_hash,
                        records,
                    ),
                )
                db.execute(
                    "UPDATE vn_sync_jobs SET state=?,arguments=?,pages=pages+1,records=records+?,bytes=bytes+?,error_code=?,updated=? WHERE id=?",
                    (
                        state,
                        next_encoded,
                        records,
                        size,
                        error,
                        self.clock(),
                        row["id"],
                    ),
                )
                return self._public(self._row(db, actor, row["id"]))
        except Exception as error:  # noqa: BLE001 - không giữ job running hoặc lộ payload ngoài hợp đồng.
            failure = (
                error
                if isinstance(error, LoiTichHop)
                else LoiTichHop("provider_unavailable", 30)
            )
            with self.kho.ket_noi() as db:
                db.execute(
                    "UPDATE vn_sync_jobs SET state='paused',error_code=?,retry_at=?,updated=? WHERE id=? AND state='running' AND attempt=?",
                    (
                        failure.code,
                        self.clock() + failure.retry_after,
                        self.clock(),
                        row["id"],
                        row["attempt"],
                    ),
                )
            raise failure from None

    def page(self, actor, arguments):
        self._check(actor, arguments, ("id", "page"))
        number = arguments.get("page")
        if type(number) is not int or not 1 <= number <= self.MAX_PAGES:
            raise LoiTichHop("invalid_arguments")
        with self.kho.ket_noi() as db:
            row = self._row(db, actor, arguments.get("id"))
            self._connection(db, actor, row)
            if row["state"] == "cancelled":
                raise LoiTichHop("permission_denied")
            record = db.execute(
                "SELECT r.result FROM vn_sync_pages p JOIN vn_runs r ON r.id=p.run_id WHERE p.job_id=? AND p.page=? AND r.owner=? AND r.revision=? AND r.state='succeeded'",
                (row["id"], number, actor["id"], row["revision"]),
            ).fetchone()
            if not record:
                raise LoiTichHop("invalid_arguments")
            payload = json.loads(record["result"])
            return {
                "job_id": row["id"],
                "page": number,
                "items": payload["items"],
                "observed_at": payload["observed_at"],
                "external_write_performed": False,
            }
