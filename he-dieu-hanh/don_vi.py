"""Danh tính toàn cổng khác tư cách thành viên trong một đơn vị.

Chưa lắp vào gateway production. Context chỉ dùng trong tiến trình; worker và
callback phải xác lập lại từ identity/unit đã lưu, không giữ context như token.
"""
from dataclasses import dataclass, field
import secrets
import time


def assert_unscoped_store(db):
    """Luồng chưa hiểu đơn vị phải dừng, kể cả đơn vị đã bị ngừng hoạt động."""
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='don_vi'").fetchone() and db.execute(
            "SELECT 1 FROM don_vi LIMIT 1").fetchone():
        raise PermissionError("Kho đã có đơn vị; không được dùng luồng thiếu phạm vi")


@dataclass(frozen=True)
class _PhamVi:
    identity: str
    unit_id: str
    role: str
    epoch: int
    _issuer: object = field(repr=False, compare=False)


class DonVi:
    def __init__(self, kho):
        self.kho = kho
        self._issuer = object()
        with kho.ket_noi() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS don_vi(
                    id TEXT PRIMARY KEY,name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS don_vi_members(
                    unit_id TEXT NOT NULL REFERENCES don_vi(id),
                    identity TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','member')),
                    active INTEGER NOT NULL,epoch INTEGER NOT NULL,
                    PRIMARY KEY(unit_id,identity));
                CREATE TABLE IF NOT EXISTS don_vi_migrations(
                    version TEXT PRIMARY KEY,unit_id TEXT NOT NULL REFERENCES don_vi(id),created REAL NOT NULL);
            """)

    @staticmethod
    def _identity(db, actor):
        if not isinstance(actor, dict) or not isinstance(actor.get("id"), str):
            raise PermissionError("Cần danh tính còn hiệu lực")
        if actor["id"] == "chu-quan":
            valid = actor.get("role") == "quan-tri" and db.execute(
                "SELECT 1 FROM chu WHERE ma='chu-quan'").fetchone()
        else:
            valid = actor.get("role") == "operator" and db.execute(
                "SELECT 1 FROM agents WHERE ma=? AND role='operator' AND active=1",
                (actor["id"],)).fetchone()
        if not valid:
            raise PermissionError("Cần danh tính còn hiệu lực")
        return actor["id"]

    @staticmethod
    def _membership(db, identity, unit_id):
        if not isinstance(unit_id, str) or not 1 <= len(unit_id) <= 80:
            raise PermissionError("Không có quyền trong đơn vị")
        row = db.execute("""SELECT m.role,m.epoch FROM don_vi_members m JOIN don_vi u ON u.id=m.unit_id
            WHERE m.unit_id=? AND m.identity=? AND m.active=1 AND u.active=1""",
            (unit_id, identity)).fetchone()
        if not row:
            raise PermissionError("Không có quyền trong đơn vị")
        return row

    @staticmethod
    def _audit(db, actor, action, target):
        db.execute("INSERT INTO su_kien(actor,action,target,created) VALUES(?,?,?,?)",
                   (actor, action, target, time.time()))

    def create(self, actor, args):
        if not isinstance(args, dict):
            raise ValueError("Yêu cầu tạo đơn vị không hợp lệ")
        name, admin = args.get("name"), args.get("admin")
        if not isinstance(name, str) or not 3 <= len(name.strip()) <= 100 or not name.isprintable():
            raise ValueError("Tên đơn vị cần 3–100 ký tự in được")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            identity = self._identity(db, actor)
            if identity != "chu-quan":
                raise PermissionError("Chỉ chủ quản hệ thống tạo đơn vị")
            target = {"id": admin, "role": "quan-tri" if admin == "chu-quan" else "operator"}
            self._identity(db, target)
            unit_id = "dv-" + secrets.token_hex(12)
            db.execute("INSERT INTO don_vi(id,name,created) VALUES(?,?,?)", (unit_id, name.strip(), time.time()))
            db.execute("INSERT INTO don_vi_members VALUES(?,?,?,1,1)", (unit_id, admin, "admin"))
            self._audit(db, identity, "tao-don-vi", unit_id)
        return {"id": unit_id, "name": name.strip()}

    def list(self, actor):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN")
            identity = self._identity(db, actor)
            rows = db.execute("""SELECT u.id,u.name,m.role FROM don_vi u JOIN don_vi_members m ON m.unit_id=u.id
                WHERE m.identity=? AND m.active=1 AND u.active=1 ORDER BY u.created,u.id""", (identity,)).fetchall()
            return {"units": [dict(row) for row in rows]}

    def bind(self, actor, unit_id):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN")
            identity = self._identity(db, actor)
            row = self._membership(db, identity, unit_id)
            scope = _PhamVi(identity, unit_id, row["role"], row["epoch"], self._issuer)
        return {**actor, "unit_scope": scope}

    def require(self, actor, db):
        identity = self._identity(db, actor)
        scope = actor.get("unit_scope")
        if not isinstance(scope, _PhamVi) or scope._issuer is not self._issuer or scope.identity != identity:
            raise PermissionError("Cần phạm vi đơn vị do máy chủ xác lập")
        row = self._membership(db, identity, scope.unit_id)
        if row["epoch"] != scope.epoch or row["role"] != scope.role:
            raise PermissionError("Quyền đơn vị đã thay đổi; cần xác lập lại phạm vi")
        return scope

    def _admin(self, db, actor, unit_id):
        identity = self._identity(db, actor)
        if not isinstance(unit_id, str) or not db.execute(
                "SELECT 1 FROM don_vi WHERE id=? AND active=1", (unit_id,)).fetchone():
            raise PermissionError("Không có quyền quản lý đơn vị")
        # Quyền control plane không phải quyền nội dung; project vẫn cần grant.
        if identity != "chu-quan":
            scope = self.require(actor, db)
            if scope.unit_id != unit_id or scope.role != "admin":
                raise PermissionError("Không có quyền quản lý đơn vị")
        return identity

    def require_system_admin(self, actor, db):
        identity = self._identity(db, actor)
        if identity != "chu-quan":
            raise PermissionError("Chỉ chủ quản hệ thống chuyển dữ liệu")
        return identity

    def members(self, actor, unit_id):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN")
            self._admin(db, actor, unit_id)
            return {"members": [dict(row) for row in db.execute(
                "SELECT identity,role,active FROM don_vi_members WHERE unit_id=? ORDER BY identity", (unit_id,))]}

    def set_member(self, actor, args):
        if not isinstance(args, dict):
            raise ValueError("Yêu cầu thành viên không hợp lệ")
        unit_id, target, role = args.get("unit_id"), args.get("identity"), args.get("role")
        if not isinstance(target, str) or role not in ("admin", "member", "revoke"):
            raise ValueError("Thành viên hoặc quyền đơn vị không hợp lệ")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            identity = self._admin(db, actor, unit_id)
            old = db.execute("SELECT * FROM don_vi_members WHERE unit_id=? AND identity=?", (unit_id, target)).fetchone()
            if role != "revoke":
                self._identity(db, {"id": target, "role": "quan-tri" if target == "chu-quan" else "operator"})
            if old and old["active"] and old["role"] == "admin" and role != "admin":
                count = db.execute("""SELECT count(*) FROM don_vi_members m WHERE m.unit_id=? AND m.active=1
                    AND m.role='admin' AND (m.identity='chu-quan' OR EXISTS(
                        SELECT 1 FROM agents a WHERE a.ma=m.identity AND a.active=1 AND a.role='operator'))""", (unit_id,)).fetchone()[0]
                if count <= 1:
                    raise ValueError("Cần giữ ít nhất một quản trị đơn vị còn hiệu lực")
            if role == "revoke":
                if old and old["active"]:
                    db.execute("UPDATE don_vi_members SET active=0,epoch=epoch+1 WHERE unit_id=? AND identity=?", (unit_id, target))
                else:
                    return {"changed": False}
            elif old and old["active"] and old["role"] == role:
                return {"changed": False}
            else:
                db.execute("""INSERT INTO don_vi_members VALUES(?,?,?,1,1)
                    ON CONFLICT(unit_id,identity) DO UPDATE SET
                    role=excluded.role,active=1,
                    epoch=don_vi_members.epoch+CASE WHEN don_vi_members.active=0 THEN 1 ELSE 0 END""", (unit_id, target, role))
            self._audit(db, identity, "doi-thanh-vien-don-vi", unit_id + ":" + target + ":" + role)
        return {"changed": True}
