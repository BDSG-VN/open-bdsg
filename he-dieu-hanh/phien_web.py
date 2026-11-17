"""Quản lý phiên web của chính người đăng nhập, không phải nhận dạng thiết bị."""

import math
import re
import secrets
import sqlite3
import time

from kho import bam

PUBLIC_ID = re.compile(r"[A-Za-z0-9_-]{24}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
UNKNOWN_HINT = "Chưa xác định"
CLIENT_HINTS = frozenset((UNKNOWN_HINT, "Windows", "macOS", "iPhone/iPad", "Android", "Linux"))


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def ensure_schema(db):
    # Bảng riêng giữ INSERT ba cột của bản trước hợp lệ khi rollback mã.
    db.execute("""CREATE TABLE IF NOT EXISTS phien_web(
        session_hash TEXT PRIMARY KEY REFERENCES phien(hash) ON DELETE CASCADE,
        public_id TEXT NOT NULL UNIQUE,
        created REAL, last_seen REAL,
        label TEXT NOT NULL DEFAULT '', hint TEXT NOT NULL DEFAULT 'Chưa xác định'
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS phien_chu_so_huu ON phien(ma,expires)")


def _metadata(db, digest, created=None, last_seen=None, hint=UNKNOWN_HINT):
    if db.execute("SELECT 1 FROM phien_web WHERE session_hash=?", (digest,)).fetchone():
        return
    for _ in range(3):
        try:
            db.execute("""INSERT INTO phien_web(session_hash,public_id,created,last_seen,hint)
                VALUES(?,?,?,?,?) ON CONFLICT(session_hash) DO NOTHING""",
                (digest, secrets.token_urlsafe(18), created, last_seen, hint))
            return
        except sqlite3.IntegrityError:
            pass
    raise ValueError("Chưa thể tạo mã phiên")


def register_session(db, digest, identity, now):
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest) or not _number(now):
        raise ValueError("Thông tin phiên không hợp lệ")
    row = db.execute("SELECT ma FROM phien WHERE hash=?", (digest,)).fetchone()
    if not row or row[0] != identity:
        raise ValueError("Thông tin phiên không hợp lệ")
    _metadata(db, digest, now, now)


def touch_session(db, digest, now, client_hint=UNKNOWN_HINT):
    """Caller truyền digest và nhãn nền tảng đã lọc; không nhận User-Agent/IP."""
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest) or not _number(now):
        return
    hint = client_hint if isinstance(client_hint, str) and client_hint in CLIENT_HINTS else UNKNOWN_HINT
    active = db.execute("""SELECT 1 FROM phien p WHERE p.hash=? AND p.expires>?
        AND (p.ma='chu-quan' OR EXISTS(SELECT 1 FROM agents a
            WHERE a.ma=p.ma AND a.active=1 AND a.role='operator'))""", (digest, now)).fetchone()
    if not active:
        return
    # Dữ liệu cũ không có ngày tạo: chỉ ghi lần quan sát, không suy ra ngày tạo.
    _metadata(db, digest, last_seen=now, hint=hint)
    db.execute("""UPDATE phien_web SET
        last_seen=CASE WHEN last_seen IS NULL OR ?>=last_seen+60 THEN ? ELSE last_seen END,
        hint=CASE WHEN hint=? THEN ? ELSE hint END WHERE session_hash=?""",
        (now, now, UNKNOWN_HINT, hint, digest))


class PhienWeb:
    def __init__(self, kho, clock=None):
        self.kho = kho
        self.clock = clock or time.time

    def _current(self, db, actor, current_token, now):
        if (not isinstance(actor, dict) or not isinstance(current_token, str)
                or not 1 <= len(current_token) <= 512 or not _number(now)):
            raise PermissionError("Cần phiên web còn hiệu lực")
        digest = bam(current_token)
        identity = self._live_digest(db, actor, digest, now)
        _metadata(db, digest)
        return digest, identity

    @staticmethod
    def _live_digest(db, actor, digest, now):
        row = db.execute("SELECT ma FROM phien WHERE hash=? AND expires>?", (digest, now)).fetchone()
        if not row or row[0] != actor.get("id"):
            raise PermissionError("Cần phiên web còn hiệu lực")
        if row[0] == "chu-quan":
            valid = actor.get("role") == "quan-tri" and db.execute("SELECT 1 FROM chu WHERE ma='chu-quan'").fetchone()
        else:
            valid = actor.get("role") == "operator" and db.execute(
                "SELECT 1 FROM agents WHERE ma=? AND active=1 AND role='operator'", (row[0],)).fetchone()
        if not valid:
            raise PermissionError("Cần phiên web còn hiệu lực")
        return row[0]

    def authorization_reference(self, actor, current_token, db):
        """Tham chiếu consent riêng; không phải chứng thư để đăng nhập web."""
        digest, identity = self._current(db, actor, current_token, self.clock())
        return {'hash': digest, 'identity': identity}

    def require_authorization(self, actor, reference, db):
        if (not isinstance(reference, dict) or set(reference) != {'hash', 'identity'}
                or not isinstance(reference['hash'], str) or not DIGEST.fullmatch(reference['hash'])
                or not isinstance(actor, dict) or reference['identity'] != actor.get('id')):
            raise PermissionError('Phiên duyệt OAuth không hợp lệ')
        self._live_digest(db, actor, reference['hash'], self.clock())

    @staticmethod
    def _identifier(identifier):
        if not isinstance(identifier, str) or not PUBLIC_ID.fullmatch(identifier):
            raise LookupError("Không tìm thấy phiên")
        return identifier

    @staticmethod
    def _target(db, identity, identifier, now):
        row = db.execute("""SELECT p.hash FROM phien p JOIN phien_web w ON w.session_hash=p.hash
            WHERE w.public_id=? AND p.ma=? AND p.expires>?""", (identifier, identity, now)).fetchone()
        if not row:
            raise LookupError("Không tìm thấy phiên")
        return row[0]

    @staticmethod
    def _audit(db, identity, action, target, now):
        db.execute("INSERT INTO su_kien(actor,action,target,created) VALUES(?,?,?,?)",
                   (identity, action, target, now))

    def list(self, actor, current_token):
        now = self.clock()
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            current, identity = self._current(db, actor, current_token, now)
            # Chỉ đăng ký tối đa số dòng sẽ trả; không quét/tạo metadata mọi tài khoản.
            rows = db.execute("""SELECT hash,expires FROM phien WHERE ma=? AND expires>?
                ORDER BY (hash=?) DESC,expires DESC,hash LIMIT 101""", (identity, now, current)).fetchall()
            sessions = []
            for row in rows[:100]:
                _metadata(db, row[0])
                meta = db.execute("SELECT public_id,label,hint,created,last_seen FROM phien_web WHERE session_hash=?", (row[0],)).fetchone()
                sessions.append({"id": meta[0], "label": meta[1], "client_hint": meta[2],
                    "created_at": meta[3], "last_seen_at": meta[4], "expires_at": row[1],
                    "current": row[0] == current})
            return {"sessions": sessions, "has_more": len(rows) > 100}

    def rename(self, actor, current_token, identifier, label):
        now = self.clock()
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            _, identity = self._current(db, actor, current_token, now)
            identifier = self._identifier(identifier)
            if (not isinstance(label, str) or len(label) > 160 or not 1 <= len(label.strip()) <= 80
                    or any(not char.isprintable() for char in label)):
                raise ValueError("Tên phiên cần 1–80 ký tự, không có ký tự điều khiển")
            digest = self._target(db, identity, identifier, now)
            db.execute("UPDATE phien_web SET label=? WHERE session_hash=?", (label.strip(), digest))
            self._audit(db, identity, "doi-ten-phien-web", identifier, now)
        return {"renamed": True}

    def revoke(self, actor, current_token, identifier):
        now = self.clock()
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            current, identity = self._current(db, actor, current_token, now)
            identifier = self._identifier(identifier)
            target = self._target(db, identity, identifier, now)
            if target == current:
                raise ValueError("Dùng Đăng xuất để kết thúc phiên hiện tại")
            db.execute("DELETE FROM phien WHERE hash=? AND ma=?", (target, identity))
            self._audit(db, identity, "thu-hoi-phien-web", identifier, now)
        return {"revoked": True}

    def revoke_others(self, actor, current_token):
        now = self.clock()
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            current, identity = self._current(db, actor, current_token, now)
            count = db.execute("DELETE FROM phien WHERE ma=? AND hash<>? AND expires>?", (identity, current, now)).rowcount
            self._audit(db, identity, "thu-hoi-phien-web-khac", str(count), now)
        return {"revoked_count": count}

    def touch(self, actor, current_token, client_hint=UNKNOWN_HINT):
        now = self.clock()
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            digest, _ = self._current(db, actor, current_token, now)
            touch_session(db, digest, now, client_hint)
