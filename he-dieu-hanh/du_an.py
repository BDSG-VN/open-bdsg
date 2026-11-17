"""Dự án riêng theo danh tính; ngữ cảnh được chụp tại thời điểm tạo tác vụ."""

import secrets
import time


from quyen_office import khoa_phien, ngat_phien
from don_vi import assert_unscoped_store


class DuAn:
    def __init__(self, kho, *, units=None):
        self.kho = kho
        self.units = units
        with kho.ket_noi() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS du_an(id TEXT PRIMARY KEY, owner TEXT, name TEXT, instructions TEXT, context TEXT, archived INTEGER, created REAL, updated REAL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS du_an_owner ON du_an(owner,updated)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS du_an_members(project_id TEXT, identity TEXT, role TEXT, PRIMARY KEY(project_id,identity))"
            )
            if units is not None:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS du_an_units(
                        project_id TEXT PRIMARY KEY REFERENCES du_an(id),
                        unit_id TEXT NOT NULL REFERENCES don_vi(id));
                    CREATE INDEX IF NOT EXISTS du_an_unit ON du_an_units(unit_id,project_id);
                    CREATE TABLE IF NOT EXISTS du_an_unit_grants(
                        project_id TEXT NOT NULL REFERENCES du_an_units(project_id),
                        unit_id TEXT NOT NULL REFERENCES don_vi(id),identity TEXT NOT NULL,
                        role TEXT NOT NULL CHECK(role IN ('viewer','editor','manager')),
                        epoch INTEGER NOT NULL,PRIMARY KEY(project_id,unit_id,identity));
                """)

    @staticmethod
    def _auth(actor):
        if (
            not isinstance(actor, dict)
            or actor.get("role") not in ("operator", "quan-tri")
            or not isinstance(actor.get("id"), str)
        ):
            raise PermissionError("Cần danh tính được quyền quản lý dự án")

    @staticmethod
    def _fields(data):
        fields = {}
        for key, minimum, maximum in [
            ("name", 3, 100),
            ("instructions", 0, 4000),
            ("context", 0, 12000),
        ]:
            value = data.get(key, "")
            if (
                not isinstance(value, str)
                or not minimum <= len(value.strip()) <= maximum
            ):
                raise ValueError("Tên hoặc nội dung dự án không hợp lệ")
            fields[key] = value.strip()
        return fields

    def _get(self, actor, identifier, write=False, owner=False):
        return self.authorize(actor, identifier, write=write, owner=owner)

    def authorize(self, actor, identifier, write=False, owner=False, db=None):
        """Cho mô-đun dùng cùng giao dịch khi kiểm quyền và ghi dữ liệu dự án."""
        self._auth(actor)
        if not isinstance(identifier, str) or len(identifier) > 80:
            raise ValueError("Không tìm thấy dự án trong phạm vi quyền")
        if db is None:
            with self.kho.ket_noi() as connection:
                return self.authorize(actor, identifier, write, owner, connection)
        if self.units is not None:
            scope = self.units.require(actor, db)
            row = db.execute("""SELECT p.*,s.unit_id FROM du_an p
                JOIN du_an_units s ON s.project_id=p.id JOIN don_vi u ON u.id=s.unit_id
                WHERE p.id=? AND u.active=1""", (identifier,)).fetchone()
            grant = db.execute("""SELECT role FROM du_an_unit_grants
                WHERE project_id=? AND unit_id=? AND identity=? AND epoch=?""",
                (identifier, scope.unit_id, scope.identity, scope.epoch)).fetchone()
            own = row and row["unit_id"] == scope.unit_id and row["owner"] == scope.identity
            manage = row and grant and grant["role"] == "manager" and row["unit_id"] == scope.unit_id
            if not row or not (own or manage or (not owner and grant and
                    (not write or grant["role"] == "editor"))):
                raise ValueError("Không tìm thấy dự án trong phạm vi quyền")
            return {**dict(row), "archived": bool(row["archived"])}
        assert_unscoped_store(db)
        row = db.execute("SELECT * FROM du_an WHERE id=?", (identifier,)).fetchone()
        member = db.execute(
            "SELECT role FROM du_an_members WHERE project_id=? AND identity=?",
            (identifier, actor["id"]),
        ).fetchone()
        privileged = row and (
            row["owner"] == actor["id"] or actor["role"] == "quan-tri"
        )
        if not row or not (
            privileged
            or (not owner and member and (not write or member["role"] == "editor"))
        ):
            raise ValueError("Không tìm thấy dự án trong phạm vi quyền")
        return {**dict(row), "archived": bool(row["archived"])}

    def list(self, actor):
        self._auth(actor)
        with self.kho.ket_noi() as db:
            if self.units is not None:
                db.execute("BEGIN")
                scope = self.units.require(actor, db)
                rows = db.execute("""SELECT p.*,s.unit_id FROM du_an p
                    JOIN du_an_units s ON s.project_id=p.id JOIN don_vi u ON u.id=s.unit_id
                    WHERE u.active=1 AND ((s.unit_id=? AND p.owner=?) OR EXISTS(
                        SELECT 1 FROM du_an_unit_grants g WHERE g.project_id=p.id
                        AND g.unit_id=? AND g.identity=? AND g.epoch=?
                        AND (g.role IN ('viewer','editor') OR s.unit_id=?)))
                    ORDER BY p.updated DESC,p.id LIMIT 100""",
                    (scope.unit_id, scope.identity, scope.unit_id, scope.identity, scope.epoch, scope.unit_id)).fetchall()
                return {"projects": [{**dict(row), "archived": bool(row["archived"])} for row in rows]}
            assert_unscoped_store(db)
            sql = "SELECT * FROM du_an" + (
                ""
                if actor["role"] == "quan-tri"
                else " WHERE owner=? OR id IN (SELECT project_id FROM du_an_members WHERE identity=?)"
            )
            rows = db.execute(
                sql + " ORDER BY updated DESC LIMIT 100",
                () if actor["role"] == "quan-tri" else (actor["id"], actor["id"]),
            ).fetchall()
        return {
            "projects": [{**dict(r), "archived": bool(r["archived"])} for r in rows]
        }

    def create(self, actor, data):
        self._auth(actor)
        fields = self._fields(data)
        identifier, now = secrets.token_hex(12), time.time()
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            scope = self.units.require(actor, db) if self.units is not None else None
            if scope is None:
                assert_unscoped_store(db)
            count = db.execute(
                "SELECT count(*) FROM du_an p JOIN du_an_units s ON s.project_id=p.id WHERE p.owner=? AND s.unit_id=?",
                (actor["id"], scope.unit_id)).fetchone()[0] if scope else db.execute(
                "SELECT count(*) FROM du_an WHERE owner=?", (actor["id"],)).fetchone()[0]
            if (
                count >= 100
            ):
                raise ValueError("Đã đạt giới hạn 100 dự án cho danh tính này")
            db.execute(
                "INSERT INTO du_an VALUES (?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    actor["id"],
                    fields["name"],
                    fields["instructions"],
                    fields["context"],
                    0,
                    now,
                    now,
                ),
            )
            if scope:
                db.execute("INSERT INTO du_an_units VALUES(?,?)", (identifier, scope.unit_id))
        self.kho.su_kien(actor["id"], "tao-du-an", identifier)
        return self._get(actor, identifier)

    def update(self, actor, data):
        fields = self._fields(data)
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            project = self.authorize(actor, data.get("id"), write=True, db=db)
            if project["archived"]:
                raise ValueError("Khôi phục dự án trước khi cập nhật")
            db.execute(
                "UPDATE du_an SET name=?,instructions=?,context=?,updated=? WHERE id=?",
                (
                    fields["name"],
                    fields["instructions"],
                    fields["context"],
                    time.time(),
                    project["id"],
                ),
            )
        self.kho.su_kien(actor["id"], "cap-nhat-du-an", project["id"])
        return self._get(actor, project["id"])

    def archive(self, actor, identifier, archived=True):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            project = self.authorize(actor, identifier, owner=True, db=db)
            db.execute(
                "UPDATE du_an SET archived=?,updated=? WHERE id=?",
                (int(archived), time.time(), project["id"]),
            )
            keys = khoa_phien(db, project_id=project["id"]) if archived else []
        ngat_phien(keys)
        self.kho.su_kien(
            actor["id"],
            "luu-tru-du-an" if archived else "khoi-phuc-du-an",
            project["id"],
        )
        return self._get(actor, project["id"])

    def context_for(self, actor, identifier):
        project = self._get(actor, identifier)
        if project["archived"]:
            raise ValueError(
                "Dự án đã lưu trữ; cần khôi phục trước khi tạo công việc mới"
            )
        return {
            k: project[k] for k in ("id", "name", "instructions", "context", "updated")
        } | ({"source_unit_id": project["unit_id"]} if self.units is not None else {})

    def members(self, actor, identifier):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN")
            self.authorize(actor, identifier, owner=True, db=db)
            if self.units is not None:
                return {"members": [dict(row) for row in db.execute("""SELECT g.unit_id,g.identity,g.role,
                    CASE WHEN m.active=1 AND m.epoch=g.epoch THEN 1 ELSE 0 END AS active
                    FROM du_an_unit_grants g LEFT JOIN don_vi_members m
                    ON m.unit_id=g.unit_id AND m.identity=g.identity WHERE g.project_id=?
                    ORDER BY g.unit_id,g.identity""", (identifier,))]}
            return {
                "members": [
                    dict(r)
                    for r in db.execute(
                        "SELECT identity,role FROM du_an_members WHERE project_id=?",
                        (identifier,),
                    )
                ]
            }

    def share(self, actor, data):
        if self.units is not None:
            return self._share_scoped(actor, data)
        project = self._get(actor, data.get("id"), owner=True)
        identity, role = data.get("identity"), data.get("role")
        if role not in ("viewer", "editor", "revoke") or not isinstance(identity, str):
            raise ValueError("Thành viên hoặc quyền không hợp lệ")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            self.authorize(actor, project["id"], owner=True, db=db)
            if not db.execute(
                "SELECT 1 FROM agents WHERE ma=? AND active=1 AND role='operator'",
                (identity,),
            ).fetchone():
                raise ValueError("Cần danh tính operator đang hoạt động")
            if role == "revoke":
                db.execute(
                    "DELETE FROM du_an_members WHERE project_id=? AND identity=?",
                    (project["id"], identity),
                )
            else:
                db.execute(
                    "INSERT INTO du_an_members VALUES (?,?,?) ON CONFLICT(project_id,identity) DO UPDATE SET role=excluded.role",
                    (project["id"], identity, role),
                )
            keys = khoa_phien(db, identity=identity, project_id=project["id"]) if role != "editor" else []
        ngat_phien(keys)
        self.kho.su_kien(actor["id"], "doi-quyen-du-an", project["id"])
        return self.members(actor, project["id"])

    def _share_scoped(self, actor, data):
        identity, role = data.get("identity"), data.get("role")
        if not isinstance(identity, str) or role not in ("viewer", "editor", "revoke"):
            raise ValueError("Thành viên hoặc quyền không hợp lệ")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            project = self.authorize(actor, data.get("id"), owner=True, db=db)
            unit_id = data.get("unit_id", project["unit_id"])
            if not isinstance(unit_id, str):
                raise ValueError("Cần đơn vị nhận chia sẻ")
            if role == "revoke":
                db.execute("DELETE FROM du_an_unit_grants WHERE project_id=? AND unit_id=? AND identity=?",
                           (project["id"], unit_id, identity))
            else:
                target_actor = {"id": identity, "role": "quan-tri" if identity == "chu-quan" else "operator"}
                target = self.units.bind(target_actor, unit_id)
                scope = self.units.require(target, db)
                db.execute("""INSERT INTO du_an_unit_grants VALUES(?,?,?,?,?)
                    ON CONFLICT(project_id,unit_id,identity) DO UPDATE SET role=excluded.role,epoch=excluded.epoch""",
                    (project["id"], unit_id, identity, role, scope.epoch))
            db.execute("INSERT INTO su_kien(actor,action,target,created) VALUES(?,?,?,?)",
                       (actor["id"], "doi-quyen-du-an-don-vi", project["id"] + ":" + unit_id + ":" + identity + ":" + role, time.time()))
        # Participant grant của editor/callback chưa mang unit; không dùng thao
        # tác đóng theo identity để vô tình ngắt một quyền ở đơn vị khác.
        return self.members(actor, project["id"])
