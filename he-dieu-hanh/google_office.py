"""OAuth riêng từng người và bản sao Drive rõ ràng, không tự đồng bộ hai chiều.

Client secret và khóa AES-GCM nằm ngoài Git/web. Chỉ drive.file: các tệp ứng
dụng tạo hoặc người dùng đã cấp, không giả quyền đọc toàn bộ Google Drive.
"""

import base64
import hashlib
import http.client
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from kiem_tep_office import kiem_tep


class LoiKetNoiGoogle(ValueError):
    """Google từ chối hoặc gián đoạn, không công khai token/phản hồi thô."""

    def __init__(self, message, status=None, oauth_error=None):
        super().__init__(message)
        self.status = status
        self.oauth_error = oauth_error


SCOPE = "https://www.googleapis.com/auth/drive.file"
MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
NATIVE = {
    "application/vnd.google-apps." + kind: extension
    for kind, extension in (
        ("document", "docx"),
        ("spreadsheet", "xlsx"),
        ("presentation", "pptx"),
    )
}


class GoogleOffice:
    def __init__(self, office, origin):
        self.office, self.kho, self.origin = office, office.kho, origin
        self.redirect = origin + "/api/google/callback"
        self._lock = threading.Lock()
        self.config = None
        self.aes = None
        config_path = os.environ.get("BDSG_GOOGLE_CLIENT_FILE")
        key_path = os.environ.get("BDSG_GOOGLE_VAULT_KEY_FILE")
        if config_path and key_path:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM

                data = json.loads(Path(config_path).read_text())
                data = data.get("web", data)
                if (
                    not data.get("client_id", "").endswith(
                        ".apps.googleusercontent.com"
                    )
                    or not data.get("client_secret")
                    or self.redirect not in data.get("redirect_uris", [])
                ):
                    raise ValueError
                self.config = data
                self.aes = AESGCM(Path(key_path).read_bytes())
            except (ImportError, OSError, ValueError, KeyError):
                self.config = None
        with self.kho.ket_noi() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS google_office_tokens(
                    actor TEXT PRIMARY KEY,cipher BLOB NOT NULL,updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS google_office_states(
                    state TEXT PRIMARY KEY,actor TEXT NOT NULL,session TEXT NOT NULL,
                    binding TEXT NOT NULL,verifier TEXT NOT NULL,expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS google_office_exports(
                    actor TEXT NOT NULL,request TEXT NOT NULL,file_id TEXT NOT NULL,
                    version INTEGER NOT NULL,drive_id TEXT NOT NULL,state TEXT NOT NULL,
                    PRIMARY KEY(actor,request));
                CREATE TABLE IF NOT EXISTS google_office_imports(
                    actor TEXT NOT NULL,request TEXT NOT NULL,project_id TEXT NOT NULL,
                    drive_id TEXT NOT NULL,file_id TEXT NOT NULL,created REAL NOT NULL,
                    PRIMARY KEY(actor,request));
            """)

    @staticmethod
    def _hash(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def _require(self):
        if not self.config or not self.aes:
            raise LoiKetNoiGoogle("Chưa cấu hình OAuth Google")

    def _request(
        self,
        host,
        method,
        path,
        body=None,
        headers=None,
        limit=65536,
        include_headers=False,
    ):
        if host not in ("oauth2.googleapis.com", "www.googleapis.com"):
            raise LoiKetNoiGoogle("Nguồn Google không được phép")
        connection = http.client.HTTPSConnection(host, timeout=15)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            raw = response.read(limit + 1)
            if len(raw) > limit or response.status not in (200, 201, 204):
                oauth_error = None
                if host == "oauth2.googleapis.com" and path == "/token":
                    try:
                        code = json.loads(raw).get("error")
                        oauth_error = (
                            code
                            if code in ("invalid_grant", "invalid_client")
                            else None
                        )
                    except (ValueError, AttributeError):
                        pass
                raise LoiKetNoiGoogle(
                    "Không hoàn tất yêu cầu Google", response.status, oauth_error
                )
            return (raw, dict(response.getheaders())) if include_headers else raw
        except (OSError, http.client.HTTPException):
            raise LoiKetNoiGoogle("Kết nối Google bị gián đoạn") from None
        finally:
            connection.close()

    def _token_request(self, fields):
        self._require()
        raw = self._request(
            "oauth2.googleapis.com",
            "POST",
            "/token",
            urlencode(
                {
                    **fields,
                    "client_id": self.config["client_id"],
                    "client_secret": self.config["client_secret"],
                }
            ),
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = json.loads(raw)
        if fields.get("grant_type") == "refresh_token" and "scope" not in data:
            data["scope"] = SCOPE
        if (
            not isinstance(data.get("access_token"), str)
            or data.get("token_type", "").lower() != "bearer"
            or not isinstance(data.get("expires_in"), int)
            or not 60 <= data["expires_in"] <= 86400
        ):
            raise LoiKetNoiGoogle("Phản hồi OAuth không hợp lệ")
        if SCOPE not in data.get("scope", "").split():
            raise LoiKetNoiGoogle("Chưa cấp quyền Drive cho ứng dụng")
        data["expires_at"] = time.time() + data["expires_in"]
        return data

    def _store(self, actor, token, session_hash=None):
        self._require()
        nonce = secrets.token_bytes(12)
        cipher = nonce + self.aes.encrypt(
            nonce, json.dumps(token).encode(), actor.encode()
        )
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                actor != "chu-quan"
                and not db.execute(
                    "SELECT 1 FROM agents WHERE ma=? AND active=1 AND role='operator'",
                    (actor,),
                ).fetchone()
            ):
                raise LoiKetNoiGoogle("Danh tính đã bị thu hồi")
            if (
                session_hash
                and not db.execute(
                    "SELECT 1 FROM phien WHERE hash=? AND ma=? AND expires>?",
                    (session_hash, actor, time.time()),
                ).fetchone()
            ):
                raise LoiKetNoiGoogle("Phiên BDSG đã hết hiệu lực")
            db.execute(
                "INSERT INTO google_office_tokens VALUES (?,?,?) ON CONFLICT(actor) DO UPDATE SET cipher=excluded.cipher,updated=excluded.updated",
                (actor, cipher, time.time()),
            )

    def _load(self, actor):
        self._require()
        from cryptography.exceptions import InvalidTag

        with self.kho.ket_noi() as db:
            row = db.execute(
                "SELECT cipher FROM google_office_tokens WHERE actor=?", (actor,)
            ).fetchone()
        if not row:
            raise LoiKetNoiGoogle("Cần kết nối tài khoản Google")
        try:
            return json.loads(
                self.aes.decrypt(row[0][:12], row[0][12:], actor.encode())
            )
        except (InvalidTag, ValueError, TypeError, UnicodeError):
            raise LoiKetNoiGoogle("Không đọc được thông tin kết nối") from None

    def status(self, actor, args=None):
        if not self.config:
            return {
                "state": "chua-cau-hinh",
                "redirect_uri": self.redirect,
                "scope": SCOPE,
            }
        try:
            self._load(actor["id"])
            return {"state": "da-ket-noi", "scope": SCOPE}
        except LoiKetNoiGoogle:
            return {"state": "chua-ket-noi", "scope": SCOPE}

    def start(self, actor, session_token):
        self._require()
        state, binding, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        with self.kho.ket_noi() as db:
            db.execute(
                "DELETE FROM google_office_states WHERE expires<? OR actor=?",
                (time.time(), actor["id"]),
            )
            db.execute(
                "INSERT INTO google_office_states VALUES (?,?,?,?,?,?)",
                (
                    self._hash(state),
                    actor["id"],
                    self._hash(session_token),
                    self._hash(binding),
                    verifier,
                    time.time() + 600,
                ),
            )
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": self.config["client_id"],
                "redirect_uri": self.redirect,
                "response_type": "code",
                "scope": SCOPE,
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        ), binding

    def callback(self, query, binding):
        with self._lock:
            return self._callback(query, binding)

    def _callback(self, query, binding):
        self._require()
        state, code = query.get("state", [""])[0], query.get("code", [""])[0]
        if len(state) > 200 or len(code) > 4096 or not state or not binding:
            raise LoiKetNoiGoogle("Phiên cấp quyền không hợp lệ")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM google_office_states WHERE state=?", (self._hash(state),)
            ).fetchone()
            if (
                not row
                or row["expires"] < time.time()
                or not secrets.compare_digest(row["binding"], self._hash(binding))
                or not db.execute(
                    "SELECT 1 FROM phien WHERE hash=? AND ma=? AND expires>?",
                    (row["session"], row["actor"], time.time()),
                ).fetchone()
            ):
                raise LoiKetNoiGoogle("Phiên cấp quyền đã hết hiệu lực")
            db.execute(
                "DELETE FROM google_office_states WHERE state=?", (self._hash(state),)
            )
        if not code or query.get("error"):
            raise LoiKetNoiGoogle("Người dùng chưa cấp quyền")
        token = self._token_request(
            {
                "code": code,
                "redirect_uri": self.redirect,
                "grant_type": "authorization_code",
                "code_verifier": row["verifier"],
            }
        )
        if not token.get("refresh_token"):
            raise LoiKetNoiGoogle("Cần cấp quyền ngoại tuyến để giữ kết nối")
        # Đăng xuất hoặc thu hồi trong lúc trao đổi code không được giữ kết nối mới.
        with self.kho.ket_noi() as db:
            if not db.execute(
                "SELECT 1 FROM phien WHERE hash=? AND ma=? AND expires>?",
                (row["session"], row["actor"], time.time()),
            ).fetchone():
                raise LoiKetNoiGoogle("Phiên BDSG đã hết hiệu lực")
        self._store(row["actor"], token, session_hash=row["session"])

    def _access(self, actor):
        with self._lock:
            token = self._load(actor["id"])
            if token.get("expires_at", 0) <= time.time() + 60:
                try:
                    updated = self._token_request(
                        {
                            "grant_type": "refresh_token",
                            "refresh_token": token["refresh_token"],
                        }
                    )
                except LoiKetNoiGoogle as error:
                    if error.oauth_error == "invalid_grant":
                        with self.kho.ket_noi() as db:
                            db.execute(
                                "DELETE FROM google_office_tokens WHERE actor=?",
                                (actor["id"],),
                            )
                    raise
                token = {**token, **updated}
                self._store(actor["id"], token)
            return {"Authorization": "Bearer " + token["access_token"]}

    def disconnect(self, actor, args=None):
        with self._lock:
            return self._disconnect(actor)

    def _disconnect(self, actor):
        token = self._load(actor["id"])
        self._request(
            "oauth2.googleapis.com",
            "POST",
            "/revoke",
            urlencode({"token": token.get("refresh_token", token["access_token"])}),
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        with self.kho.ket_noi() as db:
            db.execute("DELETE FROM google_office_tokens WHERE actor=?", (actor["id"],))
            db.execute("DELETE FROM google_office_states WHERE actor=?", (actor["id"],))
        return {"state": "da-ngat-ket-noi"}

    def forget(self, identity):
        with self._lock, self.kho.ket_noi() as db:
            db.execute("DELETE FROM google_office_tokens WHERE actor=?", (identity,))
            db.execute("DELETE FROM google_office_states WHERE actor=?", (identity,))

    def picker(self, actor):
        self._require()
        if (
            not self.config.get("picker_api_key")
            or not str(self.config.get("project_number", "")).isdigit()
        ):
            raise LoiKetNoiGoogle("Chưa cấu hình Google Picker")
        return {
            "access_token": self._access(actor)["Authorization"][7:],
            "api_key": self.config["picker_api_key"],
            "app_id": str(self.config["project_number"]),
        }

    @staticmethod
    def _id(value):
        if not isinstance(value, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{10,200}", value
        ):
            raise ValueError("Mã tệp Google không hợp lệ")
        return value

    def list(self, actor, args=None):
        query = urlencode(
            {
                "pageSize": 50,
                "q": "trashed=false",
                "orderBy": "modifiedTime desc",
                "fields": "files(id,name,mimeType,size),nextPageToken",
            }
        )
        data = json.loads(
            self._request(
                "www.googleapis.com",
                "GET",
                "/drive/v3/files?" + query,
                headers=self._access(actor),
            )
        )
        return {
            "files": data.get("files", []),
            "limited": bool(data.get("nextPageToken")),
            "scope": "chi-tep-da-cap-cho-ung-dung",
        }

    def import_file(self, actor, args):
        pid = args.get("project_id")
        request = args.get("request_key")
        if not isinstance(request, str) or not re.fullmatch(
            r"[a-f0-9-]{32,64}", request
        ):
            raise ValueError("Thiếu mã thao tác nhập")
        identifier = self._id(args.get("drive_id"))
        with self.kho.ket_noi() as db:
            self.office._project(actor, pid, db, True)
            existing = self._import_result(db, actor, request, pid, identifier)
            if existing:
                return existing
        headers = self._access(actor)
        meta = json.loads(
            self._request(
                "www.googleapis.com",
                "GET",
                "/drive/v3/files/"
                + identifier
                + "?fields=id,name,mimeType,size,trashed",
                headers=headers,
            )
        )
        if meta.get("trashed") or int(meta.get("size", 0)) > self.office.MAX_FILE_BYTES:
            raise ValueError("Tệp không tồn tại hoặc vượt giới hạn")
        extension = NATIVE.get(meta.get("mimeType"))
        name = meta["name"]
        if extension:
            name = (
                name
                if name.lower().endswith("." + extension)
                else name + "." + extension
            )
            path = (
                "/drive/v3/files/"
                + identifier
                + "/export?"
                + urlencode({"mimeType": MIME[extension]})
            )
        else:
            path = "/drive/v3/files/" + identifier + "?alt=media"
        name = self.office._name(name)
        raw = self._request(
            "www.googleapis.com",
            "GET",
            path,
            headers=headers,
            limit=self.office.MAX_FILE_BYTES,
        )
        kiem_tep(name, raw)
        scan = self.office.scanner.scan(raw)
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            self.office._project(actor, pid, db, True)
            existing = self._import_result(db, actor, request, pid, identifier)
            if existing:
                return existing
            file = self.office._create_file(db, actor, pid, name, raw, scan)
            db.execute(
                "INSERT INTO google_office_imports VALUES (?,?,?,?,?,?)",
                (actor["id"], request, pid, identifier, file["id"], time.time()),
            )
        return {"file": file, "state": "da-nhap-ban-sao"}

    def _import_result(self, db, actor, request, pid, identifier):
        existing = db.execute(
            "SELECT * FROM google_office_imports WHERE actor=? AND request=?",
            (actor["id"], request),
        ).fetchone()
        if existing:
            if existing["project_id"] != pid or existing["drive_id"] != identifier:
                raise ValueError("Mã nhập đã gắn với thao tác khác")
            file = self.office._file(actor, existing["file_id"], db)
            return {"file": self.office._metadata(file), "state": "da-nhap-ban-sao"}
        return None

    def export_file(self, actor, args):
        request = args.get("request_key")
        if not isinstance(request, str) or not re.fullmatch(
            r"[a-f0-9-]{32,64}", request
        ):
            raise ValueError("Thiếu mã thao tác xuất")
        with self.kho.ket_noi() as db:
            file = self.office._file(actor, args.get("id"), db)
            raw = db.execute(
                "SELECT content FROM office_versions WHERE file_id=? AND version=?",
                (file["id"], file["version"]),
            ).fetchone()[0]
            if db.execute(
                "SELECT 1 FROM office_editors WHERE file_id=? AND state='active' AND expires>?",
                (file["id"], time.time()),
            ).fetchone():
                raise LoiKetNoiGoogle(
                    "Đóng bộ soạn thảo và chờ lưu xong trước khi xuất"
                )
        scan = self.office.scanner.scan(raw)
        if scan["virus_state"] != "khong-phat-hien":
            raise LoiKetNoiGoogle("Tệp chưa được quét virus")
        headers = self._access(actor)
        with self.kho.ket_noi() as db:
            old = db.execute(
                "SELECT * FROM google_office_exports WHERE actor=? AND request=?",
                (actor["id"], request),
            ).fetchone()
            if not old:
                old = db.execute(
                    "SELECT * FROM google_office_exports WHERE actor=? AND file_id=? AND version=? AND state='pending'",
                    (actor["id"], file["id"], file["version"]),
                ).fetchone()
        if old:
            if old["file_id"] != file["id"] or old["version"] != file["version"]:
                raise ValueError("Mã xuất đã gắn với phiên bản khác")
            identifier = old["drive_id"]
            request = old["request"]
            if old["state"] == "complete":
                return {"drive_id": identifier, "state": "da-xuat-ban-sao"}
            try:
                remote = json.loads(
                    self._request(
                        "www.googleapis.com",
                        "GET",
                        "/drive/v3/files/" + identifier + "?fields=id,size,md5Checksum",
                        headers=headers,
                    )
                )
                if (
                    int(remote.get("size", -1)) != len(raw)
                    or remote.get("md5Checksum")
                    != hashlib.md5(raw, usedforsecurity=False).hexdigest()
                ):
                    raise LoiKetNoiGoogle(
                        "Bản sao trên Drive không khớp thao tác trước"
                    )
                with self.kho.ket_noi() as db:
                    db.execute(
                        "UPDATE google_office_exports SET state='complete' WHERE actor=? AND request=?",
                        (actor["id"], request),
                    )
                return {"drive_id": identifier, "state": "da-xuat-ban-sao"}
            except LoiKetNoiGoogle as error:
                if error.status != 404:
                    raise
        else:
            generated = json.loads(
                self._request(
                    "www.googleapis.com",
                    "GET",
                    "/drive/v3/files/generateIds?count=1&space=drive&type=files",
                    headers=headers,
                )
            )
            identifier = self._id(generated["ids"][0])
            with self.kho.ket_noi() as db:
                self.office._file(actor, file["id"], db)
                db.execute(
                    "INSERT INTO google_office_exports VALUES (?,?,?,?,?,'pending')",
                    (actor["id"], request, file["id"], file["version"], identifier),
                )
        mime = MIME.get(
            file["name"].rsplit(".", 1)[-1].lower(), "application/octet-stream"
        )
        metadata = json.dumps(
            {"id": identifier, "name": file["name"], "mimeType": mime}
        )
        if len(raw) > 5 * 1024 * 1024:
            _, response_headers = self._request(
                "www.googleapis.com",
                "POST",
                "/upload/drive/v3/files?uploadType=resumable&fields=id",
                metadata.encode(),
                {
                    **headers,
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": mime,
                    "X-Upload-Content-Length": str(len(raw)),
                },
                include_headers=True,
            )
            location = next(
                (v for k, v in response_headers.items() if k.lower() == "location"), ""
            )
            url = urlsplit(location)
            query = parse_qs(url.query)
            if (
                url.scheme != "https"
                or url.netloc != "www.googleapis.com"
                or url.path != "/upload/drive/v3/files"
                or url.fragment
                or query.get("uploadType") != ["resumable"]
                or not query.get("upload_id")
            ):
                raise LoiKetNoiGoogle("Nguồn phiên tải Google không hợp lệ")
            self._request(
                "www.googleapis.com",
                "PUT",
                url.path + "?" + url.query,
                raw,
                {**headers, "Content-Type": mime, "Content-Length": str(len(raw))},
            )
            with self.kho.ket_noi() as db:
                db.execute(
                    "UPDATE google_office_exports SET state='complete' WHERE actor=? AND request=?",
                    (actor["id"], request),
                )
            return {"drive_id": identifier, "state": "da-xuat-ban-sao"}
        boundary = "bdsg" + secrets.token_hex(16)
        body = (
            (
                "--"
                + boundary
                + "\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                + metadata
                + "\r\n--"
                + boundary
                + "\r\nContent-Type: "
                + mime
                + "\r\n\r\n"
            ).encode()
            + raw
            + ("\r\n--" + boundary + "--\r\n").encode()
        )
        self._request(
            "www.googleapis.com",
            "POST",
            "/upload/drive/v3/files?uploadType=multipart&fields=id",
            body,
            {**headers, "Content-Type": "multipart/related; boundary=" + boundary},
        )
        with self.kho.ket_noi() as db:
            db.execute(
                "UPDATE google_office_exports SET state='complete' WHERE actor=? AND request=?",
                (actor["id"], request),
            )
        return {"drive_id": identifier, "state": "da-xuat-ban-sao"}
