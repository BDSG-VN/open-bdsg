"""Dự án riêng theo danh tính; ngữ cảnh được chụp tại thời điểm tạo tác vụ."""
import secrets
import time


class DuAn:
    def __init__(self, kho):
        self.kho = kho
        with kho.ket_noi() as db:
            db.execute("CREATE TABLE IF NOT EXISTS du_an(id TEXT PRIMARY KEY, owner TEXT, name TEXT, instructions TEXT, context TEXT, archived INTEGER, created REAL, updated REAL)")
            db.execute("CREATE INDEX IF NOT EXISTS du_an_owner ON du_an(owner,updated)")

    @staticmethod
    def _auth(actor):
        if not isinstance(actor, dict) or actor.get("role") not in ("operator", "quan-tri") or not isinstance(actor.get("id"), str):
            raise PermissionError("Cần danh tính được quyền quản lý dự án")

    @staticmethod
    def _fields(data):
        fields = {}
        for key, minimum, maximum in [("name", 3, 100), ("instructions", 0, 4000), ("context", 0, 12000)]:
            value = data.get(key, "")
            if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
                raise ValueError("Tên hoặc nội dung dự án không hợp lệ")
            fields[key] = value.strip()
        return fields

    def _get(self, actor, identifier):
        self._auth(actor)
        if not isinstance(identifier, str) or len(identifier) > 80:
            raise ValueError("Không tìm thấy dự án trong phạm vi quyền")
        with self.kho.ket_noi() as db:
            row = db.execute("SELECT * FROM du_an WHERE id=?", (identifier,)).fetchone()
        if not row or (row["owner"] != actor["id"] and actor["role"] != "quan-tri"):
            raise ValueError("Không tìm thấy dự án trong phạm vi quyền")
        return {**dict(row), "archived": bool(row["archived"])}

    def list(self, actor):
        self._auth(actor)
        with self.kho.ket_noi() as db:
            sql = "SELECT * FROM du_an" + ("" if actor["role"] == "quan-tri" else " WHERE owner=?")
            rows = db.execute(sql + " ORDER BY updated DESC LIMIT 100", () if actor["role"] == "quan-tri" else (actor["id"],)).fetchall()
        return {"projects": [{**dict(r), "archived": bool(r["archived"])} for r in rows]}

    def create(self, actor, data):
        self._auth(actor)
        fields = self._fields(data)
        identifier, now = secrets.token_hex(12), time.time()
        with self.kho.ket_noi() as db:
            if db.execute("SELECT count(*) FROM du_an WHERE owner=?", (actor["id"],)).fetchone()[0] >= 100:
                raise ValueError("Đã đạt giới hạn 100 dự án cho danh tính này")
            db.execute("INSERT INTO du_an VALUES (?,?,?,?,?,?,?,?)", (identifier, actor["id"], fields["name"], fields["instructions"], fields["context"], 0, now, now))
        self.kho.su_kien(actor["id"], "tao-du-an", identifier)
        return self._get(actor, identifier)

    def update(self, actor, data):
        project = self._get(actor, data.get("id"))
        if project["archived"]:
            raise ValueError("Khôi phục dự án trước khi cập nhật")
        fields = self._fields(data)
        with self.kho.ket_noi() as db:
            db.execute("UPDATE du_an SET name=?,instructions=?,context=?,updated=? WHERE id=?", (fields["name"], fields["instructions"], fields["context"], time.time(), project["id"]))
        self.kho.su_kien(actor["id"], "cap-nhat-du-an", project["id"])
        return self._get(actor, project["id"])

    def archive(self, actor, identifier, archived=True):
        project = self._get(actor, identifier)
        with self.kho.ket_noi() as db:
            db.execute("UPDATE du_an SET archived=?,updated=? WHERE id=?", (int(archived), time.time(), project["id"]))
        self.kho.su_kien(actor["id"], "luu-tru-du-an" if archived else "khoi-phuc-du-an", project["id"])
        return self._get(actor, project["id"])

    def context_for(self, actor, identifier):
        project = self._get(actor, identifier)
        if project["archived"]:
            raise ValueError("Dự án đã lưu trữ; cần khôi phục trước khi tạo công việc mới")
        return {k: project[k] for k in ("id", "name", "instructions", "context", "updated")}
