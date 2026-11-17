"""Phiên Docs có lưu bền: khóa soạn thảo, callback ký, quét và CAS phiên bản.

Người cùng quyền dự án dùng chung phiên. Snapshot force-save chỉ báo
thành công sau commit, callback phiên cũ không được ghi đè phiên mới.
"""

import hashlib
import http.client
import json
import os
import re
import secrets
import time
from urllib.parse import unquote, urlencode, urlsplit

from chu_ky_office import sign, verify
from kiem_tep_office import kiem_tep
from van_phong import LoiXungDotVanPhong
from phien_office_don_vi import PhienOfficeDonVi


class SoanThaoOffice:
    def __init__(self, office, origin):
        self.office, self.kho, self.origin = office, office.kho, origin
        self.secret = os.environ.get("BDSG_OFFICE_JWT_SECRET", "")
        self.prefix = "/office-docs/"
        self.scopes = PhienOfficeDonVi(office)
        with self.kho.ket_noi() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS office_editors(
                    key TEXT PRIMARY KEY,file_id TEXT NOT NULL,actor TEXT NOT NULL,
                    role TEXT NOT NULL,revision INTEGER NOT NULL,cap TEXT NOT NULL,
                    expires REAL NOT NULL,state TEXT NOT NULL,pending TEXT,
                    pending_at REAL,last_saved REAL,sha256 TEXT);
                CREATE INDEX IF NOT EXISTS office_editor_file ON office_editors(file_id,state);
                CREATE TABLE IF NOT EXISTS office_editor_members(
                    key TEXT NOT NULL,actor TEXT NOT NULL,role TEXT NOT NULL,
                    PRIMARY KEY(key,actor));
                CREATE TABLE IF NOT EXISTS office_editor_requests(
                    id TEXT PRIMARY KEY,key TEXT NOT NULL,actor TEXT NOT NULL,role TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS office_editor_callbacks(
                    key TEXT NOT NULL,status INTEGER NOT NULL,request TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,created REAL NOT NULL,
                    PRIMARY KEY(key,status,request));
                CREATE TABLE IF NOT EXISTS office_editor_failures(
                    key TEXT PRIMARY KEY,request TEXT NOT NULL,created REAL NOT NULL);
            """)

    def status(self):
        return {
            "state": "da-cau-hinh" if len(self.secret) >= 32 else "chua-cau-hinh",
            "edition": "ONLYOFFICE Docs Community",
            "mobile_editing": False,
        }

    def create(self, actor, args):
        from mau_office import create

        name = self.office._name(args.get("name"))
        raw = create(name.rsplit(".", 1)[-1].lower())
        return self.office.create_bytes(
            actor, args.get("project_id"), name, raw, args.get("request_key")
        )

    def _row(self, db, key):
        row = db.execute("SELECT * FROM office_editors WHERE key=?", (key,)).fetchone()
        if not row or row["expires"] < time.time() or row["state"] != "active":
            raise PermissionError("Phiên soạn thảo đã hết hiệu lực")
        if self.scopes.units is not None:
            self.scopes.actors(key,db)
        return dict(row)

    def _actor(self, session, db):
        if self.scopes.units is not None:
            return self.scopes.actor(session['key'],session['actor'],db)
        return {"id": session["actor"], "role": session["role"]}

    def open(self, actor, args):
        if self.status()["state"] != "da-cau-hinh":
            raise ValueError("Chưa cấu hình bộ soạn thảo")
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            file = self.office._file(actor, args.get("id"), db, True)
            reference = self.scopes.reference(actor,file['project_id'],db)
            if file["trashed"]:
                raise ValueError("Tệp đang trong thùng rác")
            extension = file["name"].rsplit(".", 1)[-1].lower()
            kind = {"docx": "word", "xlsx": "cell", "pptx": "slide"}.get(extension)
            if not kind:
                raise ValueError("Định dạng chưa có bộ soạn thảo")
            raw = db.execute(
                "SELECT content FROM office_versions WHERE file_id=? AND version=?",
                (file["id"], file["version"]),
            ).fetchone()[0]
        kiem_tep(file["name"], raw)
        checked = self.office.scanner.scan(raw)
        if checked["virus_state"] != "khong-phat-hien":
            raise ValueError("Cần quét virus trước khi mở bộ soạn thảo")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self.office._file(actor, file["id"], db, True)
            self.office._check_revision(current, file["revision"])
            if self.scopes.reference(actor,file['project_id'],db)!=reference:
                raise PermissionError('Quyền thay đổi trong lúc kiểm tệp Office')
            sql="SELECT * FROM office_editors e WHERE file_id=? AND state='active' AND expires>?"
            params=[file['id'],time.time()]
            if reference is not None:
                sql+=" AND EXISTS(SELECT 1 FROM office_editor_scopes s WHERE s.key=e.key AND json_extract(s.unit_ref,'$.unit_id')=?)"
                params.append(reference['unit']['unit_id'])
            old=db.execute(sql,params).fetchone()
            if old and reference is not None:
                try:self._row(db,old['key'])
                except (PermissionError,ValueError):
                    db.execute("UPDATE office_editors SET state='revoked',pending=NULL WHERE key=?",(old['key'],))
                    old=None
            if old:
                session = dict(old)
                if old["revision"] != file["revision"]:
                    raise LoiXungDotVanPhong("Tệp đang có phiên chỉnh sửa khác")
            else:
                session = {
                    "key": "bdsg-" + secrets.token_hex(16),
                    "file_id": file["id"],
                    "actor": actor["id"],
                    "role": actor["role"],
                    "revision": file["revision"],
                    "cap": secrets.token_urlsafe(32),
                    "expires": time.time() + 12 * 3600,
                    "state": "active",
                    "pending": None,
                    "pending_at": None,
                    "last_saved": None,
                    "sha256": checked["sha256"],
                }
                db.execute(
                    "INSERT INTO office_editors VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    tuple(session.values()),
                )
            db.execute(
                "INSERT INTO office_editor_members VALUES (?,?,?) ON CONFLICT(key,actor) DO UPDATE SET role=excluded.role",
                (session["key"], actor["id"], actor["role"]),
            )
            if reference is not None and not db.execute('SELECT 1 FROM office_editor_scopes WHERE key=? AND actor=?',(session['key'],actor['id'])).fetchone():
                self.scopes.remember(session['key'],actor,file['project_id'],db)
        url = (
            self.origin
            + "/api/office-source?"
            + urlencode({"key": session["key"], "cap": session["cap"]})
        )
        config = {
            "documentType": kind,
            "type": "desktop",
            "width": "100%",
            "height": "100%",
            "document": {
                "fileType": extension,
                "key": session["key"],
                "title": file["name"],
                "url": url,
                "permissions": {"edit": True, "download": False, "print": False},
            },
            "editorConfig": {
                "mode": "edit",
                "lang": "vi",
                "callbackUrl": self.origin + "/api/office-callback",
                "user": {"id": actor["id"], "name": actor.get("name", actor["id"])},
                "coEditing": {"mode": "fast", "change": False},
            },
        }
        config["token"] = sign(
            {**config, "exp": int(session["expires"]), "iat": int(time.time())},
            self.secret,
        )
        return {
            "key": session["key"],
            "config": config,
            "api_url": self.prefix + "web-apps/apps/api/documents/api.js",
        }

    def source(self, query, authorization):
        key, cap = query.get("key", [""])[0], query.get("cap", [""])[0]
        url = self.origin + "/api/office-source?" + urlencode({"key": key, "cap": cap})
        signed = verify(authorization.removeprefix("Bearer "), self.secret, "download")
        if signed.get("url") != url:
            raise PermissionError("Nguồn Office không khớp chữ ký")
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            session = self._row(db, key)
            if not secrets.compare_digest(cap, session["cap"]):
                raise PermissionError("Không có quyền tải nguồn")
            file = self.office._file(self._actor(session,db), session["file_id"], db, True)
            self.office._check_revision(file, session["revision"])
            raw = db.execute(
                "SELECT content FROM office_versions WHERE file_id=? AND version=?",
                (file["id"], file["version"]),
            ).fetchone()[0]
            return raw

    def engine_access(self, actor, path):
        if not actor:
            return False
        if len(path) > 8192:
            return False
        # Cache và WebSocket mang key; tài nguyên tĩnh vẫn yêu cầu phiên BDSG.
        path = unquote(urlsplit(path).path)
        if "%" in path or ".." in path:
            return False
        matches = re.findall(
            r"(?:^|/)(bdsg-[a-f0-9]{32})(?:_[A-Za-z0-9.-]+)?(?:/|$)", path
        )
        if ("/cache/" in path or "/doc/" in path) and not matches:
            return False
        for key in matches:
            try:
                with self.kho.ket_noi() as db:
                    db.execute('BEGIN')
                    session = self._row(db, key)
                    if self.scopes.units is not None:
                        self.scopes.actor(key,actor['id'],db,current=actor)
                    self.office._file(actor, session["file_id"], db)
            except (ValueError, PermissionError):
                return False
        return True

    def save(self, actor, args):
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            session = self._row(db, args.get("key"))
            if self.scopes.units is not None:
                self.scopes.actor(session['key'],actor['id'],db,current=actor)
            file = self.office._file(actor, session["file_id"], db, True)
            if not db.execute(
                "SELECT 1 FROM office_editor_members WHERE key=? AND actor=?",
                (session["key"], actor["id"]),
            ).fetchone():
                raise PermissionError("Phiên thuộc người khác")
            self.office._check_revision(file, session["revision"])
            if session["pending"] and session["pending_at"] > time.time() - 120:
                return {"state": "dang-luu", "request_id": session["pending"]}
            request = secrets.token_hex(16)
            db.execute(
                "DELETE FROM office_editor_failures WHERE key=?", (session["key"],)
            )
            db.execute(
                "UPDATE office_editors SET pending=?,pending_at=? WHERE key=?",
                (request, time.time(), session["key"]),
            )
            db.execute(
                "INSERT INTO office_editor_requests VALUES (?,?,?,?)",
                (request, session["key"], actor["id"], actor["role"]),
            )
        payload = {
            "c": "forcesave",
            "key": session["key"],
            "userdata": request,
            "operation": "command",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        }
        connection = http.client.HTTPConnection("127.0.0.1", 8088, timeout=10)
        try:
            connection.request(
                "POST",
                "/command",
                json.dumps({"token": sign(payload, self.secret)}),
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            value = json.loads(response.read(8192))
            if response.status != 200 or value.get("error") not in (0, 4):
                raise ValueError("Bộ soạn thảo chưa nhận lệnh lưu")
            if value["error"] == 4:
                with self.kho.ket_noi() as db:
                    db.execute(
                        "UPDATE office_editors SET pending=NULL WHERE key=? AND pending=?",
                        (session["key"], request),
                    )
                return {"state": "khong-co-thay-doi"}
            return {"state": "dang-luu", "request_id": request}
        finally:
            connection.close()

    def progress(self, actor, args):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            row = db.execute(
                "SELECT * FROM office_editors WHERE key=?", (args.get("key"),)
            ).fetchone()
            if (
                not row
                or not db.execute(
                    "SELECT 1 FROM office_editor_members WHERE key=? AND actor=?",
                    (args.get("key"), actor["id"]),
                ).fetchone()
            ):
                raise PermissionError("Không có quyền xem phiên")
            file = self.office._file(actor, row["file_id"], db)
            if self.scopes.units is not None:
                self.scopes.actor(row['key'],actor['id'],db,current=actor)
            return {
                "state": row["state"],
                "pending": bool(row["pending"]),
                "pending_at": row["pending_at"],
                "last_saved": row["last_saved"],
                "revision": file["revision"],
                "save_error": bool(
                    db.execute(
                        "SELECT 1 FROM office_editor_failures WHERE key=?",
                        (args.get("key"),),
                    ).fetchone()
                ),
            }

    def _fetch(self, url, key):
        parsed = urlsplit(url)
        own = urlsplit(self.origin)
        if (
            parsed.scheme == "https"
            and parsed.netloc == own.netloc
            and parsed.path.startswith(self.prefix)
        ):
            path = parsed.path[len(self.prefix) - 1 :]
        elif parsed.scheme == "http" and parsed.netloc == "127.0.0.1:8088":
            path = parsed.path
        else:
            raise ValueError("Nguồn kết quả không được phép")
        if (
            parsed.fragment
            or ".." in path
            or not re.fullmatch(
                r"/cache/files/(?:data/)?"
                + re.escape(key)
                + r"(?:_[A-Za-z0-9.-]+)?/[A-Za-z0-9_./-]+",
                path,
            )
        ):
            raise ValueError("Đường dẫn kết quả không hợp lệ")
        connection = http.client.HTTPConnection("127.0.0.1", 8088, timeout=12)
        try:
            connection.request(
                "GET", path + ("?" + parsed.query if parsed.query else "")
            )
            response = connection.getresponse()
            raw = response.read(self.office.MAX_FILE_BYTES + 1)
            if response.status != 200 or len(raw) > self.office.MAX_FILE_BYTES:
                raise ValueError("Không tải được kết quả trong giới hạn")
            return raw
        finally:
            connection.close()

    def callback(self, body, authorization):
        token = body.get("token") or authorization.removeprefix("Bearer ")
        payload = verify(token, self.secret, "callback")
        key, status = payload.get("key"), payload.get("status")
        if type(status) is not int:
            raise ValueError("Thiếu trạng thái callback")
        request = payload.get("userdata", "") if status == 6 else ""
        if not isinstance(request, str) or len(request) > 128:
            raise ValueError("Mã callback không hợp lệ")
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    k: payload.get(k)
                    for k in ("key", "status", "userdata", "url", "users")
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        with self.kho.ket_noi() as db:
            committed = db.execute(
                "SELECT fingerprint FROM office_editor_callbacks WHERE key=? AND status=? AND request=?",
                (key, status, request),
            ).fetchone()
            if committed:
                if committed[0] != fingerprint:
                    raise LoiXungDotVanPhong("Callback cùng mã nhưng khác dữ liệu")
                return {"error": 0}
            session = self._row(db, key)
            if status == 6:
                member = db.execute(
                    "SELECT actor,role FROM office_editor_requests WHERE id=? AND key=?",
                    (payload.get("userdata"), key),
                ).fetchone()
            elif status == 2:
                users = payload.get("users", [])
                member = db.execute(
                    "SELECT actor,role FROM office_editor_members WHERE key=? AND actor=?",
                    (key, users[0] if isinstance(users, list) and users else ""),
                ).fetchone()
            else:
                member = {"actor": session["actor"], "role": session["role"]}
            if not member:
                raise PermissionError("Không xác định được người lưu phiên")
            actor = (self.scopes.actor(key,member['actor'],db) if self.scopes.units is not None
                     else {"id": member["actor"], "role": member["role"]})
            file = self.office._file(actor, session["file_id"], db, True)
            self.office._check_revision(file, session["revision"])
            if status == 6 and (
                not session["pending"] or payload.get("userdata") != session["pending"]
            ):
                raise LoiXungDotVanPhong("Snapshot không thuộc lệnh lưu hiện tại")
        if status in (2, 6):
            raw = self._fetch(payload.get("url", ""), key)
            checks = kiem_tep(file["name"], raw)
            scan = self.office.scanner.scan(raw)
            if scan["virus_state"] != "khong-phat-hien":
                raise ValueError("Kết quả chưa được quét")
            with self.kho.ket_noi() as db:
                db.execute("BEGIN IMMEDIATE")
                committed = db.execute(
                    "SELECT fingerprint FROM office_editor_callbacks WHERE key=? AND status=? AND request=?",
                    (key, status, request),
                ).fetchone()
                if committed:
                    if committed[0] != fingerprint:
                        raise LoiXungDotVanPhong("Callback cùng mã nhưng khác dữ liệu")
                    return {"error": 0}
                latest = self._row(db, key)
                current = self.office._file(actor, session["file_id"], db, True)
                self.office._check_revision(current, session["revision"])
                if (
                    latest["revision"] != session["revision"]
                    or latest["pending"] != session["pending"]
                ):
                    raise LoiXungDotVanPhong("Callback đã bị thay thế")
                if scan["sha256"] != session["sha256"]:
                    current["version"] += 1
                    self.office._version(db, current, actor, raw, scan)
                    current["revision"] += 1
                    db.execute(
                        "UPDATE office_files SET version=?,revision=?,updated=? WHERE id=?",
                        (
                            current["version"],
                            current["revision"],
                            time.time(),
                            current["id"],
                        ),
                    )
                    db.execute(
                        "UPDATE office_checks SET result=? WHERE file_id=? AND version=?",
                        (
                            json.dumps({**checks, **scan}),
                            current["id"],
                            current["version"],
                        ),
                    )
                db.execute(
                    "UPDATE office_editors SET revision=?,pending=NULL,last_saved=?,sha256=?,state=? WHERE key=?",
                    (
                        current["revision"],
                        time.time(),
                        hashlib.sha256(raw).hexdigest(),
                        "closed" if status == 2 else "active",
                        key,
                    ),
                )
                self.office._audit(db, actor, "office-editor-save", current["id"])
                db.execute(
                    "INSERT INTO office_editor_callbacks VALUES (?,?,?,?,?)",
                    (key, status, request, fingerprint, time.time()),
                )
        elif status == 7:
            with self.kho.ket_noi() as db:
                db.execute("BEGIN IMMEDIATE")
                latest = self._row(db, key)
                if latest["pending"] and payload.get("userdata") == latest["pending"]:
                    db.execute(
                        "UPDATE office_editors SET pending=NULL WHERE key=? AND pending=?",
                        (key, latest["pending"]),
                    )
                    db.execute(
                        "INSERT INTO office_editor_failures VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET request=excluded.request,created=excluded.created",
                        (key, latest["pending"], time.time()),
                    )
        elif status == 3:
            with self.kho.ket_noi() as db:
                db.execute(
                    "UPDATE office_editors SET state='error',pending=NULL WHERE key=?",
                    (key,),
                )
        elif status == 4:
            with self.kho.ket_noi() as db:
                db.execute(
                    "UPDATE office_editors SET state='closed',pending=NULL WHERE key=?",
                    (key,),
                )
        elif status != 1:
            raise ValueError("Trạng thái callback chưa hỗ trợ")
        return {"error": 0}
