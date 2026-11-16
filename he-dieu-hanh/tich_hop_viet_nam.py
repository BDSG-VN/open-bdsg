"""Một interface cho cấu hình, cấp quyền đọc và đối soát lượt gọi đa nền tảng.

Không tự gửi tin, đăng bài, phát hành hóa đơn hoặc chuyển tiền. Mọi lời gọi
được đăng ký qua nhân, gắn chủ quản, cấu hình và revision chứng thư cụ thể.
"""

import hashlib
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

from vn_adapters import decode, prepare
from vn_hop_dong import catalogue, provider, validate_secrets, validate_settings
from vn_transport import LoiTichHop, VanChuyenHTTPS


class TichHopVietNam:
    def __init__(self, kho, transport=None, key_file=None, clock=None):
        self.kho = kho
        self.transport = transport or VanChuyenHTTPS()
        self.clock = clock or time.time
        self.aes = None
        self._capacity = threading.BoundedSemaphore(4)
        self._busy = set()
        self._lock = threading.Lock()
        key_file = key_file or os.environ.get("BDSG_INTEGRATION_VAULT_KEY_FILE")
        if key_file:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM

                key = Path(key_file).read_bytes()
                if len(key) != 32:
                    raise ValueError
                self.aes = AESGCM(key)
            except (OSError, ValueError, ImportError):
                pass
        with self.kho.ket_noi() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS vn_connections(
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, provider TEXT NOT NULL,
                    label TEXT NOT NULL, settings TEXT NOT NULL, cipher BLOB,
                    operations TEXT NOT NULL, revision INTEGER NOT NULL, enabled INTEGER NOT NULL,
                    expires REAL, state TEXT NOT NULL, checked REAL,
                    failures INTEGER NOT NULL DEFAULT 0, cooldown REAL NOT NULL DEFAULT 0,
                    created REAL NOT NULL, updated REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS vn_connection_owner ON vn_connections(owner,enabled);
                CREATE TABLE IF NOT EXISTS vn_runs(
                    id TEXT PRIMARY KEY, connection_id TEXT NOT NULL, owner TEXT NOT NULL,
                    operation TEXT NOT NULL, revision INTEGER NOT NULL, request_key TEXT NOT NULL,
                    args_hash TEXT NOT NULL, state TEXT NOT NULL, started REAL NOT NULL,
                    finished REAL, records INTEGER NOT NULL DEFAULT 0, error_code TEXT, result TEXT,
                    UNIQUE(owner,request_key));
                CREATE INDEX IF NOT EXISTS vn_run_connection ON vn_runs(connection_id,started);
            """)
            db.execute(
                "UPDATE vn_runs SET state='interrupted',error_code='interrupted',finished=? WHERE state='running'",
                (self.clock(),),
            )

    @staticmethod
    def _auth(actor):
        if not actor or actor.get("role") != "quan-tri":
            raise PermissionError("Chỉ chủ quản quản lý tích hợp Việt Nam")

    @staticmethod
    def _arguments(values, allowed):
        if not isinstance(values, dict) or set(values) - set(allowed):
            raise LoiTichHop("invalid_arguments")

    @staticmethod
    def _aad(row):
        return (
            "vn:"
            + row["id"]
            + ":"
            + row["owner"]
            + ":"
            + row["provider"]
            + ":"
            + str(row["revision"])
        ).encode()

    def _encrypt(self, row, value):
        if not self.aes:
            raise LoiTichHop("configuration_required")
        nonce = secrets.token_bytes(12)
        return nonce + self.aes.encrypt(
            nonce, json.dumps(value).encode(), self._aad(row)
        )

    def _decrypt(self, row):
        if not self.aes:
            raise LoiTichHop("configuration_required")
        from cryptography.exceptions import InvalidTag

        try:
            raw = row["cipher"]
            return json.loads(self.aes.decrypt(raw[:12], raw[12:], self._aad(row)))
        except (InvalidTag, ValueError, TypeError, KeyError, UnicodeError):
            raise LoiTichHop("authorization_required") from None

    @staticmethod
    def _public(row):
        return {
            "id": row["id"],
            "provider": row["provider"],
            "label": row["label"],
            "settings": json.loads(row["settings"]),
            "operations": json.loads(row["operations"]),
            "revision": row["revision"],
            "enabled": bool(row["enabled"]),
            "state": row["state"],
            "has_credentials": row["cipher"] is not None,
            "expires_at": row["expires"],
            "checked_at": row["checked"],
            "cooldown_until": row["cooldown"],
            "external_writes_enabled": False,
        }

    @staticmethod
    def _row(db, actor, identifier):
        if not isinstance(identifier, str):
            raise LoiTichHop("invalid_arguments")
        row = db.execute(
            "SELECT * FROM vn_connections WHERE id=? AND owner=?",
            (identifier, actor["id"]),
        ).fetchone()
        if not row:
            raise PermissionError("Không có quyền với kết nối")
        return dict(row)

    def list(self, actor, arguments=None):
        self._auth(actor)
        self._arguments(arguments or {}, ())
        with self.kho.ket_noi() as db:
            rows = db.execute(
                "SELECT * FROM vn_connections WHERE owner=? ORDER BY created DESC LIMIT 100",
                (actor["id"],),
            ).fetchall()
        return {
            **catalogue(),
            "connections": [self._public(row) for row in rows],
            "vault_configured": self.aes is not None,
        }

    def save(self, actor, arguments):
        self._auth(actor)
        self._arguments(
            arguments,
            (
                "id",
                "provider",
                "label",
                "settings",
                "credentials",
                "operations",
                "expires_at",
                "expected_revision",
            ),
        )
        identifier = arguments.get("id") or "vn-" + secrets.token_hex(12)
        if not isinstance(identifier, str) or not re.fullmatch(
            r"vn-[a-f0-9]{24}", identifier
        ):
            raise LoiTichHop("invalid_arguments")
        provider_id = arguments.get("provider")
        contract = provider(provider_id)
        settings = validate_settings(provider_id, arguments.get("settings"))
        label = arguments.get("label")
        operations = arguments.get("operations")
        if (
            not isinstance(label, str)
            or not 1 <= len(label.strip()) <= 120
            or any(char in label for char in "\0\r\n")
            or not isinstance(operations, list)
            or not operations
            or any(
                not isinstance(op, str) or op not in contract["operations"]
                for op in operations
            )
            or len(set(operations)) != len(operations)
        ):
            raise LoiTichHop("invalid_arguments")
        expires = arguments.get("expires_at")
        now = self.clock()
        if expires is not None and (
            isinstance(expires, bool)
            or not isinstance(expires, (int, float))
            or not now < expires <= now + 366 * 86400
        ):
            raise LoiTichHop("invalid_arguments")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            before = db.execute(
                "SELECT * FROM vn_connections WHERE id=?", (identifier,)
            ).fetchone()
            if before:
                before = dict(before)
                if before["owner"] != actor["id"]:
                    raise PermissionError("Không có quyền sửa kết nối")
                expected = arguments.get("expected_revision")
                if isinstance(expected, bool) or expected != before["revision"]:
                    raise LoiTichHop("connection_changed")
                revision = before["revision"] + 1
                if "expires_at" not in arguments:
                    expires = before["expires"]
            else:
                if (
                    arguments.get("id")
                    or db.execute(
                        "SELECT count(*) FROM vn_connections WHERE owner=?",
                        (actor["id"],),
                    ).fetchone()[0]
                    >= 64
                ):
                    raise LoiTichHop("invalid_arguments")
                revision = 1
            credentials = arguments.get("credentials")
            if (
                credentials is None
                and before
                and before["enabled"]
                and before["provider"] == provider_id
                and json.loads(before["settings"]) == settings
            ):
                credentials = self._decrypt(before)
            credentials = validate_secrets(
                provider_id, credentials if credentials is not None else {}
            )
            row = {
                "id": identifier,
                "owner": actor["id"],
                "provider": provider_id,
                "revision": revision,
            }
            cipher = self._encrypt(row, credentials)
            db.execute(
                """INSERT INTO vn_connections(id,owner,provider,label,settings,cipher,operations,revision,enabled,expires,state,checked,failures,cooldown,created,updated)
                          VALUES (?,?,?,?,?,?,?,?,1,?,'configured',NULL,0,0,?,?)
                          ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,label=excluded.label,
                          settings=excluded.settings,cipher=excluded.cipher,operations=excluded.operations,
                          revision=excluded.revision,enabled=1,expires=excluded.expires,state='configured',
                          checked=NULL,failures=0,cooldown=0,updated=excluded.updated""",
                (
                    identifier,
                    actor["id"],
                    provider_id,
                    label.strip(),
                    json.dumps(settings),
                    cipher,
                    json.dumps(operations),
                    revision,
                    expires,
                    now,
                    now,
                ),
            )
            saved = self._row(db, actor, identifier)
        return self._public(saved)

    def disconnect(self, actor, arguments):
        self._auth(actor)
        self._arguments(arguments, ("id", "expected_revision"))
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, actor, arguments.get("id"))
            if arguments.get("expected_revision") != row["revision"] or isinstance(
                arguments.get("expected_revision"), bool
            ):
                raise LoiTichHop("connection_changed")
            db.execute(
                "UPDATE vn_connections SET enabled=0,cipher=NULL,revision=revision+1,state='revoked',updated=? WHERE id=?",
                (self.clock(), row["id"]),
            )
            return self._public(self._row(db, actor, row["id"]))

    def runs(self, actor, arguments):
        self._auth(actor)
        self._arguments(arguments, ("id",))
        with self.kho.ket_noi() as db:
            self._row(db, actor, arguments.get("id"))
            # Lịch sử chỉ metadata; payload đọc riêng trong kết quả của lượt gọi.
            rows = db.execute(
                "SELECT id,operation,revision,state,started,finished,records,error_code FROM vn_runs WHERE owner=? AND connection_id=? ORDER BY started DESC LIMIT 50",
                (actor["id"], arguments["id"]),
            ).fetchall()
        return {"runs": [dict(row) for row in rows]}

    def read(self, actor, arguments):
        self._auth(actor)
        self._arguments(arguments, ("id", "operation", "arguments", "request_key"))
        request_key = arguments.get("request_key")
        if not isinstance(request_key, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{8,100}", request_key
        ):
            raise LoiTichHop("invalid_arguments")
        identifier = arguments.get("id")
        if not isinstance(identifier, str):
            raise LoiTichHop("invalid_arguments")
        if not self._capacity.acquire(blocking=False):
            raise LoiTichHop("busy")
        acquired = False
        try:
            with self._lock:
                if identifier in self._busy:
                    raise LoiTichHop("busy")
                self._busy.add(identifier)
                acquired = True
            return self._read(actor, arguments)
        finally:
            if acquired:
                with self._lock:
                    self._busy.discard(identifier)
            self._capacity.release()

    def _read(self, actor, arguments):
        now = self.clock()
        with self.kho.ket_noi() as db:
            row = self._row(db, actor, arguments["id"])
        if not row["enabled"] or row["cipher"] is None:
            raise LoiTichHop("connection_changed")
        if row["expires"] is not None and row["expires"] <= now:
            raise LoiTichHop("authorization_required")
        if row["state"] in (
            "authorization_required",
            "permission_denied",
            "configuration_required",
        ):
            raise LoiTichHop(row["state"])
        if row["cooldown"] > now:
            raise LoiTichHop("rate_limited", int(row["cooldown"] - now) + 1)
        operation = arguments.get("operation")
        if not isinstance(operation, str) or operation not in json.loads(
            row["operations"]
        ):
            raise LoiTichHop("permission_denied")
        credentials = self._decrypt(row)
        args = arguments.get("arguments", {})
        plan = prepare(
            row["provider"], json.loads(row["settings"]), credentials, operation, args
        )
        args_hash = hashlib.sha256(
            json.dumps(
                {
                    "connection": row["id"],
                    "revision": row["revision"],
                    "operation": operation,
                    "args": args,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        run_id = "read-" + secrets.token_hex(16)
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self._row(db, actor, row["id"])
            if not current["enabled"] or current["revision"] != row["revision"]:
                raise LoiTichHop("connection_changed")
            existing = db.execute(
                "SELECT * FROM vn_runs WHERE owner=? AND request_key=?",
                (actor["id"], arguments["request_key"]),
            ).fetchone()
            if existing:
                if existing["args_hash"] != args_hash:
                    raise LoiTichHop("invalid_arguments")
                if existing["state"] == "succeeded":
                    return {**json.loads(existing["result"]), "replayed": True}
                raise LoiTichHop(
                    "busy" if existing["state"] == "running" else "interrupted"
                )
            if (
                db.execute(
                    "SELECT count(*) FROM vn_runs WHERE connection_id=? AND started>?",
                    (row["id"], now - 60),
                ).fetchone()[0]
                >= 30
            ):
                raise LoiTichHop("rate_limited", 60)
            if (
                db.execute(
                    "SELECT count(*) FROM vn_runs WHERE owner=?", (actor["id"],)
                ).fetchone()[0]
                >= 20000
            ):
                raise LoiTichHop("rate_limited", 300)
            db.execute(
                "INSERT INTO vn_runs(id,connection_id,owner,operation,revision,request_key,args_hash,state,started) VALUES (?,?,?,?,?,?,?,'running',?)",
                (
                    run_id,
                    row["id"],
                    actor["id"],
                    operation,
                    row["revision"],
                    arguments["request_key"],
                    args_hash,
                    now,
                ),
            )
        try:
            response = self.transport.request(
                plan.host,
                plan.method,
                plan.path,
                plan.headers,
                plan.body,
                timeout=35 if plan.provider_id == "momo" else 12,
            )
            result = decode(plan, response, credentials)
            result.update(
                {
                    "run_id": run_id,
                    "provider": row["provider"],
                    "connection_id": row["id"],
                    "operation": operation,
                    "observed_at": self.clock(),
                    "replayed": False,
                    "environment": json.loads(row["settings"]).get(
                        "environment", "provider_production"
                    ),
                }
            )
            encoded = json.dumps(result, ensure_ascii=False)
            if len(encoded.encode()) > 512 * 1024:
                raise LoiTichHop("response_too_large")
            with self.kho.ket_noi() as db:
                db.execute("BEGIN IMMEDIATE")
                current = self._row(db, actor, row["id"])
                if not current["enabled"] or current["revision"] != row["revision"]:
                    raise LoiTichHop("connection_changed")
                db.execute(
                    "UPDATE vn_runs SET state='succeeded',finished=?,records=?,result=? WHERE id=?",
                    (self.clock(), len(result["items"]), encoded, run_id),
                )
                db.execute(
                    "UPDATE vn_connections SET state='last_read_succeeded',checked=?,failures=0,cooldown=0 WHERE id=?",
                    (self.clock(), row["id"]),
                )
            return result
        except Exception as error:  # noqa: BLE001 - luôn kết thúc ledger, không lộ lỗi từ adapter/chứng thư.
            failure = (
                error
                if isinstance(error, LoiTichHop)
                else LoiTichHop("provider_unavailable", 30)
            )
            with self.kho.ket_noi() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "UPDATE vn_runs SET state='failed',error_code=?,finished=? WHERE id=?",
                    (failure.code, self.clock(), run_id),
                )
                db.execute(
                    "UPDATE vn_connections SET state=?,failures=failures+1,cooldown=? WHERE id=? AND revision=? AND enabled=1",
                    (
                        failure.code,
                        self.clock()
                        + (
                            max(60, failure.retry_after)
                            if row["failures"] >= 2
                            else failure.retry_after
                        ),
                        row["id"],
                        row["revision"],
                    ),
                )
            raise failure from None
        finally:
            credentials.clear()
