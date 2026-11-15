"""Lưu dữ liệu vận hành riêng; không để CSDL hoặc chứng thư trong thư mục web."""

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from quyen_office import khoa_phien, ngat_phien

MA = re.compile(r"[a-z][a-z0-9_-]{2,63}\Z")


def bam(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Kho:
    def __init__(self, thu_muc):
        self.root = Path(thu_muc)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = self.root / "van-hanh.db"
        with self.ket_noi() as c:
            c.executescript("""
              CREATE TABLE IF NOT EXISTS chu(ma TEXT PRIMARY KEY, salt TEXT, hash TEXT);
              CREATE TABLE IF NOT EXISTS phien(hash TEXT PRIMARY KEY, ma TEXT, expires REAL);
              CREATE TABLE IF NOT EXISTS agents(ma TEXT PRIMARY KEY, ten TEXT, role TEXT, token_hash TEXT UNIQUE, active INTEGER DEFAULT 1);
              CREATE TABLE IF NOT EXISTS tin(id TEXT PRIMARY KEY, sender TEXT, recipient TEXT, body TEXT, created REAL);
              CREATE INDEX IF NOT EXISTS tin_nguoi_nhan ON tin(recipient,created);
              CREATE TABLE IF NOT EXISTS yeu_cau(id TEXT PRIMARY KEY, owner TEXT, title TEXT, sector TEXT, description TEXT, stage TEXT, created REAL);
              CREATE TABLE IF NOT EXISTS su_kien(id INTEGER PRIMARY KEY, actor TEXT, action TEXT, target TEXT, created REAL);
              CREATE TABLE IF NOT EXISTS thu_dang_nhap(ip TEXT, created REAL);
              CREATE INDEX IF NOT EXISTS thu_dang_nhap_ip ON thu_dang_nhap(ip,created);
              CREATE TABLE IF NOT EXISTS web_users(ma TEXT PRIMARY KEY,salt TEXT,hash TEXT);
            """)
        os.chmod(self.db, 0o600)

    @contextmanager
    def ket_noi(self):
        c = sqlite3.connect(str(self.db), timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def tao_chu(self, password):
        salt = secrets.token_hex(16)
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
        with self.ket_noi() as c:
            if c.execute("SELECT 1 FROM chu").fetchone():
                raise ValueError("Đã có chủ quản; không ghi đè thông tin đăng nhập")
            c.execute("INSERT INTO chu VALUES (?,?,?)", ("chu-quan", salt, digest))

    def dang_nhap(self, username, password, ip):
        now = time.time()
        with self.ket_noi() as c:
            c.execute("DELETE FROM thu_dang_nhap WHERE created<?", (now - 600,))
            count = c.execute(
                "SELECT count(*) FROM thu_dang_nhap WHERE ip=? AND created>?",
                (ip, now - 300),
            ).fetchone()[0]
            total = c.execute("SELECT count(*) FROM thu_dang_nhap").fetchone()[0]
            if count >= 8 or total >= 100:
                return None, "tam-khoa"
            c.execute("INSERT INTO thu_dang_nhap VALUES (?,?)", (ip, now))
            user = c.execute("SELECT * FROM chu WHERE ma=?", (username,)).fetchone()
            if not user:
                user = c.execute(
                    "SELECT w.* FROM web_users w JOIN agents a ON a.ma=w.ma WHERE w.ma=? AND a.active=1 AND a.role='operator'",
                    (username,),
                ).fetchone()
            salt = user["salt"] if user else "00" * 16
            digest = hashlib.scrypt(
                password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
            ).hex()
            if not user or not hmac.compare_digest(digest, user["hash"]):
                return None, "sai-thong-tin"
            token = secrets.token_urlsafe(36)
            c.execute("DELETE FROM phien WHERE expires<?", (now,))
            c.execute(
                "INSERT INTO phien VALUES (?,?,?)",
                (bam(token), username, now + 8 * 3600),
            )
            c.execute("DELETE FROM thu_dang_nhap WHERE ip=?", (ip,))
            return token, "ok"

    def tu_phien(self, token):
        with self.ket_noi() as c:
            row = c.execute(
                "SELECT ma FROM phien WHERE hash=? AND expires>?",
                (bam(token), time.time()),
            ).fetchone()
        if not row:
            return None
        if row["ma"] == "chu-quan":
            return {"id": row["ma"], "role": "quan-tri", "name": "Chủ quản Thanh Hoá"}
        with self.ket_noi() as c:
            person = c.execute(
                "SELECT ma,ten,role FROM agents WHERE ma=? AND active=1 AND role='operator'",
                (row["ma"],),
            ).fetchone()
        return (
            {"id": person["ma"], "name": person["ten"], "role": person["role"]}
            if person
            else None
        )

    def tao_nguoi_dung(self, actor, args):
        if actor.get("role") != "quan-tri":
            raise PermissionError("Chỉ chủ quản tạo người dùng")
        identifier, name, password = (
            args.get("id"),
            args.get("name"),
            args.get("password"),
        )
        if (
            not isinstance(identifier, str)
            or not MA.fullmatch(identifier)
            or identifier == "chu-quan"
            or not isinstance(name, str)
            or not 1 <= len(name) <= 100
            or not isinstance(password, str)
            or not 16 <= len(password) <= 256
        ):
            raise ValueError("Cần mã người dùng, tên và mật khẩu 16–256 ký tự")
        salt = secrets.token_hex(16)
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
        with self.ket_noi() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM agents WHERE ma=?", (identifier,)).fetchone():
                raise ValueError("Danh tính đã tồn tại")
            c.execute(
                "INSERT INTO agents(ma,ten,role,token_hash) VALUES (?,?,?,?)",
                (identifier, name, "operator", bam(secrets.token_urlsafe(40))),
            )
            c.execute(
                "INSERT INTO web_users VALUES (?,?,?)", (identifier, salt, digest)
            )
        self.su_kien(actor["id"], "tao-nguoi-dung", identifier)
        return {"id": identifier, "name": name, "role": "operator"}

    def dang_xuat(self, token):
        with self.ket_noi() as c:
            c.execute("DELETE FROM phien WHERE hash=?", (bam(token),))

    def tao_agent(self, ma, ten, role="agent"):
        if (
            not MA.fullmatch(ma)
            or role not in ("agent", "operator")
            or not 1 <= len(ten) <= 100
        ):
            raise ValueError("Thông tin agent không hợp lệ")
        token = secrets.token_urlsafe(40)
        with self.ket_noi() as c:
            c.execute(
                "INSERT INTO agents(ma,ten,role,token_hash) VALUES (?,?,?,?)",
                (ma, ten, role, bam(token)),
            )
        return token

    def thu_hoi_agent(self, ma):
        with self.ket_noi() as c:
            c.execute("UPDATE agents SET active=0 WHERE ma=?", (ma,))
            keys = khoa_phien(c, identity=ma)
            if c.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='google_office_tokens'"
            ).fetchone():
                c.execute("DELETE FROM google_office_tokens WHERE actor=?", (ma,))
        ngat_phien(keys)

    def tu_token(self, token):
        with self.ket_noi() as c:
            row = c.execute(
                "SELECT ma,ten,role FROM agents WHERE token_hash=? AND active=1",
                (bam(token),),
            ).fetchone()
        return (
            {"id": row["ma"], "name": row["ten"], "role": row["role"]} if row else None
        )

    def agents(self):
        with self.ket_noi() as c:
            return [
                dict(r)
                for r in c.execute(
                    "SELECT ma AS id,ten AS name,role,active FROM agents ORDER BY ma"
                )
            ]

    def su_kien(self, actor, action, target=""):
        with self.ket_noi() as c:
            c.execute(
                "INSERT INTO su_kien(actor,action,target,created) VALUES (?,?,?,?)",
                (actor, action, target, time.time()),
            )

    def gui(self, sender, recipient, body):
        if not isinstance(body, str) or not 1 <= len(body.strip()) <= 4000:
            raise ValueError("Thông điệp cần từ 1 đến 4000 ký tự")
        with self.ket_noi() as c:
            if (
                recipient != "chu-quan"
                and not c.execute(
                    "SELECT 1 FROM agents WHERE ma=? AND active=1", (recipient,)
                ).fetchone()
            ):
                raise ValueError("Agent nhận không tồn tại hoặc đã bị thu hồi")
            ma = secrets.token_hex(12)
            c.execute(
                "INSERT INTO tin VALUES (?,?,?,?,?)",
                (ma, sender, recipient, body.strip(), time.time()),
            )
        self.su_kien(sender, "gui-thong-diep", recipient)
        return {"id": ma, "status": "da-giao-hop-thu", "recipient": recipient}

    def hop_thu(self, identity, peer=None):
        with self.ket_noi() as c:
            params = [identity, identity]
            sql = "SELECT * FROM tin WHERE (sender=? OR recipient=?)"
            if peer:
                sql += " AND (sender=? OR recipient=?)"
                params.extend([peer, peer])
            sql += " ORDER BY created DESC LIMIT 100"
            return list(reversed([dict(r) for r in c.execute(sql, params)]))

    def tao_yeu_cau(self, owner, args):
        title = args.get("title", "")
        sector = args.get("sector", "")
        description = args.get("description", "")
        if not isinstance(title, str) or not 3 <= len(title.strip()) <= 160:
            raise ValueError("Tên yêu cầu cần từ 3 đến 160 ký tự")
        if (
            not isinstance(description, str)
            or not 10 <= len(description.strip()) <= 4000
        ):
            raise ValueError("Mô tả cần từ 10 đến 4000 ký tự")
        if sector not in (
            "bat-dong-san",
            "thuong-mai",
            "van-hanh",
            "cong-nghe",
            "nong-nghiep",
            "tri-thuc",
        ):
            raise ValueError("Lĩnh vực không hợp lệ")
        ma = secrets.token_hex(8)
        with self.ket_noi() as c:
            c.execute(
                "INSERT INTO yeu_cau VALUES (?,?,?,?,?,?,?)",
                (
                    ma,
                    owner,
                    title.strip(),
                    sector,
                    description.strip(),
                    "tu-van",
                    time.time(),
                ),
            )
        self.su_kien(owner, "tao-yeu-cau", ma)
        return {"id": ma, "stage": "tu-van"}

    def yeu_cau(self, owner, admin=False):
        with self.ket_noi() as c:
            if admin:
                rows = c.execute(
                    "SELECT * FROM yeu_cau ORDER BY created DESC LIMIT 200"
                )
            else:
                rows = c.execute(
                    "SELECT * FROM yeu_cau WHERE owner=? ORDER BY created DESC LIMIT 200",
                    (owner,),
                )
            return [dict(r) for r in rows]

    def doi_chang(self, identity, ma, stage, admin=False):
        if stage not in ("tu-van", "trien-khai", "van-hanh", "kinh-doanh"):
            raise ValueError("Chặng không hợp lệ")
        with self.ket_noi() as c:
            sql = "UPDATE yeu_cau SET stage=? WHERE id=?" + (
                "" if admin else " AND owner=?"
            )
            params = (stage, ma) if admin else (stage, ma, identity)
            if c.execute(sql, params).rowcount != 1:
                raise ValueError("Không tìm thấy yêu cầu trong phạm vi quyền")
        self.su_kien(identity, "doi-chang", ma)
        return {"id": ma, "stage": stage}

    def hoat_dong(self, identity, admin=False):
        with self.ket_noi() as c:
            sql = "SELECT actor,action,target,created FROM su_kien"
            params = () if admin else (identity,)
            if not admin:
                sql += " WHERE actor=?"
            return [
                dict(r)
                for r in c.execute(sql + " ORDER BY created DESC LIMIT 60", params)
            ]
