"""Nền lưu tệp Office: quyền dự án, phiên bản nguyên tử và chống ghi đè.

Chưa có bộ soạn thảo hoặc quét mã độc. Tệp là dữ liệu mờ, không được thực thi,
chuyển đổi hay đưa ra web root. BLOB nhỏ trong SQLite để bản sao lưu hiện có
giữ nguyên cả nội dung và metadata trong một giao dịch.
"""

import base64
import binascii
import hashlib
import re
import secrets
import time
from pathlib import PurePath


class VanPhong:
    MAX_BYTES = 32 * 1024
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
            """)

    def status(self, actor, args):
        with self.kho.ket_noi() as db:
            self.projects.authorize(actor, args.get("project_id"), db=db)
        return {
            "storage": "bdsg-sqlite",
            "editor_state": "chua-cau-hinh",
            "google_state": "chua-ket-noi",
            "scan_state": "chua-quet",
            "limits": {
                "file_bytes": self.MAX_BYTES,
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
            raise ValueError("Tệp đã thay đổi; đọc lại trước khi lưu để tránh ghi đè")

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
        # Thùng rác và lịch sử vẫn chiếm dung lượng, không đặt lại hạn mức khi xóa mềm.
        if (
            (creating and files >= self.MAX_FILES)
            or versions >= self.MAX_VERSIONS
            or total + size > self.MAX_TOTAL_BYTES
        ):
            raise ValueError("Dự án đạt giới hạn tệp, lịch sử hoặc dung lượng Office")

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
        pid, identifier, now = (
            args.get("project_id"),
            secrets.token_hex(12),
            time.time(),
        )
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            self._project(actor, pid, db, True)
            self._quota(db, pid, len(raw), creating=True)
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
                "INSERT INTO office_files VALUES (?,?,?,?,?,?,?,?,?)",
                tuple(row.values()),
            )
            self._version(db, row, actor, raw)
            self._audit(db, actor, "office-tao-tep", identifier)
        return self._metadata(row)

    def read(self, actor, args):
        with self.kho.ket_noi() as db:
            row = self._file(actor, args.get("id"), db)
            version = args.get("version", row["version"])
            if type(version) is not int or version < 1:
                raise ValueError("Phiên bản không hợp lệ")
            value = db.execute(
                "SELECT * FROM office_versions WHERE file_id=? AND version=?",
                (row["id"], version),
            ).fetchone()
            if not value:
                raise ValueError("Không có phiên bản này")
            if hashlib.sha256(value["content"]).hexdigest() != value["sha256"]:
                raise ValueError(
                    "Nội dung không khớp dấu kiểm; cần kiểm tra bản sao lưu"
                )
            return {
                "file": self._metadata(row),
                "version": version,
                "size": value["size"],
                "sha256": value["sha256"],
                "content_base64": base64.b64encode(value["content"]).decode("ascii"),
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
