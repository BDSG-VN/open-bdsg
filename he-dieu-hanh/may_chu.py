#!/usr/bin/env python3
"""Cổng HTTP cùng nguồn: phiên web và MCP Bearer tách biệt, chỉ nghe loopback."""

import argparse
import json
import os
import secrets
import sys
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, quote

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))
from kho import Kho
from dieu_phoi import DieuPhoi
from cong_viec import CongViec
from cau_hinh_mo_hinh import CauHinhMoHinh
from cau_hinh_ket_noi import CauHinhKetNoi
from du_an import DuAn
from tai_lieu import TaiLieu
from van_phong import VanPhong
from runtime_tac_vu import RuntimeTacVu
from trinh_duyet import TrinhDuyet, revoke_browser
from hanh_dong import HanhDong, active_actor
from lich_cong_viec import LichCongViec
from phoi_hop import PhoiHop
from ho_tro_khach import HoTroKhach, QuaHanHoTro
from ket_noi_chatgpt import KetNoiChatGPT


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
        self.tasks.documents = self.documents
        self.runtime = RuntimeTacVu(self.kho, self.tasks)
        self.browser = TrinhDuyet(self.kho, self.tasks)
        self.tasks.on_cancel = lambda owner, task_id: revoke_browser(owner, task_id)

        def revoke(identity):
            self.tasks.cancel_owner(identity)
            revoke_browser(identity)

        self.core.on_revoke = revoke
        self.actions = HanhDong(self.kho, self.core, self.tasks,self.browser)
        self.schedules = LichCongViec(self.kho, self.core, self.tasks)
        self.delegation = PhoiHop(self.kho, self.core, self.tasks)
        self.model_settings = CauHinhMoHinh(self.kho, self.tasks)
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
                self.send_header("Set-Cookie", cookie)
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
            if not self.origin_ok(required=path != "/mcp"):
                return self.send(403, {"error": "Nguồn truy cập không được phép"})
            actor = self.actor(path == "/mcp")
            if path not in ("/api/login", "/api/customer-support") and not actor:
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

    server = ThreadingHTTPServer(("127.0.0.1", port), XuLy)
    server.daemon_threads = True
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
    server.serve_forever()


if __name__ == "__main__":
    main()
