"""Kho tài liệu bất biến; tải qua xác thực, không xuất tệp riêng ra web root."""

import base64
import hashlib
import io
import os
import re
import secrets
import time
import json
import subprocess
import tempfile
import threading
from pathlib import Path
from co_lap import command_for
from quet_virus import QuetVirus


class TaiLieu:
    MAX_BYTES = 1024 * 1024

    def __init__(self, kho, projects):
        self.kho, self.projects = kho, projects
        self.scanner = QuetVirus()
        self.pdf_capacity = threading.BoundedSemaphore(1)
        self.root = kho.root / "tai-lieu"
        self.root.mkdir(mode=0o700, exist_ok=True)
        with kho.ket_noi() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,project_id TEXT,owner TEXT,name TEXT,version INTEGER,sha256 TEXT,size INTEGER,text TEXT,truncated INTEGER,created REAL,UNIQUE(project_id,name,version))"
            )

    def _project(self, actor, pid, write=False, db=None):
        p = self.projects.authorize(actor, pid, write=write, db=db)
        if write and p["archived"]:
            raise ValueError("Khôi phục dự án trước khi thêm tài liệu")
        return p

    def upload(self, actor, args):
        pid = args.get("project_id")
        self._project(actor, pid, True)
        name = args.get("name", "")
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[^/\\\x00-\x1f]{1,100}", name)
            or Path(name).suffix.lower() not in (".txt", ".md", ".csv", ".pdf")
        ):
            raise ValueError(
                "Chỉ nhận TXT, Markdown, CSV và PDF văn bản; tên không chứa đường dẫn"
            )
        try:
            raw = base64.b64decode(args.get("content_base64", ""), validate=True)
        except Exception:
            raise ValueError("Nội dung tệp không hợp lệ") from None
        if not 0 < len(raw) <= self.MAX_BYTES:
            raise ValueError("Tệp phải từ 1 byte đến 1 MiB")
        self.scanner.scan(raw)
        if name.lower().endswith(".pdf"):
            if not self.pdf_capacity.acquire(blocking=False):
                raise ValueError(
                    "Bộ đọc PDF đang bận; thử lại khi tệp hiện tại hoàn tất"
                )
            try:
                with tempfile.TemporaryDirectory(prefix="bdsg-pdf-") as folder:
                    work = Path(folder) / "work"
                    work.mkdir(mode=0o700)
                    with (
                        (Path(folder) / "stdout").open("w+b") as out,
                        (Path(folder) / "stderr").open("w+b") as err,
                    ):
                        subprocess.run(
                            command_for(),
                            input=json.dumps(
                                {"mode": "pdf", "data": base64.b64encode(raw).decode()}
                            ).encode(),
                            stdout=out,
                            stderr=err,
                            timeout=15,
                            check=True,
                        )
                        out.seek(0)
                        result = json.loads(out.read(100000))
                        text = result["text"] + (
                            "\n[Phần tiếp theo đã rút gọn]"
                            if result["truncated"]
                            else ""
                        )
            except Exception:
                raise ValueError(
                    "PDF phải có văn bản, không mã hóa, tối đa 50 trang"
                ) from None
            finally:
                self.pdf_capacity.release()
        else:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise ValueError("Tài liệu văn bản cần mã UTF-8") from None
            if "\x00" in text:
                raise ValueError("Không nhận tệp nhị phân dưới tên văn bản")
        identifier = secrets.token_hex(12)
        path = self.root / identifier
        try:
            with self.kho.ket_noi() as db:
                # Serialize allocation, including quota and immutable version number.
                db.execute("BEGIN IMMEDIATE")
                self._project(actor, pid, True, db=db)
                count, total = db.execute(
                    "SELECT count(*),coalesce(sum(size),0) FROM documents WHERE project_id=?",
                    (pid,),
                ).fetchone()
                if count >= 100 or total + len(raw) > 20 * 1024 * 1024:
                    raise ValueError("Dự án đạt hạn 100 tệp hoặc 20 MiB")
                version = db.execute(
                    "SELECT coalesce(max(version),0)+1 FROM documents WHERE project_id=? AND name=?",
                    (pid, name),
                ).fetchone()[0]
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(raw)
                db.execute(
                    "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        identifier,
                        pid,
                        actor["id"],
                        name,
                        version,
                        hashlib.sha256(raw).hexdigest(),
                        len(raw),
                        text[:16000],
                        int(len(text) > 16000),
                        time.time(),
                    ),
                )
        except Exception:
            if path.is_file():
                path.unlink()
            raise
        self.kho.su_kien(actor["id"], "tai-tai-lieu", identifier)
        return self.get(actor, identifier, False)

    def get(self, actor, identifier, content=True):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN")
            row = db.execute(
                "SELECT * FROM documents WHERE id=?", (identifier,)
            ).fetchone()
            if not row:
                raise ValueError("Tài liệu không tồn tại trong phạm vi quyền")
            self._project(actor, row["project_id"], db=db)
        value = dict(row)
        if not content:
            value.pop("text")
        return value

    def list(self, actor, pid):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN")
            self._project(actor, pid, db=db)
            return {
                "documents": [
                    dict(r)
                    for r in db.execute(
                        "SELECT id,project_id,name,version,sha256,size,truncated,created FROM documents WHERE project_id=? ORDER BY created DESC LIMIT 100",
                        (pid,),
                    )
                ]
            }

    def snapshot(self, actor, ids, pid):
        if (
            not isinstance(ids, list)
            or len(ids) > 5
            or any(not isinstance(x, str) for x in ids)
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Chọn tối đa 5 tài liệu khác nhau")
        result = []
        for identifier in ids:
            if not isinstance(identifier, str):
                raise ValueError("Mã tài liệu không hợp lệ")
            doc = self.get(actor, identifier)
            if doc["project_id"] != pid:
                raise ValueError("Tài liệu không thuộc dự án đang chọn")
            result.append(
                {
                    k: doc[k]
                    for k in ("id", "name", "version", "sha256", "text", "truncated")
                }
            )
        if sum(len(d["text"].encode()) for d in result) > 24000:
            raise ValueError("Nội dung tài liệu vượt 24 KiB; chọn ít tài liệu hơn")
        return result

    def download(self, actor, identifier):
        doc = self.get(actor, identifier, False)
        raw = (self.root / doc["id"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != doc["sha256"]:
            raise ValueError("Tệp không khớp dấu kiểm")
        self.scanner.scan(raw)
        # Scan có thể chạy lâu; quyền phải còn hiệu lực trước khi trả byte.
        self.get(actor, identifier, False)
        return doc, raw
