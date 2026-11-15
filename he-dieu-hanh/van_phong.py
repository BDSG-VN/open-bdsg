"""Nền lưu tệp Office: quyền dự án, phiên bản nguyên tử và chống ghi đè.

Chưa có bộ soạn thảo hoặc quét mã độc. Tệp là dữ liệu mờ, không được thực thi,
chuyển đổi hay đưa ra web root. BLOB nhỏ trong SQLite để bản sao lưu hiện có
giữ nguyên cả nội dung và metadata trong một giao dịch.
"""

import base64
import binascii
import hashlib
import json
import re
import secrets
import time
from pathlib import PurePath

from kiem_tep_office import kiem_tep


class LoiXungDotVanPhong(ValueError):
    """Mã lỗi ổn định cho UI, không cần công khai thông điệp ngoại lệ."""


class LoiHanMucVanPhong(ValueError):
    """Kho đã đầy; dữ liệu chi tiết vẫn nằm sau quyền dự án."""


class VanPhong:
    MAX_BYTES = 32 * 1024
    MAX_FILE_BYTES = 8 * 1024 * 1024
    CHUNK_BYTES = 512 * 1024
    UPLOAD_TTL = 15 * 60
    MAX_GLOBAL_BYTES = 1024 * 1024 * 1024
    MAX_FILES = 100
    MAX_VERSIONS = 1000
    MAX_TOTAL_BYTES = 20 * 1024 * 1024
    EXTENSIONS = frozenset({".txt", ".md", ".csv", ".pdf", ".docx", ".xlsx", ".pptx"})

    def __init__(self, kho, projects):
        self.kho, self.projects = kho, projects
        with kho.ket_noi() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS office_files(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    name TEXT NOT NULL, owner TEXT NOT NULL,
                    revision INTEGER NOT NULL, version INTEGER NOT NULL,
                    trashed INTEGER NOT NULL, created REAL NOT NULL,
                    updated REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS office_project
                    ON office_files(project_id,updated);
                CREATE TABLE IF NOT EXISTS office_versions(
                    file_id TEXT NOT NULL REFERENCES office_files(id),
                    version INTEGER NOT NULL, content BLOB NOT NULL,
                    size INTEGER NOT NULL, sha256 TEXT NOT NULL,
                    actor TEXT NOT NULL, created REAL NOT NULL,
                    PRIMARY KEY(file_id,version)
                );
                CREATE TABLE IF NOT EXISTS office_uploads(
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, project_id TEXT NOT NULL,
                    request_key TEXT NOT NULL, name TEXT NOT NULL, total INTEGER NOT NULL,
                    received INTEGER NOT NULL, sha256 TEXT NOT NULL, content BLOB,
                    state TEXT NOT NULL, file_id TEXT, expires REAL NOT NULL,
                    UNIQUE(owner,request_key)
                );
                CREATE INDEX IF NOT EXISTS office_upload_project ON office_uploads(project_id,state,expires);
                CREATE TABLE IF NOT EXISTS office_upload_parts(
                    upload_id TEXT NOT NULL REFERENCES office_uploads(id) ON DELETE CASCADE,
                    offset INTEGER NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL,
                    PRIMARY KEY(upload_id,offset)
                );
                CREATE TABLE IF NOT EXISTS office_checks(
                    file_id TEXT NOT NULL, version INTEGER NOT NULL, result TEXT NOT NULL,
                    PRIMARY KEY(file_id,version)
                );
            """)

    def status(self, actor, args):
        with self.kho.ket_noi() as db:
            project = self._project(actor, args.get("project_id"), db)
            member = db.execute(
                "SELECT role FROM du_an_members WHERE project_id=? AND identity=?",
                (project["id"], actor["id"]),
            ).fetchone()
            can_write = not project["archived"] and (
                actor["role"] == "quan-tri"
                or project["owner"] == actor["id"]
                or (member and member["role"] == "editor")
            )
            files = db.execute(
                "SELECT count(*) FROM office_files WHERE project_id=?", (project["id"],)
            ).fetchone()[0]
            versions, total = db.execute(
                "SELECT count(*),coalesce(sum(v.size),0) FROM office_versions v "
                "JOIN office_files f ON f.id=v.file_id WHERE f.project_id=?",
                (project["id"],),
            ).fetchone()
            pending, reserved = db.execute(
                "SELECT count(*),coalesce(sum(total),0) FROM office_uploads WHERE project_id=? AND state='pending' AND expires>?",
                (project["id"], time.time()),
            ).fetchone()
        return {
            "storage": "bdsg-sqlite",
            "editor_state": "chua-cau-hinh",
            "google_state": "chua-ket-noi",
            "scan_state": "chua-quet",
            "permissions": {
                "can_write": bool(can_write),
                "archived": project["archived"],
            },
            "usage": {"files": files, "versions": versions, "bytes": total},
            "transfer_usage": {"pending": pending, "reserved_bytes": reserved},
            "limits": {
                "file_bytes": self.MAX_FILE_BYTES,
                "inline_file_bytes": self.MAX_BYTES,
                "chunk_bytes": self.CHUNK_BYTES,
                "upload_ttl_seconds": self.UPLOAD_TTL,
                "project_files_including_trash": self.MAX_FILES,
                "project_versions": self.MAX_VERSIONS,
                "project_bytes_including_history": self.MAX_TOTAL_BYTES,
            },
        }

    @classmethod
    def _name(cls, value):
        if (
            not isinstance(value, str)
            or value != value.strip()
            or not re.fullmatch(r"[^/\\\x00-\x1f\x7f]{1,120}", value)
            or PurePath(value).suffix.lower() not in cls.EXTENSIONS
        ):
            raise ValueError(
                "Tên tệp cần phần mở rộng được hỗ trợ và không chứa đường dẫn"
            )
        return value

    @classmethod
    def _content(cls, value):
        if not isinstance(value, str) or len(value) > ((cls.MAX_BYTES + 2) // 3) * 4:
            raise ValueError("Tệp vượt giới hạn 32 KiB")
        try:
            raw = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Nội dung base64 không hợp lệ") from None
        if len(raw) > cls.MAX_BYTES:
            raise ValueError("Tệp vượt giới hạn 32 KiB")
        return raw

    def _project(self, actor, pid, db, write=False):
        project = self.projects.authorize(actor, pid, write=write, db=db)
        # Xác thực ở nhân có thể xảy ra trước lúc chờ khóa SQLite. Kiểm lại
        # trên chính giao dịch để thu hồi đã commit không còn ghi được tệp.
        if actor["role"] == "quan-tri":
            active = (
                actor["id"] == "chu-quan"
                and db.execute(
                    "SELECT 1 FROM chu WHERE ma=?", (actor["id"],)
                ).fetchone()
            )
        else:
            active = db.execute(
                "SELECT 1 FROM agents WHERE ma=? AND active=1 AND role=?",
                (actor["id"], actor["role"]),
            ).fetchone()
        if not active:
            raise PermissionError("Danh tính đã bị thu hồi")
        if write and project["archived"]:
            raise ValueError("Khôi phục dự án trước khi sửa tệp Office")
        return project

    def _file(self, actor, identifier, db, write=False):
        if not isinstance(identifier, str) or not re.fullmatch(
            r"[a-f0-9]{24}", identifier
        ):
            raise ValueError("Không tìm thấy tệp trong phạm vi quyền")
        row = db.execute(
            "SELECT * FROM office_files WHERE id=?", (identifier,)
        ).fetchone()
        if not row:
            raise ValueError("Không tìm thấy tệp trong phạm vi quyền")
        self._project(actor, row["project_id"], db, write)
        return dict(row)

    @staticmethod
    def _check_revision(row, expected):
        if type(expected) is not int or expected != row["revision"]:
            raise LoiXungDotVanPhong(
                "Tệp đã thay đổi; đọc lại trước khi lưu để tránh ghi đè"
            )

    @staticmethod
    def _metadata(row):
        return {**row, "trashed": bool(row["trashed"]), "scan_state": "chua-quet"}

    def _quota(self, db, pid, size, creating=False):
        files = db.execute(
            "SELECT count(*) FROM office_files WHERE project_id=?", (pid,)
        ).fetchone()[0]
        versions, total = db.execute(
            "SELECT count(*),coalesce(sum(v.size),0) FROM office_versions v "
            "JOIN office_files f ON f.id=v.file_id WHERE f.project_id=?",
            (pid,),
        ).fetchone()
        pending, reserved = db.execute(
            "SELECT count(*),coalesce(sum(total),0) FROM office_uploads "
            "WHERE project_id=? AND state='pending' AND expires>?",
            (pid, time.time()),
        ).fetchone()
        global_bytes = db.execute(
            "SELECT coalesce(sum(size),0) FROM office_versions"
        ).fetchone()[0]
        global_reserved = db.execute(
            "SELECT coalesce(sum(total),0) FROM office_uploads WHERE state='pending' AND expires>?",
            (time.time(),),
        ).fetchone()[0]
        # Thùng rác và lịch sử vẫn chiếm dung lượng, không đặt lại hạn mức khi xóa mềm.
        if (
            (creating and files + pending >= self.MAX_FILES)
            or versions + pending >= self.MAX_VERSIONS
            or total + reserved + size > self.MAX_TOTAL_BYTES
            or global_bytes + global_reserved + size > self.MAX_GLOBAL_BYTES
        ):
            raise LoiHanMucVanPhong(
                "Dự án đạt giới hạn tệp, lịch sử hoặc dung lượng Office"
            )

    def _version(self, db, row, actor, raw):
        self._quota(db, row["project_id"], len(raw))
        db.execute(
            "INSERT INTO office_versions VALUES (?,?,?,?,?,?,?)",
            (
                row["id"],
                row["version"],
                raw,
                len(raw),
                hashlib.sha256(raw).hexdigest(),
                actor["id"],
                time.time(),
            ),
        )

    def list(self, actor, args):
        pid, trash = args.get("project_id"), args.get("trashed", False)
        if type(trash) is not bool:
            raise ValueError("Trạng thái thùng rác phải là boolean")
        with self.kho.ket_noi() as db:
            self._project(actor, pid, db)
            rows = db.execute(
                "SELECT f.*,v.size,v.sha256 FROM office_files f "
                "JOIN office_versions v ON v.file_id=f.id AND v.version=f.version "
                "WHERE f.project_id=? AND f.trashed=? ORDER BY f.updated DESC,f.id",
                (pid, int(trash)),
            ).fetchall()
        return {"files": [self._metadata(dict(r)) for r in rows]}

    def create(self, actor, args):
        name, raw = (
            self._name(args.get("name")),
            self._content(args.get("content_base64")),
        )
        pid = args.get("project_id")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            self._project(actor, pid, db, True)
            return self._create_file(db, actor, pid, name, raw)

    def _create_file(self, db, actor, pid, name, raw):
        self._quota(db, pid, len(raw), creating=True)
        identifier, now = secrets.token_hex(12), time.time()
        row = {
            "id": identifier,
            "project_id": pid,
            "name": name,
            "owner": actor["id"],
            "revision": 1,
            "version": 1,
            "trashed": 0,
            "created": now,
            "updated": now,
        }
        db.execute(
            "INSERT INTO office_files VALUES (?,?,?,?,?,?,?,?,?)", tuple(row.values())
        )
        self._version(db, row, actor, raw)
        self._audit(db, actor, "office-tao-tep", identifier)
        return self._metadata(row)

    @staticmethod
    def _upload_public(row):
        return {
            key: row[key]
            for key in (
                "id",
                "project_id",
                "name",
                "total",
                "received",
                "sha256",
                "state",
                "file_id",
                "expires",
            )
        }

    def _upload(self, actor, identifier, db, write=False):
        if not isinstance(identifier, str) or not re.fullmatch(
            r"[a-f0-9]{24}", identifier
        ):
            raise ValueError("Phiên tải không tồn tại")
        row = db.execute(
            "SELECT rowid AS blob_id,id,owner,project_id,request_key,name,total,received,sha256,state,file_id,expires "
            "FROM office_uploads WHERE id=?",
            (identifier,),
        ).fetchone()
        if not row or row["owner"] != actor["id"] or row["expires"] <= time.time():
            raise ValueError("Phiên tải không tồn tại hoặc đã hết hạn")
        self._project(actor, row["project_id"], db, write)
        return dict(row)

    def begin_upload(self, actor, args):
        pid, name = args.get("project_id"), self._name(args.get("name"))
        total, digest, key = (
            args.get("total"),
            args.get("sha256"),
            args.get("request_key"),
        )
        if type(total) is not int or not 0 <= total <= self.MAX_FILE_BYTES:
            raise ValueError("Tệp vượt 8 MiB")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Thiếu SHA-256")
        if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9-]{32,64}", key):
            raise ValueError("Mã yêu cầu không hợp lệ")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            self._project(actor, pid, db, True)
            db.execute("DELETE FROM office_uploads WHERE expires<=?", (time.time(),))
            old = db.execute(
                "SELECT id FROM office_uploads WHERE owner=? AND request_key=?",
                (actor["id"], key),
            ).fetchone()
            if old:
                row = self._upload(actor, old["id"], db, True)
                if (row["project_id"], row["name"], row["total"], row["sha256"]) != (
                    pid,
                    name,
                    total,
                    digest,
                ):
                    raise LoiXungDotVanPhong("Mã yêu cầu đã gắn với tệp khác")
                return self._upload_public(row)
            if (
                db.execute(
                    "SELECT count(*) FROM office_uploads WHERE owner=? AND state='pending'",
                    (actor["id"],),
                ).fetchone()[0]
                >= 2
            ):
                raise LoiHanMucVanPhong("Chỉ giữ hai phiên tải đồng thời")
            self._quota(db, pid, total, creating=True)
            identifier = secrets.token_hex(12)
            db.execute(
                "INSERT INTO office_uploads VALUES (?,?,?,?,?,?,0,?,zeroblob(?),'pending',NULL,?)",
                (
                    identifier,
                    actor["id"],
                    pid,
                    key,
                    name,
                    total,
                    digest,
                    total,
                    time.time() + self.UPLOAD_TTL,
                ),
            )
            self._audit(db, actor, "office-bat-dau-tai", identifier)
            return self._upload_public(self._upload(actor, identifier, db))

    def upload_status(self, actor, args):
        with self.kho.ket_noi() as db:
            return self._upload_public(self._upload(actor, args.get("id"), db))

    def uploads(self, actor, args):
        with self.kho.ket_noi() as db:
            self._project(actor, args.get("project_id"), db)
            rows = db.execute(
                "SELECT id,project_id,name,total,received,sha256,state,file_id,expires FROM office_uploads "
                "WHERE owner=? AND project_id=? AND expires>? ORDER BY expires DESC LIMIT 102",
                (actor["id"], args.get("project_id"), time.time()),
            ).fetchall()
            return {"uploads": [self._upload_public(dict(row)) for row in rows]}

    def upload_part(self, actor, args):
        value = args.get("content_base64")
        if not isinstance(value, str) or len(value) > ((self.CHUNK_BYTES + 2) // 3) * 4:
            raise ValueError("Phần tải vượt giới hạn")
        try:
            raw = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Phần tải không hợp lệ") from None
        offset = args.get("offset")
        if (
            type(offset) is not int
            or offset < 0
            or not 0 < len(raw) <= self.CHUNK_BYTES
        ):
            raise ValueError("Vị trí phần tải không hợp lệ")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._upload(actor, args.get("id"), db, True)
            if (
                row["state"] != "pending"
                or offset > row["received"]
                or offset + len(raw) > row["total"]
            ):
                raise LoiXungDotVanPhong("Đọc trạng thái phiên tải trước khi tiếp tục")
            with db.blobopen("office_uploads", "content", row["blob_id"]) as blob:
                blob.seek(offset)
                if offset < row["received"]:
                    recorded = db.execute(
                        "SELECT size,sha256 FROM office_upload_parts WHERE upload_id=? AND offset=?",
                        (row["id"], offset),
                    ).fetchone()
                    if (
                        not recorded
                        or recorded["size"] != len(raw)
                        or recorded["sha256"] != hashlib.sha256(raw).hexdigest()
                        or offset + len(raw) > row["received"]
                        or blob.read(len(raw)) != raw
                    ):
                        raise LoiXungDotVanPhong("Phần gửi lại không khớp")
                    return self._upload_public(row)
                blob.write(raw)
            db.execute(
                "INSERT INTO office_upload_parts VALUES (?,?,?,?)",
                (row["id"], offset, len(raw), hashlib.sha256(raw).hexdigest()),
            )
            row["received"] += len(raw)
            row["expires"] = time.time() + self.UPLOAD_TTL
            db.execute(
                "UPDATE office_uploads SET received=?,expires=? WHERE id=?",
                (row["received"], row["expires"], row["id"]),
            )
            self._audit(db, actor, "office-ghi-phan", row["id"] + ":" + str(offset))
            return self._upload_public(row)

    def finish_upload(self, actor, args):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._upload(actor, args.get("id"), db, True)
            if row["state"] == "complete":
                return {
                    "file": self._metadata(self._file(actor, row["file_id"], db)),
                    "completed": True,
                }
            if row["received"] != row["total"]:
                raise ValueError("Chưa đủ nội dung tệp")
            with db.blobopen(
                "office_uploads", "content", row["blob_id"], readonly=True
            ) as blob:
                raw = blob.read()
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError("Nội dung không khớp SHA-256")
            checks = kiem_tep(row["name"], raw)
            # Bỏ reservation trong cùng giao dịch; nếu lưu lỗi, reservation vẫn nguyên.
            db.execute(
                "UPDATE office_uploads SET state='committing' WHERE id=?", (row["id"],)
            )
            file = self._create_file(db, actor, row["project_id"], row["name"], raw)
            db.execute(
                "INSERT INTO office_checks VALUES (?,?,?)",
                (file["id"], 1, json.dumps(checks)),
            )
            db.execute(
                "UPDATE office_uploads SET state='complete',file_id=?,content=NULL,expires=? WHERE id=?",
                (file["id"], time.time() + self.UPLOAD_TTL, row["id"]),
            )
            return {"file": file, "checks": checks, "completed": True}

    def cancel_upload(self, actor, args):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._upload(actor, args.get("id"), db)
            if row["state"] == "complete":
                return {
                    "cancelled": False,
                    "completed": True,
                    "file_id": row["file_id"],
                }
            db.execute("DELETE FROM office_uploads WHERE id=?", (row["id"],))
            self._audit(db, actor, "office-huy-tai", row["id"])
            return {"cancelled": True, "completed": False}

    def read_part(self, actor, args):
        offset, version = args.get("offset"), args.get("version")
        if (
            type(offset) is not int
            or offset < 0
            or type(version) is not int
            or version < 1
        ):
            raise ValueError("Vị trí hoặc phiên bản không hợp lệ")
        with self.kho.ket_noi() as db:
            row = self._file(actor, args.get("id"), db)
            value = db.execute(
                "SELECT rowid AS blob_id,size,sha256 FROM office_versions WHERE file_id=? AND version=?",
                (row["id"], version),
            ).fetchone()
            if not value or offset > value["size"]:
                raise ValueError("Không có phần tệp này")
            with db.blobopen(
                "office_versions", "content", value["blob_id"], readonly=True
            ) as blob:
                blob.seek(offset)
                raw = blob.read(self.CHUNK_BYTES)
            return {
                "version": version,
                "offset": offset,
                "next_offset": offset + len(raw),
                "size": value["size"],
                "sha256": value["sha256"],
                "content_base64": base64.b64encode(raw).decode("ascii"),
            }

    def read(self, actor, args):
        with self.kho.ket_noi() as db:
            row = self._file(actor, args.get("id"), db)
            version = args.get("version", row["version"])
            if type(version) is not int or version < 1:
                raise ValueError("Phiên bản không hợp lệ")
            value = db.execute(
                "SELECT rowid AS blob_id,version,size,sha256 FROM office_versions WHERE file_id=? AND version=?",
                (row["id"], version),
            ).fetchone()
            if not value:
                raise ValueError("Không có phiên bản này")
            raw = None
            if value["size"] <= self.MAX_BYTES:
                with db.blobopen(
                    "office_versions", "content", value["blob_id"], readonly=True
                ) as blob:
                    raw = blob.read()
                if hashlib.sha256(raw).hexdigest() != value["sha256"]:
                    raise ValueError(
                        "Nội dung không khớp dấu kiểm; cần kiểm tra bản sao lưu"
                    )
            check = db.execute(
                "SELECT result FROM office_checks WHERE file_id=? AND version=?",
                (row["id"], version),
            ).fetchone()
            return {
                "file": self._metadata(row),
                "version": version,
                "size": value["size"],
                "sha256": value["sha256"],
                "content_base64": None
                if raw is None
                else base64.b64encode(raw).decode("ascii"),
                "checks": json.loads(check[0])
                if check
                else {
                    "format_state": "chua-kiem",
                    "virus_state": "chua-quet",
                    "warnings": [],
                },
            }

    def history(self, actor, args):
        with self.kho.ket_noi() as db:
            row = self._file(actor, args.get("id"), db)
            versions = db.execute(
                "SELECT version,size,sha256,actor,created FROM office_versions "
                "WHERE file_id=? ORDER BY version DESC",
                (row["id"],),
            ).fetchall()
        return {"versions": [dict(v) for v in versions]}

    @staticmethod
    def _audit(db, actor, action, target):
        # Cùng giao dịch với thay đổi, không ghi nội dung hoặc tên tệp vào nhật ký.
        db.execute(
            "INSERT INTO su_kien(actor,action,target,created) VALUES (?,?,?,?)",
            (actor["id"], action, target, time.time()),
        )

    def update(self, actor, args):
        """Một thay đổi mỗi lần, tất cả đều so sánh revision và giữ lại lịch sử."""
        action = args.get("action")
        if action not in ("save", "rename", "trash", "untrash", "restore-version"):
            raise ValueError("Thao tác Office chưa hỗ trợ")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._file(actor, args.get("id"), db, True)
            self._check_revision(row, args.get("expected_revision"))
            if row["trashed"] and action != "untrash":
                raise ValueError("Khôi phục tệp trong thùng rác trước khi thay đổi")
            if action == "untrash" and not row["trashed"]:
                raise ValueError("Tệp chưa nằm trong thùng rác")
            if action == "rename":
                name = self._name(args.get("name"))
                if (
                    PurePath(name).suffix.lower()
                    != PurePath(row["name"]).suffix.lower()
                ):
                    raise ValueError("Đổi tên không chuyển đổi định dạng tệp")
                row["name"] = name
            elif action in ("trash", "untrash"):
                row["trashed"] = int(action == "trash")
            else:
                if action == "save":
                    raw = self._content(args.get("content_base64"))
                else:
                    version = args.get("version")
                    if type(version) is not int or version < 1:
                        raise ValueError("Phiên bản không hợp lệ")
                    old = db.execute(
                        "SELECT content,sha256 FROM office_versions WHERE file_id=? AND version=?",
                        (row["id"], version),
                    ).fetchone()
                    if (
                        not old
                        or hashlib.sha256(old["content"]).hexdigest() != old["sha256"]
                    ):
                        raise ValueError("Không có phiên bản hợp lệ để khôi phục")
                    raw = old["content"]
                row["version"] += 1
                self._version(db, row, actor, raw)
            row["revision"] += 1
            row["updated"] = time.time()
            db.execute(
                "UPDATE office_files SET name=?,revision=?,version=?,trashed=?,updated=? WHERE id=?",
                (
                    row["name"],
                    row["revision"],
                    row["version"],
                    row["trashed"],
                    row["updated"],
                    row["id"],
                ),
            )
            self._audit(db, actor, "office-" + action, row["id"])
        return self._metadata(row)
