#!/usr/bin/env python3
"""Cổng HTTP cùng nguồn: phiên web và MCP Bearer tách biệt, chỉ nghe loopback."""

import argparse
import json
import os
import secrets
import sys
import signal
import sqlite3
import threading
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, quote

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))
from kho import Kho
from dieu_phoi import DieuPhoi
from cong_viec import CongViec
from cau_hinh_mo_hinh import CauHinhMoHinh
from trung_tam_ai import TrungTamAI
from cau_hinh_ket_noi import CauHinhKetNoi
from du_an import DuAn
from tai_lieu import TaiLieu
from van_phong import VanPhong
from soan_thao_office import SoanThaoOffice
from google_office import GoogleOffice, LoiKetNoiGoogle
from dang_nhap_google import DangNhapGoogle, LoiDangNhapGoogle
from runtime_tac_vu import RuntimeTacVu
from trinh_duyet import TrinhDuyet, revoke_browser
from hanh_dong import HanhDong, active_actor
from lich_cong_viec import LichCongViec
from phoi_hop import PhoiHop
from ho_tro_khach import HoTroKhach, QuaHanHoTro
from ket_noi_chatgpt import KetNoiChatGPT
from van_hanh_may_chu import VanHanhMayChu, MayChuCoGioiHan
from thiet_bi_may_chu import ThietBiMayChu
from kiem_tra_khoi_phuc import read_status
from tinh_trang_offsite import read_offsite_status
from phien_web import PhienWeb
from tich_hop_viet_nam import TichHopVietNam
from vn_dong_bo import DongBoVietNam


class UngDung:
    def __init__(self, data, origin, ghi=False, catalogue=None, connections=None):
        self.origin = origin.rstrip("/")
        self.catalogue = (
            catalogue
            or json.loads(
                (GOC / "nen-tang/danh-muc.json").read_text(encoding="utf-8-sig")
            )["products"]
        )
        self.kho = Kho(data)
        self.web_sessions = PhienWeb(self.kho)
        self.node = ThietBiMayChu(self.kho.root, node_id=os.environ.get("BDSG_NODE_ID"))
        self.customer_support = HoTroKhach(self.catalogue)
        self.chatgpt_connection = KetNoiChatGPT(self.kho)
        self.core = DieuPhoi(self.kho, self.catalogue, ghi, connections)

        def verify(actor):
            try:
                return active_actor(self.kho, actor["id"])["role"] == actor["role"]
            except (ValueError, PermissionError, KeyError, TypeError):
                return False

        self.core.verify_actor = verify
        self.tasks = CongViec(self.kho, self.core)
        self.projects = DuAn(self.kho)
        self.tasks.projects = self.projects
        self.documents = TaiLieu(self.kho, self.projects)
        self.office = VanPhong(self.kho, self.projects)
        self.office_editor = SoanThaoOffice(self.office, self.origin)
        self.google_office = GoogleOffice(self.office, self.origin)
        self.google_login = DangNhapGoogle(self.kho, self.origin)
        self.vn_integrations = TichHopVietNam(self.kho)
        self.vn_sync = DongBoVietNam(self.vn_integrations)
        self.office.editor_status = self.office_editor.status
        self.tasks.documents = self.documents
        self.runtime = RuntimeTacVu(self.kho, self.tasks)
        self.browser = TrinhDuyet(self.kho, self.tasks)
        self.tasks.on_cancel = lambda owner, task_id: revoke_browser(owner, task_id)

        def revoke(identity):
            self.tasks.cancel_owner(identity)
            revoke_browser(identity)
            self.google_office.forget(identity)

        self.core.on_revoke = revoke
        self.actions = HanhDong(self.kho, self.core, self.tasks,self.browser)
        self.schedules = LichCongViec(self.kho, self.core, self.tasks)
        self.delegation = PhoiHop(self.kho, self.core, self.tasks)
        self.model_settings = CauHinhMoHinh(self.kho, self.tasks)
        self.ai = TrungTamAI(self.kho)
        self.tasks.ai = self.ai
        if self.ai.path.exists():
            self.tasks.model = self.ai
        self.connectors = CauHinhKetNoi(
            self.kho, self.core.connections, self.catalogue, self.origin
        )
        self.core.dang_ky_cong_viec(
            self.tasks,
            self.model_settings.save,
            self.connectors,
            self.model_settings.disable,
            self.projects,
        )
        self.core.dang_ky_mo_rong(self)
        self.operations = VanHanhMayChu(self)

    def node_report(self, actor):
        if not actor or actor.get("role") != "quan-tri":
            raise PermissionError("Chỉ chủ quản xem máy chủ")
        return {"node": self.node.snapshot(), "operations": self.operations.report(),
                "recovery": read_status(os.environ.get("BDSG_RECOVERY_STATUS_FILE")),
                "offsite": read_offsite_status(os.environ.get("BDSG_OFFSITE_STATUS_FILE"))}

    def configure_ai(self, actor, args):
        # Giữ cùng khóa với tạo/tiếp tục tác vụ để đổi nhà cung cấp không cắt lượt đang chạy.
        with self.tasks.lock:
            with self.kho.ket_noi() as db:
                active = db.execute("SELECT count(*) FROM cong_viec_tasks WHERE status IN ('queued','running','cancelling') OR json_extract(document,'$.runtime_running')=1").fetchone()[0]
            if active:
                raise ValueError("Đợi công việc đang chạy kết thúc trước khi đổi cấu hình AI")
            result = self.ai.save(actor,args)
            self.tasks.model = self.ai
            return result

    def catalog(self):
        p = self.kho.root / "web-status.json"
        checks = (
            json.loads(p.read_text())
            if p.is_file()
            else {"checked_at": None, "checks": {}}
        )
        connections = {
            c["platform_id"]: {"state": c["state"], "checked_at": c.get("checked_at")}
            for c in self.core.connections.tom_tat()
        }
        return {
            "products": [
                {
                    **p,
                    "web": checks["checks"].get(p["id"], {"state": "chua-do"}),
                    "mcp": connections.get(p["id"], {"state": "chua-cau-hinh"}),
                }
                for p in self.catalogue
            ],
            "checked_at": checks["checked_at"],
            "mcp_endpoint": self.origin + "/mcp",
        }


def tao_may_chu(app, port=8766):
    class XuLy(BaseHTTPRequestHandler):
        server_version = "BDSG"
        sys_version = ""

        def log_message(self, *_):
            pass

        def send(self, status, payload=None, cookie=None, headers=None):
            data = (
                json.dumps(payload, ensure_ascii=False).encode()
                if payload is not None
                else b""
            )
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if cookie:
                for item in cookie if isinstance(cookie, list) else [cookie]:
                    self.send_header("Set-Cookie", item)
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def origin_ok(self, required=False):
            origin = self.headers.get("Origin")
            return origin == app.origin or (not origin and not required)

        def session(self):
            try:
                c = SimpleCookie(self.headers.get("Cookie", ""))
                return c["bdsg_session"].value if "bdsg_session" in c else ""
            except CookieError:
                return ""

        def actor(self, mcp=False):
            if mcp:
                h = self.headers.get("Authorization", "")
                return (
                    app.kho.tu_token(h[7:])
                    if h.startswith("Bearer ") and len(h) < 512
                    else None
                )
            return app.kho.tu_phien(self.session())

        def cookie_actor_matches(self, actor):
            expected = self.headers.get("X-BDSG-Actor")
            # Cookie dùng chung giữa các tab; biểu mẫu cũ không được chạy dưới tài khoản mới.
            if actor and expected is not None and expected != actor["id"]:
                self.send(409, {
                    "error": "Danh tính phiên đã thay đổi. Hãy tải lại không gian.",
                    "code": "identity_changed",
                })
                return False
            return True

        def client_hint(self):
            agent = self.headers.get("User-Agent", "")[:512].lower()
            for words, hint in ((("iphone", "ipad"), "iPhone/iPad"),
                                (("android",), "Android"), (("windows",), "Windows"),
                                (("macintosh", "mac os"), "macOS"), (("linux",), "Linux")):
                if any(word in agent for word in words):
                    return hint
            return "Chưa xác định"

        def sessions_response(self, action, body=None):
            actor = self.actor()
            if not actor:
                return self.send(401, {"error": "Cần đăng nhập"})
            token = self.session()
            try:
                if action == "list":
                    app.web_sessions.touch(actor, token, self.client_hint())
                    return self.send(200, app.web_sessions.list(actor, token))
                expected = {"rename": {"id", "label"}, "revoke": {"id"}, "revoke-others": set()}
                if action not in expected or not isinstance(body, dict) or set(body) != expected[action]:
                    return self.send(400, {"error": "Yêu cầu quản lý phiên không hợp lệ"})
                if action == "rename":
                    result = app.web_sessions.rename(actor, token, body["id"], body["label"])
                elif action == "revoke":
                    result = app.web_sessions.revoke(actor, token, body["id"])
                else:
                    result = app.web_sessions.revoke_others(actor, token)
                return self.send(200, result)
            except LookupError:
                return self.send(404, {"error": "Không tìm thấy phiên"})
            except PermissionError:
                return self.send(403, {"error": "Phiên không còn hiệu lực; hãy đăng nhập lại"})
            except ValueError as error:
                return self.send(400, {"error": str(error)})
            except sqlite3.Error:
                return self.send(503, {"error": "Chưa đọc được phiên đăng nhập; hãy thử lại"})

        def body(self):
            if (
                self.headers.get("Transfer-Encoding")
                or self.headers.get_content_type() != "application/json"
            ):
                raise ValueError("Cần nội dung JSON với Content-Length")
            length = int(self.headers.get("Content-Length", "0"))
            limit = {"/api/tools": 65536, "/api/upload": 1500000}.get(
                urlsplit(self.path).path, 16384
            )
            if not 0 < length <= limit:
                raise ValueError("Yêu cầu vượt giới hạn hoặc thiếu nội dung")
            obj = json.loads(self.rfile.read(length))
            if not isinstance(obj, dict):
                raise ValueError("Nội dung phải là đối tượng JSON")
            return obj

        def do_GET(self):
            self.connection.settimeout(12)
            if not self.origin_ok():
                return self.send(403, {"error": "Nguồn truy cập không được phép"})
            path = urlsplit(self.path).path
            public_paths = {
                "/api/auth/google", "/api/ready", "/api/google/callback",
                "/api/office-source", "/mcp", "/api/catalogue",
                "/api/customer-agents", "/api/customer-agent", "/api/modules",
                "/api/model", "/api/suc-khoe", "/api/me",
            }
            if path not in public_paths and not self.cookie_actor_matches(self.actor()):
                return
            if path == '/api/auth/google':
                return self.send(200, app.google_login.status())
            if path == "/api/ready":
                state = app.operations.readiness()
                return self.send(200 if state["status"] == "ready" else 503,
                                 {"status": state["status"]})
            if path == "/api/sessions":
                return self.sessions_response("list")
            if path in ("/api/system", "/api/node"):
                actor = self.actor()
                if not actor:
                    return self.send(401, {"error": "Cần đăng nhập"})
                if actor["role"] != "quan-tri":
                    return self.send(403, {"error": "Chỉ chủ quản xem vận hành"})
                return self.send(200, app.node_report(actor) if path == "/api/node"
                                 else app.operations.report())
            if app.operations.draining.is_set() and path != "/api/suc-khoe":
                return self.send(503, {"error": "Đang dừng dịch vụ; thử lại sau"}, headers={"Retry-After": "5"})
            if path == "/api/google/callback":
                query = parse_qs(urlsplit(self.path).query)
                if any(value.startswith('login.') for value in query.get('state', [])):
                    cookies = ['bdsg_google_login=; Path=/api/google/callback; Secure; HttpOnly; SameSite=Lax; Max-Age=0']
                    target = '/?login=google-failed#work'
                    try:
                        cookie = SimpleCookie(self.headers.get('Cookie', ''))
                        token = app.google_login.callback(query, cookie['bdsg_google_login'].value if 'bdsg_google_login' in cookie else '')
                        cookies.append('bdsg_session=' + token + '; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=28800')
                        target = '/?login=google-success#work'
                    except (CookieError, ValueError, PermissionError, OSError):
                        pass
                    return self.send(303, cookie=cookies, headers={'Location':target,'Referrer-Policy':'no-referrer'})
                try:
                    cookie = SimpleCookie(self.headers.get("Cookie", ""))
                    app.google_office.callback(parse_qs(urlsplit(self.path).query),
                                               cookie["bdsg_google"].value if "bdsg_google" in cookie else "")
                    target = "/?google=connected#office"
                except (CookieError, ValueError, PermissionError, OSError):
                    target = "/?google=failed#office"
                return self.send(303, cookie="bdsg_google=; Path=/api/google/callback; Secure; HttpOnly; SameSite=Lax; Max-Age=0",
                                 headers={"Location": target, "Referrer-Policy": "no-referrer"})
            if path == "/api/office-source":
                try:
                    raw = app.office_editor.source(parse_qs(urlsplit(self.path).query), self.headers.get("Authorization", ""))
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(len(raw)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                except (ValueError, PermissionError):
                    return self.send(403, {"error": "Không có quyền tải nguồn Office"})
            if path == "/api/office-engine-auth":
                allowed = app.office_editor.engine_access(self.actor(), self.headers.get("X-BDSG-Engine-Path", ""))
                return self.send(200 if allowed else 403)
            if path == "/mcp":
                if not self.actor(True):
                    return self.send(
                        401,
                        {"error": "Cần chứng thư MCP"},
                        headers={"WWW-Authenticate": 'Bearer realm="bdsg-thanhhoa"'},
                    )
                return self.send(
                    405,
                    {"error": "Dùng POST cho MCP; không hỗ trợ SSE chủ động"},
                    headers={"Allow": "POST"},
                )
            if path == "/api/catalogue":
                return self.send(200, app.catalog())
            if path == "/api/customer-agents":
                return self.send(200, app.customer_support.catalogue())
            if path == "/api/customer-agent":
                try:
                    return self.send(200, app.customer_support.brains.detail(parse_qs(urlsplit(self.path).query).get('id',[''])[0]))
                except ValueError as error:
                    return self.send(404, {'error':str(error)})
            if path == "/api/modules":
                return self.send(200, app.tasks.modules(None))
            if path == "/api/model":
                return self.send(200, app.tasks.model.public_status())
            if path == "/api/suc-khoe":
                return self.send(
                    200,
                    {
                        "status": "ok",
                        "service": "bdsg-thanhhoa",
                        "mcp": "xac-thuc-bat-buoc",
                    },
                )
            actor = self.actor()
            if path == "/api/chatgpt-connection":
                if not actor:
                    return self.send(401, {"error":"Cần đăng nhập"})
                if actor['role'] != 'quan-tri':
                    return self.send(403, {"error":"Chỉ chủ quản xem cài đặt ChatGPT"})
                return self.send(200, app.chatgpt_connection.status())
            if path == "/api/document":
                if not actor:
                    return self.send(401, {"error": "Cần đăng nhập"})
                try:
                    document, raw = app.documents.download(
                        actor, parse_qs(urlsplit(self.path).query).get("id", [""])[0]
                    )
                    self.send_response(200)
                    for k, v in {
                        "Content-Type": "application/octet-stream",
                        "Content-Length": str(len(raw)),
                        "Content-Disposition": "attachment; filename*=UTF-8''"
                        + quote(document["name"]),
                        "Cache-Control": "no-store",
                        "X-Content-Type-Options": "nosniff",
                    }.items():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                except (ValueError, PermissionError):
                    return self.send(404, {"error": "Tệp ngoài phạm vi quyền"})
            if path == "/api/me":
                if actor:
                    try:
                        app.web_sessions.touch(actor, self.session(), self.client_hint())
                    except PermissionError:
                        actor = None
                    except sqlite3.Error:
                        return self.send(503, {"error": "Chưa xác minh được phiên; hãy thử lại"})
                return self.send(
                    200, {"authenticated": actor is not None, "user": actor}
                )
            routes = {
                "/api/agents": "agent.danh_sach",
                "/api/requests": "kinh_doanh.danh_sach",
                "/api/activity": "nhat_ky.danh_sach",
                "/api/connections": "nen_tang.ket_noi",
                "/api/messages": "agent.doc_hop_thu",
                "/api/tasks": "cong_viec.danh_sach",
                "/api/task": "cong_viec.chi_tiet",
            }
            if path not in routes:
                return self.send(404, {"error": "Không tìm thấy"})
            if not actor:
                return self.send(401, {"error": "Cần đăng nhập"})
            arguments = (
                {"id": parse_qs(urlsplit(self.path).query).get("id", [""])[0]}
                if path == "/api/task"
                else {}
            )
            return self.send(200, app.core.goi(actor, routes[path], arguments))

        def do_POST(self):
            self.connection.settimeout(12)
            path = urlsplit(self.path).path
            if path == "/api/office-callback":
                try:
                    return self.send(200, app.office_editor.callback(self.body(), self.headers.get("Authorization", "")))
                except (ValueError, PermissionError, OSError):
                    return self.send(200, {"error": 1})
            if app.operations.draining.is_set():
                return self.send(503, {"error": "Đang dừng dịch vụ; thử lại sau"}, headers={"Retry-After": "5"})
            if not self.origin_ok(required=path != "/mcp"):
                return self.send(403, {"error": "Nguồn truy cập không được phép"})
            actor = self.actor(path == "/mcp")
            if (path not in ("/mcp", "/api/login", "/api/customer-support", "/api/auth/google/start")
                    and not self.cookie_actor_matches(actor)):
                return
            if path not in ("/api/login", "/api/customer-support", '/api/auth/google/start') and not actor:
                return self.send(
                    401,
                    {"error": "Cần xác thực"},
                    headers={"WWW-Authenticate": 'Bearer realm="bdsg-thanhhoa"'}
                    if path == "/mcp"
                    else {},
                )
            try:
                body = self.body()
            except (ValueError, UnicodeDecodeError):
                return self.send(
                    400, {"error": "Nội dung yêu cầu không hợp lệ hoặc quá lớn"}
                )
            try:
                if path in ("/api/sessions/rename", "/api/sessions/revoke", "/api/sessions/revoke-others"):
                    return self.sessions_response(path.rsplit("/", 1)[1], body)
                if path == '/api/auth/google/start':
                    if actor:
                        return self.send(409, {'error':'Bạn đã đăng nhập; hãy đăng xuất trước khi đổi tài khoản'})
                    if body != {}:
                        return self.send(400, {'error':'Yêu cầu đăng nhập không hợp lệ'})
                    try:
                        ip = self.headers.get('X-BDSG-Client-IP', self.client_address[0])
                        url, binding = app.google_login.start(ip)
                        return self.send(200, {'url':url}, cookie='bdsg_google_login='+binding+'; Path=/api/google/callback; Secure; HttpOnly; SameSite=Lax; Max-Age=600')
                    except LoiDangNhapGoogle as error:
                        return self.send(409, {'error':str(error)})
                if path == "/api/google/picker":
                    if actor["role"] not in ("operator", "quan-tri"):
                        return self.send(403, {"error": "Cần quyền vận hành"})
                    try:
                        return self.send(200, app.google_office.picker(actor))
                    except LoiKetNoiGoogle:
                        return self.send(409, {"error": "Chưa sẵn sàng Google Picker; kiểm tra cấu hình và kết nối tài khoản"})
                if path == "/api/google/start":
                    if actor["role"] not in ("operator", "quan-tri"):
                        return self.send(403, {"error": "Cần quyền vận hành"})
                    try:
                        url, binding = app.google_office.start(actor, self.session())
                        return self.send(200, {"url": url}, cookie="bdsg_google=" + binding +
                                         "; Path=/api/google/callback; Secure; HttpOnly; SameSite=Lax; Max-Age=600")
                    except LoiKetNoiGoogle:
                        return self.send(409, {"error": "Chủ quản cần cấu hình OAuth Google trước khi kết nối"})
                if path == "/api/chatgpt-connection/start":
                    if actor['role'] != 'quan-tri':
                        return self.send(403, {"error":"Chỉ chủ quản quản lý kết nối ChatGPT"})
                    return self.send(409, {"error":"Chưa được OpenAI cấp quyền và Client ID cho website. Hồ sơ đăng ký không phải quyền đăng nhập.", "state":"awaiting_partner_approval"})
                if path == "/api/customer-support":
                    try:
                        ip = self.headers.get("X-BDSG-Client-IP", self.client_address[0])[:100]
                        return self.send(200, app.customer_support.reply(body, ip))
                    except QuaHanHoTro as error:
                        return self.send(429, {"error":str(error)}, headers={"Retry-After":"60"})
                    except ValueError as error:
                        return self.send(400, {"error":str(error)})
                if path == "/api/login":
                    user, password = body.get("username", ""), body.get("password", "")
                    if (
                        not isinstance(user, str)
                        or not isinstance(password, str)
                        or len(user) > 64
                        or len(password) > 256
                    ):
                        return self.send(
                            400, {"error": "Thông tin đăng nhập không hợp lệ"}
                        )
                    ip = self.headers.get("X-BDSG-Client-IP", self.client_address[0])
                    token, state = app.kho.dang_nhap(user, password, ip)
                    if not token:
                        return self.send(
                            429 if state == "tam-khoa" else 401,
                            {
                                "error": "Tạm giới hạn đăng nhập; thử lại sau"
                                if state == "tam-khoa"
                                else "Thông tin đăng nhập chưa đúng"
                            },
                        )
                    app.kho.su_kien(user, "dang-nhap")
                    return self.send(
                        200,
                        {"ok": True},
                        "bdsg_session="
                        + token
                        + "; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=28800",
                    )
                if path == "/api/logout":
                    app.kho.dang_xuat(self.session())
                    return self.send(
                        200,
                        {"ok": True},
                        "bdsg_session=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0",
                    )
                if path == "/api/tools":
                    if not isinstance(body.get("name"), str) or not isinstance(
                        body.get("arguments", {}), dict
                    ):
                        return self.send(400, {"error": "Lời gọi công cụ không hợp lệ"})
                    return self.send(
                        200,
                        app.core.goi(actor, body["name"], body.get("arguments", {})),
                    )
                if path == "/api/upload":
                    target = body.pop("destination", "documents")
                    if target not in ("documents", "office-part"):
                        return self.send(400, {"error":"Loại tải lên chưa hỗ trợ"})
                    return self.send(200, app.core.goi(actor, "van_phong.ghi_phan" if target == "office-part" else "tai_lieu.tai_len", body))
                if path == "/api/model-config":
                    if actor["role"] != "quan-tri":
                        return self.send(
                            403, {"error": "Chỉ chủ quản được cấu hình mô hình"}
                        )
                    result = app.core.goi(actor, "cau_hinh.mo_hinh", body)
                    return (
                        self.send(200, result["ket_qua"])
                        if result["ok"]
                        else self.send(
                            400,
                            {
                                "error": "Không lưu được cấu hình. Kiểm tra nhà cung cấp, tên mô hình và khóa API."
                            },
                        )
                    )
                if path == "/mcp":
                    version = self.headers.get("MCP-Protocol-Version", "2025-03-26")
                    if version not in ("2025-03-26", "2025-06-18"):
                        return self.send(
                            400, {"error": "Phiên bản MCP chưa được hỗ trợ"}
                        )
                    accept = self.headers.get("Accept", "")
                    if (
                        "application/json" not in accept
                        or "text/event-stream" not in accept
                    ):
                        return self.send(
                            406,
                            {
                                "error": "MCP cần Accept: application/json, text/event-stream"
                            },
                        )
                    if body.get("jsonrpc") != "2.0" or not isinstance(
                        body.get("method"), str
                    ):
                        return self.send(400, {"error": "Gói JSON-RPC không hợp lệ"})
                    result = app.core.mcp(actor, body)
                    return self.send(202 if result is None else 200, result)
                return self.send(404, {"error": "Không tìm thấy"})
            except Exception:
                return self.send(
                    500,
                    {"error": "Không hoàn tất được yêu cầu; kiểm tra nhật ký vận hành"},
                )

        def do_OPTIONS(self):
            self.send(405, {"error": "Không mở CORS"}, headers={"Allow": "GET, POST"})

    server = MayChuCoGioiHan(("127.0.0.1", port), XuLy)
    return server


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["serve", "init", "create-agent", "revoke-agent"])
    ap.add_argument(
        "--data", default=os.environ.get("BDSG_DATA_DIR", "/var/lib/bdsg-thanhhoa")
    )
    ap.add_argument(
        "--origin", default=os.environ.get("BDSG_ORIGIN", "https://thanhhoa.bdsg.vn")
    )
    ap.add_argument(
        "--port", type=int, default=int(os.environ.get("BDSG_PORT", "8766"))
    )
    ap.add_argument("--id")
    ap.add_argument("--name")
    ap.add_argument("--role", choices=["agent", "operator"], default="agent")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    os.umask(0o077)
    kho = Kho(args.data)
    if args.action in ("init", "create-agent"):
        if not args.output or args.output.exists():
            raise SystemExit(
                "Cần đường dẫn đầu ra riêng tư mới để nhận chứng thư một lần"
            )
        if args.action == "init":
            password = secrets.token_urlsafe(24)
            kho.tao_chu(password)
            credentials = {
                "url": args.origin,
                "username": "chu-quan",
                "password": password,
            }
        else:
            token = kho.tao_agent(args.id or "", args.name or "", args.role)
            credentials = {
                "id": args.id,
                "mcp_url": args.origin + "/mcp",
                "token": token,
            }
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(credentials, f, ensure_ascii=False, indent=2)
        os.chmod(args.output, 0o600)
        print(
            "Đã ghi chứng thư riêng tư vào đường dẫn yêu cầu; không in bí mật ra nhật ký."
        )
        return
    if args.action == "revoke-agent":
        kho.thu_hoi_agent(args.id)
        revoke_browser(args.id)
        return
    app = UngDung(
        args.data,
        args.origin,
        os.environ.get("BDSG_ALLOW_WRITES") == "1",
        connections=os.environ.get("BDSG_CONNECTIONS"),
    )
    server = tao_may_chu(app, args.port)
    app.schedules.start()
    print("BDSG HTTP/MCP đang nghe tại loopback", flush=True)
    def stop_service(*_):
        if not app.operations.draining.is_set():
            app.operations.draining.set()
            # shutdown phải chạy ngoài luồng serve_forever để tránh deadlock.
            threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop_service)
    signal.signal(signal.SIGINT, stop_service)
    try:
        server.serve_forever()
    finally:
        app.operations.draining.set()
        server.server_close()
        app.schedules.close()
        app.tasks.close()
        app.core.audit.close()


if __name__ == "__main__":
    main()
