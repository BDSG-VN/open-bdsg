"""Công cụ nghiệp vụ đi qua nhân Open BDSG và danh tính do máy chủ xác thực."""
import contextvars
import ipaddress
import json
import os
import socket
import threading
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from nhan.danh_tinh import DanhTinh
from nhan.dinh_tuyen import BanKhaiCongCu, Nhan, TrinhDieuKhien
from nhan.nhat_ky import NhatKy
from nhan.quyen import ChinhSach, CongGhi
from nhan.mcp import MayChuMCP


class KhongChuyenHuong(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CongMCP:
    """Đầu nối chỉ đọc cấu hình vận hành riêng; không nhận URL từ yêu cầu người dùng."""
    def __init__(self, path, catalogue):
        self.config = json.loads(Path(path).read_text()) if path and Path(path).is_file() else []
        ids = {p["id"] for p in catalogue}
        for entry in self.config:
            u = urlsplit(entry.get("url", ""))
            if entry.get("platform_id") not in ids or u.scheme != "https" or not u.hostname or not u.hostname.endswith(".bdsg.vn") or u.username or u.password or u.fragment or u.port not in (None, 443):
                raise ValueError("Cấu hình đầu nối không hợp lệ")
            if not isinstance(entry.get("read_tools", []), list) or not isinstance(entry.get("write_tools", []), list):
                raise ValueError("Danh sách công cụ đầu nối không hợp lệ")

    def tom_tat(self):
        return [{"platform_id": c["platform_id"], "state": "da-khai-bao",
                 "read_tools": c.get("read_tools", []), "write_tools": c.get("write_tools", [])} for c in self.config]

    def goi(self, actor, platform_id, tool, arguments, ghi=False):
        config = next((c for c in self.config if c["platform_id"] == platform_id), None)
        if not config or actor["role"] not in config.get("roles", ["quan-tri"]):
            raise PermissionError("Chưa có đầu nối được cấp cho danh tính này")
        if tool not in config.get("write_tools" if ghi else "read_tools", []):
            raise PermissionError("Công cụ chưa được chủ quản cho phép")
        u = urlsplit(config["url"])
        ips = [ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)]
        if not ips or not all(ip.is_global for ip in ips):
            raise PermissionError("Đầu nối phải dùng địa chỉ công khai")
        token = os.environ.get(config.get("token_env", ""), "")
        if not token:
            raise ValueError("Chưa cấu hình chứng thư đầu nối")
        opener = build_opener(KhongChuyenHuong())
        session = {}

        def rpc(id_, method, params):
            headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                       "Authorization": "Bearer " + token, "MCP-Protocol-Version": "2025-06-18", **session}
            payload = {"jsonrpc": "2.0", "method": method, "params": params}
            if id_ is not None:
                payload["id"] = id_
            req = Request(config["url"], data=json.dumps(payload).encode(), headers=headers)
            with opener.open(req, timeout=15) as response:
                if id_ is None:
                    if response.status != 202:
                        raise ValueError("Đầu nối không nhận thông báo khởi tạo")
                    return None
                if response.headers.get("Mcp-Session-Id"):
                    session["Mcp-Session-Id"] = response.headers["Mcp-Session-Id"]
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise ValueError("Phản hồi đầu nối quá lớn")
                if "text/event-stream" in response.headers.get("Content-Type", ""):
                    frames = [json.loads(line[5:].strip()) for line in raw.decode().splitlines() if line.startswith("data:")]
                    value = next((x for x in frames if x.get("id") == id_), None)
                else:
                    value = json.loads(raw)
            if not isinstance(value, dict) or value.get("id") != id_ or value.get("error"):
                raise ValueError("Đầu nối không trả phản hồi MCP hợp lệ")
            return value["result"]

        initialized = rpc(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "open-bdsg-thanhhoa", "version": "0.2.0"}})
        if initialized.get("protocolVersion") != "2025-06-18":
            raise ValueError("Đầu nối cần phiên bản MCP 2025-06-18")
        rpc(None, "notifications/initialized", {})
        # Không tự thử các công cụ khác hoặc chạy chỉ dẫn nằm trong kết quả từ nền tảng.
        return rpc(2, "tools/call", {"name": tool, "arguments": arguments})


class CongCu(TrinhDieuKhien):
    def __init__(self, declarations):
        self.declarations = declarations

    def cong_cu(self):
        return self.declarations


def schema(properties=None, required=None):
    return {"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}


class DieuPhoi:
    def __init__(self, kho, catalogue, ghi=False, connections=None):
        self.kho = kho
        self.catalogue = catalogue
        self.actor = contextvars.ContextVar("bdsg_actor", default=None)
        self.lock = threading.RLock()
        self.connections = CongMCP(connections, catalogue)
        self.audit = (kho.root / "nhat-ky-nhan.jsonl").open("a", encoding="utf-8", buffering=1)
        os.chmod(kho.root / "nhat-ky-nhan.jsonl", 0o600)
        # Nhật ký nhân chỉ giữ tên trường/kích thước; nội dung nghiệp vụ nằm trong CSDL có quyền.
        self.nhan = Nhan(chinh_sach=ChinhSach(CongGhi(mo=ghi, ly_do="Chủ quản bật ghi cho yêu cầu và thông điệp", nguoi_mo="van-hanh")),
                         nhat_ky=NhatKy(dong_ra=self.audit, ham_lam_mo=lambda p: ({"fields": sorted(p), "bytes": len(json.dumps(p))}, len(p))))
        text = {"type": "string"}
        self.nhan.dang_ky("nen_tang", CongCu([
            BanKhaiCongCu("danh_sach", lambda a: {"products": self.catalogue}, mo_ta="Danh mục nền tảng BDSG; liên kết web không xác nhận liên thông dữ liệu.", luoc_do=schema()),
            BanKhaiCongCu("ket_noi", lambda a: {"connections": self.connections.tom_tat()}, mo_ta="Đầu nối MCP được chủ quản khai báo; chưa khai báo khác với đã kết nối.", luoc_do=schema())]))
        self.nhan.dang_ky("agent", CongCu([
            BanKhaiCongCu("danh_sach", lambda a: {"agents": self.kho.agents()}, mo_ta="Danh sách hộp thư agent được đăng ký, không hàm ý đã có mô hình AI.", luoc_do=schema()),
            BanKhaiCongCu("doc_hop_thu", lambda a: {"messages": self.kho.hop_thu(self.actor.get()["id"], a.get("peer"))}, mo_ta="Đọc thông điệp mà danh tính này gửi hoặc nhận.", luoc_do=schema({"peer": text})),
            BanKhaiCongCu("gui_tin", lambda a: self.kho.gui(self.actor.get()["id"], a.get("recipient"), a.get("body")), ghi=True,
                          mo_ta="Giao thông điệp vào hộp thư agent; danh tính người gửi lấy từ xác thực, không từ tham số.", luoc_do=schema({"recipient": text, "body": {"type": "string", "minLength": 1, "maxLength": 4000}}, ["recipient", "body"]))]))
        self.nhan.dang_ky("kinh_doanh", CongCu([
            BanKhaiCongCu("danh_sach", lambda a: {"requests": self.kho.yeu_cau(self.actor.get()["id"], self.actor.get()["role"] == "quan-tri")}, mo_ta="Yêu cầu kinh doanh trong phạm vi danh tính.", luoc_do=schema()),
            BanKhaiCongCu("tao_yeu_cau", lambda a: self.kho.tao_yeu_cau(self.actor.get()["id"], a), ghi=True, mo_ta="Ghi nhận nhu cầu để đi qua tư vấn, triển khai, vận hành và kinh doanh.", luoc_do=schema({"title": text, "sector": text, "description": text}, ["title", "sector", "description"])),
            BanKhaiCongCu("doi_chang", lambda a: self.kho.doi_chang(self.actor.get()["id"], a.get("id"), a.get("stage"), self.actor.get()["role"] == "quan-tri"), ghi=True, mo_ta="Cập nhật chặng của yêu cầu có quyền quản lý.", luoc_do=schema({"id": text, "stage": text}, ["id", "stage"]))]))
        self.nhan.dang_ky("nhat_ky", CongCu([
            BanKhaiCongCu("danh_sach", lambda a: {"events": self.kho.hoat_dong(self.actor.get()["id"], self.actor.get()["role"] == "quan-tri")}, mo_ta="Nhật ký thao tác, không chứa mật khẩu hoặc nội dung thông điệp.", luoc_do=schema())]))
        external = schema({"platform_id": text, "tool": text, "arguments": {"type": "object"}}, ["platform_id", "tool", "arguments"])
        self.nhan.dang_ky("ket_noi", CongCu([
            BanKhaiCongCu("doc", lambda a: self.connections.goi(self.actor.get(), a.get("platform_id"), a.get("tool"), a.get("arguments"), False), mo_ta="Gọi công cụ đọc trong danh sách cho phép của đầu nối đã cấu hình.", luoc_do=external),
            BanKhaiCongCu("ghi", lambda a: self.connections.goi(self.actor.get(), a.get("platform_id"), a.get("tool"), a.get("arguments"), True), ghi=True, mo_ta="Gọi công cụ ghi được chủ quản cho phép; yêu cầu quyền ghi và cổng ghi mở.", luoc_do=external)]))
        reads = ["nen_tang.danh_sach", "nen_tang.ket_noi", "agent.danh_sach", "agent.doc_hop_thu", "nhat_ky.danh_sach"]
        writes = ["agent.gui_tin"]
        self.nhan.chinh_sach.khai_vai("agent", doc=reads, ghi=writes)
        self.nhan.chinh_sach.khai_vai("operator", doc=reads + ["kinh_doanh.danh_sach"], ghi=writes + ["kinh_doanh.tao_yeu_cau", "kinh_doanh.doi_chang"])
        self.nhan.chinh_sach.khai_vai("quan-tri", doc=reads + ["kinh_doanh.danh_sach", "ket_noi.doc"], ghi=writes + ["kinh_doanh.tao_yeu_cau", "kinh_doanh.doi_chang", "ket_noi.ghi"])

    def danh_tinh(self, actor):
        return DanhTinh(ma=actor["id"], ten=actor["name"], vai=(actor["role"],), nguon="cong-thanhhoa")

    def goi(self, actor, name, args):
        with self.lock:
            token = self.actor.set(actor)
            try:
                return self.nhan.goi(self.danh_tinh(actor), name, args).thanh_dict()
            finally:
                self.actor.reset(token)

    def mcp(self, actor, payload):
        with self.lock:
            token = self.actor.set(actor)
            try:
                identity = self.danh_tinh(actor)
                server = MayChuMCP(self.nhan, giai_danh_tinh=lambda p: identity, ten_may="bdsg-thanhhoa", phien_ban="0.2.0")
                # HTTP không giữ phiên MCP. Mỗi yêu cầu đều xác thực lại Bearer riêng.
                server.danh_tinh = identity
                server.da_bat_tay = True
                return server.xu_ly(payload)
            finally:
                self.actor.reset(token)
