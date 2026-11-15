"""Công cụ nghiệp vụ đi qua nhân Open BDSG và danh tính do máy chủ xác thực."""

import contextvars
import ipaddress
import json
import os
import socket
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from nhan.danh_tinh import DanhTinh
from nhan.dinh_tuyen import BanKhaiCongCu, Nhan, TrinhDieuKhien
from nhan.nhat_ky import NhatKy
from nhan.quyen import ChinhSach, CongGhi
from nhan.mcp import MayChuMCP
from nhan_dong_thoi import HanMucDongThoi, NhatKyDongThoi


class KhongChuyenHuong(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CongMCP:
    """Đầu nối chỉ đọc cấu hình vận hành riêng; không nhận URL từ yêu cầu người dùng."""

    def __init__(self, path, catalogue):
        self.config = (
            json.loads(Path(path).read_text()) if path and Path(path).is_file() else []
        )
        ids = {p["id"] for p in catalogue}
        for entry in self.config:
            u = urlsplit(entry.get("url", ""))
            if (
                entry.get("platform_id") not in ids
                or u.scheme != "https"
                or not u.hostname
                or not u.hostname.endswith(".bdsg.vn")
                or u.username
                or u.password
                or u.fragment
                or u.port not in (None, 443)
            ):
                raise ValueError("Cấu hình đầu nối không hợp lệ")
            if not isinstance(entry.get("read_tools", []), list) or not isinstance(
                entry.get("write_tools", []), list
            ):
                raise ValueError("Danh sách công cụ đầu nối không hợp lệ")

    def tom_tat(self):
        return [
            {
                "platform_id": c["platform_id"],
                "state": c.get("state", "da-khai-bao"),
                "checked_at": c.get("checked_at"),
                "read_tools": c.get("read_tools", []),
                "write_tools": c.get("write_tools", []),
            }
            for c in self.config
        ]

    def goi(self, actor, platform_id, tool, arguments, ghi=False):
        config = next((c for c in self.config if c["platform_id"] == platform_id), None)
        if not config or actor["role"] not in config.get("roles", ["quan-tri"]):
            raise PermissionError("Chưa có đầu nối được cấp cho danh tính này")
        if tool not in config.get("write_tools" if ghi else "read_tools", []):
            raise PermissionError("Công cụ chưa được chủ quản cho phép")
        return self._phien(config, "tools/call", {"name": tool, "arguments": arguments})

    def kiem_tra(self, config):
        return self._phien(config, "tools/list", {})

    def _phien(self, config, method, parameters):
        u = urlsplit(config["url"])
        ips = [
            ipaddress.ip_address(x[4][0])
            for x in socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)
        ]
        if not ips or not all(ip.is_global for ip in ips):
            raise PermissionError("Đầu nối phải dùng địa chỉ công khai")
        token = config.get("token") or os.environ.get(config.get("token_env", ""), "")
        if not token:
            raise ValueError("Chưa cấu hình chứng thư đầu nối")
        opener = build_opener(KhongChuyenHuong())
        session = {}

        def rpc(id_, method, params):
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Authorization": "Bearer " + token,
                "MCP-Protocol-Version": "2025-06-18",
                **session,
            }
            payload = {"jsonrpc": "2.0", "method": method, "params": params}
            if id_ is not None:
                payload["id"] = id_
            req = Request(
                config["url"], data=json.dumps(payload).encode(), headers=headers
            )
            with opener.open(req, timeout=10) as response:
                if id_ is None:
                    if response.status != 202:
                        raise ValueError("Đầu nối không nhận thông báo khởi tạo")
                    return None
                if response.headers.get("Mcp-Session-Id"):
                    session["Mcp-Session-Id"] = response.headers["Mcp-Session-Id"]
                if "text/event-stream" in response.headers.get("Content-Type", ""):
                    # Đọc đến kết quả đúng ID, không chờ máy chủ đóng luồng SSE.
                    used, fields, value, deadline = 0, [], None, time.monotonic() + 10
                    while time.monotonic() < deadline:
                        line = response.readline(2 * 1024 * 1024 - used + 1)
                        used += len(line)
                        if used > 2 * 1024 * 1024:
                            raise ValueError("Phản hồi đầu nối quá lớn")
                        if not line:
                            break
                        line = line.decode("utf-8").rstrip("\r\n")
                        if line.startswith("data:"):
                            fields.append(line[5:].lstrip(" "))
                        elif not line and fields:
                            frame = json.loads("\n".join(fields))
                            fields = []
                            if isinstance(frame, dict) and frame.get("id") == id_:
                                value = frame
                                break
                else:
                    raw = response.read(2 * 1024 * 1024 + 1)
                    if len(raw) > 2 * 1024 * 1024:
                        raise ValueError("Phản hồi đầu nối quá lớn")
                    value = json.loads(raw)
            if (
                not isinstance(value, dict)
                or value.get("id") != id_
                or value.get("error")
            ):
                raise ValueError("Đầu nối không trả phản hồi MCP hợp lệ")
            return value["result"]

        try:
            initialized = rpc(
                1,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "open-bdsg-thanhhoa", "version": "0.2.0"},
                },
            )
            if initialized.get("protocolVersion") != "2025-06-18":
                raise ValueError("Đầu nối cần phiên bản MCP 2025-06-18")
            rpc(None, "notifications/initialized", {})
            # Không tự thử các công cụ khác hoặc chạy chỉ dẫn trong kết quả.
            return rpc(2, method, parameters)
        finally:
            if session:
                try:
                    request = Request(
                        config["url"],
                        method="DELETE",
                        headers={
                            "Authorization": "Bearer " + token,
                            "MCP-Protocol-Version": "2025-06-18",
                            **session,
                        },
                    )
                    with opener.open(request, timeout=3):
                        pass
                except Exception:
                    pass  # Máy chủ có thể không hỗ trợ đóng phiên bằng DELETE.


class CongCu(TrinhDieuKhien):
    def __init__(self, declarations):
        self.declarations = declarations

    def cong_cu(self):
        return self.declarations


def schema(properties=None, required=None):
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": False,
    }


class DieuPhoi:
    def __init__(self, kho, catalogue, ghi=False, connections=None):
        self.kho = kho
        self.catalogue = catalogue
        self.actor = contextvars.ContextVar("bdsg_actor", default=None)
        self.lock = threading.RLock()
        self.verify_actor = None
        self.connections = CongMCP(connections, catalogue)
        self.audit = (kho.root / "nhat-ky-nhan.jsonl").open(
            "a", encoding="utf-8", buffering=1
        )
        os.chmod(kho.root / "nhat-ky-nhan.jsonl", 0o600)
        # Nhật ký nhân chỉ giữ tên trường/kích thước; nội dung nghiệp vụ nằm trong CSDL có quyền.
        self.nhan = Nhan(
            chinh_sach=ChinhSach(
                CongGhi(
                    mo=ghi,
                    ly_do="Chủ quản bật ghi cho yêu cầu và thông điệp",
                    nguoi_mo="van-hanh",
                )
            ),
            bo_han_muc=HanMucDongThoi(),
            nhat_ky=NhatKyDongThoi(
                dong_ra=self.audit,
                ham_lam_mo=lambda p: (
                    {"fields": sorted(p), "bytes": len(json.dumps(p))},
                    len(p),
                ),
            ),
        )
        text = {"type": "string"}
        self.nhan.dang_ky(
            "nen_tang",
            CongCu(
                [
                    BanKhaiCongCu(
                        "danh_sach",
                        lambda a: {"products": self.catalogue},
                        mo_ta="Danh mục nền tảng BDSG; liên kết web không xác nhận liên thông dữ liệu.",
                        luoc_do=schema(),
                    ),
                    BanKhaiCongCu(
                        "ket_noi",
                        lambda a: {"connections": self.connections.tom_tat()},
                        mo_ta="Đầu nối MCP được chủ quản khai báo; chưa khai báo khác với đã kết nối.",
                        luoc_do=schema(),
                    ),
                ]
            ),
        )
        self.nhan.dang_ky(
            "agent",
            CongCu(
                [
                    BanKhaiCongCu(
                        "danh_sach",
                        lambda a: {"agents": self.kho.agents()},
                        mo_ta="Danh sách hộp thư agent được đăng ký, không hàm ý đã có mô hình AI.",
                        luoc_do=schema(),
                    ),
                    BanKhaiCongCu(
                        "doc_hop_thu",
                        lambda a: {
                            "messages": self.kho.hop_thu(
                                self.actor.get()["id"], a.get("peer")
                            )
                        },
                        mo_ta="Đọc thông điệp mà danh tính này gửi hoặc nhận.",
                        luoc_do=schema({"peer": text}),
                    ),
                    BanKhaiCongCu(
                        "gui_tin",
                        lambda a: self.kho.gui(
                            self.actor.get()["id"], a.get("recipient"), a.get("body")
                        ),
                        ghi=True,
                        mo_ta="Giao thông điệp vào hộp thư agent; danh tính người gửi lấy từ xác thực, không từ tham số.",
                        luoc_do=schema(
                            {
                                "recipient": text,
                                "body": {
                                    "type": "string",
                                    "minLength": 1,
                                    "maxLength": 4000,
                                },
                            },
                            ["recipient", "body"],
                        ),
                    ),
                ]
            ),
        )
        self.nhan.dang_ky(
            "kinh_doanh",
            CongCu(
                [
                    BanKhaiCongCu(
                        "danh_sach",
                        lambda a: {
                            "requests": self.kho.yeu_cau(
                                self.actor.get()["id"],
                                self.actor.get()["role"] == "quan-tri",
                            )
                        },
                        mo_ta="Yêu cầu kinh doanh trong phạm vi danh tính.",
                        luoc_do=schema(),
                    ),
                    BanKhaiCongCu(
                        "tao_yeu_cau",
                        lambda a: self.kho.tao_yeu_cau(self.actor.get()["id"], a),
                        ghi=True,
                        mo_ta="Ghi nhận nhu cầu để đi qua tư vấn, triển khai, vận hành và kinh doanh.",
                        luoc_do=schema(
                            {"title": text, "sector": text, "description": text},
                            ["title", "sector", "description"],
                        ),
                    ),
                    BanKhaiCongCu(
                        "doi_chang",
                        lambda a: self.kho.doi_chang(
                            self.actor.get()["id"],
                            a.get("id"),
                            a.get("stage"),
                            self.actor.get()["role"] == "quan-tri",
                        ),
                        ghi=True,
                        mo_ta="Cập nhật chặng của yêu cầu có quyền quản lý.",
                        luoc_do=schema({"id": text, "stage": text}, ["id", "stage"]),
                    ),
                ]
            ),
        )
        self.nhan.dang_ky(
            "nhat_ky",
            CongCu(
                [
                    BanKhaiCongCu(
                        "danh_sach",
                        lambda a: {
                            "events": self.kho.hoat_dong(
                                self.actor.get()["id"],
                                self.actor.get()["role"] == "quan-tri",
                            )
                        },
                        mo_ta="Nhật ký thao tác, không chứa mật khẩu hoặc nội dung thông điệp.",
                        luoc_do=schema(),
                    )
                ]
            ),
        )
        external = schema(
            {"platform_id": text, "tool": text, "arguments": {"type": "object"}},
            ["platform_id", "tool", "arguments"],
        )
        self.nhan.dang_ky(
            "ket_noi",
            CongCu(
                [
                    BanKhaiCongCu(
                        "doc",
                        lambda a: self.connections.goi(
                            self.actor.get(),
                            a.get("platform_id"),
                            a.get("tool"),
                            a.get("arguments"),
                            False,
                        ),
                        mo_ta="Gọi công cụ đọc trong danh sách cho phép của đầu nối đã cấu hình.",
                        luoc_do=external,
                    ),
                    BanKhaiCongCu(
                        "ghi",
                        lambda a: self.connections.goi(
                            self.actor.get(),
                            a.get("platform_id"),
                            a.get("tool"),
                            a.get("arguments"),
                            True,
                        ),
                        ghi=True,
                        mo_ta="Gọi công cụ ghi được chủ quản cho phép; yêu cầu quyền ghi và cổng ghi mở.",
                        luoc_do=external,
                    ),
                ]
            ),
        )
        reads = [
            "nen_tang.danh_sach",
            "nen_tang.ket_noi",
            "agent.danh_sach",
            "agent.doc_hop_thu",
            "nhat_ky.danh_sach",
        ]
        writes = ["agent.gui_tin"]
        self.nhan.chinh_sach.khai_vai("agent", doc=reads, ghi=writes)
        self.nhan.chinh_sach.khai_vai(
            "operator",
            doc=reads + ["kinh_doanh.danh_sach"],
            ghi=writes + ["kinh_doanh.tao_yeu_cau", "kinh_doanh.doi_chang"],
        )
        self.nhan.chinh_sach.khai_vai(
            "quan-tri",
            doc=reads + ["kinh_doanh.danh_sach", "ket_noi.doc"],
            ghi=writes
            + ["kinh_doanh.tao_yeu_cau", "kinh_doanh.doi_chang", "ket_noi.ghi"],
        )

    def dang_ky_cong_viec(
        self, engine, configure_model, connectors, disable_model, projects
    ):
        text = {"type": "string"}
        project_fields = {"name": text, "instructions": text, "context": text}
        self.nhan.dang_ky(
            "du_an",
            CongCu(
                [
                    BanKhaiCongCu(
                        "danh_sach",
                        lambda a: projects.list(self.actor.get()),
                        mo_ta="Dự án và ngữ cảnh riêng trong phạm vi danh tính.",
                        luoc_do=schema(),
                    ),
                    BanKhaiCongCu(
                        "tao",
                        lambda a: projects.create(self.actor.get(), a),
                        ghi=True,
                        mo_ta="Tạo không gian dự án với hướng dẫn và ngữ cảnh dùng lại.",
                        luoc_do=schema(project_fields, ["name"]),
                    ),
                    BanKhaiCongCu(
                        "cap_nhat",
                        lambda a: projects.update(self.actor.get(), a),
                        ghi=True,
                        mo_ta="Cập nhật dự án; tác vụ đã tạo giữ bản chụp ngữ cảnh cũ.",
                        luoc_do=schema({**project_fields, "id": text}, ["id", "name"]),
                    ),
                    BanKhaiCongCu(
                        "luu_tru",
                        lambda a: projects.archive(self.actor.get(), a.get("id")),
                        ghi=True,
                        mo_ta="Lưu trữ có thể khôi phục, không xóa tác vụ hay ngữ cảnh.",
                        luoc_do=schema({"id": text}, ["id"]),
                    ),
                    BanKhaiCongCu(
                        "khoi_phuc",
                        lambda a: projects.archive(
                            self.actor.get(), a.get("id"), False
                        ),
                        ghi=True,
                        mo_ta="Khôi phục dự án đã lưu trữ.",
                        luoc_do=schema({"id": text}, ["id"]),
                    ),
                ]
            ),
        )
        self.nhan.dang_ky(
            "mo_dun",
            CongCu(
                [
                    BanKhaiCongCu(
                        "danh_sach",
                        lambda a: engine.modules(self.actor.get()),
                        mo_ta="Mô-đun web và công cụ MCP đã khai báo, không suy diễn liên thông.",
                        luoc_do=schema(),
                    )
                ]
            ),
        )
        self.nhan.dang_ky(
            "cong_viec",
            CongCu(
                [
                    BanKhaiCongCu(
                        "danh_sach",
                        lambda a: engine.list(self.actor.get()),
                        mo_ta="Danh sách tác vụ trong phạm vi danh tính.",
                        luoc_do=schema(),
                    ),
                    BanKhaiCongCu(
                        "chi_tiet",
                        lambda a: engine.detail(self.actor.get(), a.get("id")),
                        mo_ta="Kế hoạch, tiến trình và sản phẩm của tác vụ có quyền xem.",
                        luoc_do=schema({"id": text}, ["id"]),
                    ),
                    BanKhaiCongCu(
                        "tao",
                        lambda a: engine.create(self.actor.get(), a),
                        ghi=True,
                        mo_ta="Tạo tác vụ với ngữ cảnh dự án và quyền đọc/thực thi được chọn rõ; không tự ghi nghiệp vụ bên ngoài.",
                        luoc_do=schema(
                            {
                                "prompt": text,
                                "module_ids": {"type": "array", "items": text},
                                "template": text,
                                "project_id": text,
                                "allow_module_reads": {"type": "boolean"},
                                "document_ids": {"type": "array", "items": text},
                                "allow_python": {"type": "boolean"},
                                "browser_hosts": {"type": "array", "items": text},
                                "allow_action_drafts": {"type": "boolean"},
                                "allow_delegation": {"type": "boolean"},
                            },
                            ["prompt"],
                        ),
                    ),
                    BanKhaiCongCu(
                        "tiep_tuc",
                        lambda a: engine.followup(
                            self.actor.get(), a.get("id"), a.get("text")
                        ),
                        ghi=True,
                        mo_ta="Bổ sung ngữ cảnh và chạy tiếp một tác vụ đã dừng.",
                        luoc_do=schema({"id": text, "text": text}, ["id", "text"]),
                    ),
                    BanKhaiCongCu(
                        "dung",
                        lambda a: engine.cancel(self.actor.get(), a.get("id")),
                        ghi=True,
                        mo_ta="Yêu cầu dừng hợp tác giữa các bước thực thi.",
                        luoc_do=schema({"id": text}, ["id"]),
                    ),
                ]
            ),
        )
        common = [
            "nen_tang.danh_sach",
            "nen_tang.ket_noi",
            "agent.danh_sach",
            "agent.doc_hop_thu",
            "nhat_ky.danh_sach",
            "mo_dun.danh_sach",
        ]
        jobs = ["cong_viec.danh_sach", "cong_viec.chi_tiet", "du_an.danh_sach"]
        self.nhan.dang_ky(
            "cau_hinh",
            CongCu(
                [
                    BanKhaiCongCu(
                        "dau_noi",
                        lambda a: connectors.list(self.actor.get()),
                        mo_ta="Chủ quản xem cấu hình đầu nối đã che chứng thư.",
                        luoc_do=schema(),
                    ),
                    BanKhaiCongCu(
                        "luu_dau_noi",
                        lambda a: connectors.save(self.actor.get(), a),
                        ghi=True,
                        mo_ta="Khai báo đầu nối BDSG và tên công cụ đọc được phép; không tự kết nối.",
                        luoc_do=schema(
                            {
                                "platform_id": text,
                                "url": text,
                                "token": text,
                                "read_tools": {"type": "array", "items": text},
                                "write_tools": {"type": "array", "items": text},
                                "allow_writes": {"type": "boolean"},
                            },
                            ["platform_id", "url"],
                        ),
                    ),
                    BanKhaiCongCu(
                        "kiem_tra_dau_noi",
                        lambda a: connectors.probe(
                            self.actor.get(), a.get("platform_id")
                        ),
                        ghi=True,
                        mo_ta="Kiểm initialize/tools/list, không gọi nghiệp vụ bên ngoài.",
                        luoc_do=schema({"platform_id": text}, ["platform_id"]),
                    ),
                    BanKhaiCongCu(
                        "ngat_dau_noi",
                        lambda a: connectors.disconnect(
                            self.actor.get(), a.get("platform_id")
                        ),
                        ghi=True,
                        mo_ta="Ngắt đầu nối và xóa chứng thư hoạt động trong cấu hình riêng.",
                        luoc_do=schema({"platform_id": text}, ["platform_id"]),
                    ),
                    BanKhaiCongCu(
                        "tat_mo_hinh",
                        lambda a: disable_model(self.actor.get()),
                        ghi=True,
                        mo_ta="Tắt API mô hình cho các lượt chạy mới, xóa khóa đang lưu.",
                        luoc_do=schema(),
                    ),
                    BanKhaiCongCu(
                        "mo_hinh",
                        lambda a: configure_model(self.actor.get(), a),
                        ghi=True,
                        mo_ta="Chủ quản lưu chứng thư mô hình riêng trên máy chủ. Không trả khóa API trong kết quả.",
                        luoc_do=schema(
                            {
                                "provider": text,
                                "model": text,
                                "api_key": text,
                                "base_url": text,
                            },
                            ["provider", "model", "api_key"],
                        ),
                    ),
                ]
            ),
        )
        writes = [
            "agent.gui_tin",
            "kinh_doanh.tao_yeu_cau",
            "kinh_doanh.doi_chang",
            "cong_viec.tao",
            "cong_viec.tiep_tuc",
            "cong_viec.dung",
            "du_an.tao",
            "du_an.cap_nhat",
            "du_an.luu_tru",
            "du_an.khoi_phuc",
        ]
        self.nhan.chinh_sach.khai_vai("agent", doc=common, ghi=["agent.gui_tin"])
        self.nhan.chinh_sach.khai_vai(
            "operator", doc=common + jobs + ["kinh_doanh.danh_sach"], ghi=writes
        )
        self.nhan.chinh_sach.khai_vai(
            "quan-tri",
            doc=common
            + jobs
            + ["kinh_doanh.danh_sach", "ket_noi.doc", "cau_hinh.dau_noi"],
            ghi=writes
            + [
                "ket_noi.ghi",
                "cau_hinh.mo_hinh",
                "cau_hinh.tat_mo_hinh",
                "cau_hinh.luu_dau_noi",
                "cau_hinh.kiem_tra_dau_noi",
                "cau_hinh.ngat_dau_noi",
            ],
        )

    def dang_ky_mo_rong(self, app):
        text = {"type": "string"}
        obj = {"type": "object"}
        boolean = {"type": "boolean"}
        integer = {"type": "integer"}
        actor = lambda: self.actor.get()
        declarations = {
            "van_phong": [
                ("trang_thai", lambda a: app.office.status(actor(), a), False,
                 {"project_id": text}, ["project_id"]),
                ("danh_sach", lambda a: app.office.list(actor(), a), False,
                 {"project_id": text, "trashed": boolean}, ["project_id"]),
                ("tao", lambda a: app.office.create(actor(), a), True,
                 {"project_id": text, "name": text, "content_base64": text},
                 ["project_id", "name", "content_base64"]),
                ("doc", lambda a: app.office.read(actor(), a), False,
                 {"id": text, "version": integer}, ["id"]),
                ("lich_su", lambda a: app.office.history(actor(), a), False,
                 {"id": text}, ["id"]),
                ("cap_nhat", lambda a: app.office.update(actor(), a), True,
                 {"id": text, "expected_revision": integer, "action": text,
                  "name": text, "content_base64": text, "version": integer},
                 ["id", "expected_revision", "action"]),
            ],
            "tai_lieu": [
                (
                    "danh_sach",
                    lambda a: app.documents.list(actor(), a.get("project_id")),
                    False,
                    {"project_id": text},
                    ["project_id"],
                ),
                (
                    "tai_len",
                    lambda a: app.documents.upload(actor(), a),
                    True,
                    {"project_id": text, "name": text, "content_base64": text},
                    ["project_id", "name", "content_base64"],
                ),
            ],
            "cong_tac": [
                (
                    "thanh_vien",
                    lambda a: app.projects.members(actor(), a.get("id")),
                    False,
                    {"id": text},
                    ["id"],
                ),
                (
                    "chia_se",
                    lambda a: app.projects.share(actor(), a),
                    True,
                    {"id": text, "identity": text, "role": text},
                    ["id", "identity", "role"],
                ),
            ],
            "nguoi_dung": [
                (
                    "tao",
                    lambda a: app.kho.tao_nguoi_dung(actor(), a),
                    True,
                    {"id": text, "name": text, "password": text},
                    ["id", "name", "password"],
                ),
                (
                    "thu_hoi",
                    lambda a: self._thu_hoi_nguoi_dung(actor(), a),
                    True,
                    {"id": text},
                    ["id"],
                ),
            ],
            "runtime": [
                (
                    "python",
                    lambda a: app.runtime.run(actor(), a),
                    True,
                    {
                        "task_id": text,
                        "code": text,
                        "output_names": {"type": "array", "items": text},
                    },
                    ["task_id", "code"],
                )
            ],
            "trinh_duyet": [
                (
                    "hanh_dong",
                    lambda a: app.browser.approved_action(actor(), a),
                    True,
                    {
                        "task_id": text,
                        "action": text,
                        "node": integer,
                        "nonce": text,
                        "text": text,
                    },
                    ["task_id", "action", "node", "nonce"],
                ),
                (
                    "doc",
                    lambda a: app.browser.call(actor(), a),
                    True,
                    {
                        "task_id": text,
                        "action": text,
                        "url": text,
                        "nonce": text,
                        "node": integer,
                    },
                    ["task_id", "action"],
                ),
                (
                    "tiep_quan",
                    lambda a: app.browser.call(actor(), a, manual=True),
                    True,
                    {
                        "task_id": text,
                        "action": text,
                        "url": text,
                        "nonce": text,
                        "node": integer,
                        "text": text,
                        "image": boolean,
                    },
                    ["task_id", "action"],
                ),
            ],
            "hanh_dong": [
                (
                    "xem_trinh_duyet",
                    lambda a: app.actions.preview(actor(), a.get("id")),
                    False,
                    {"id": text},
                    ["id"],
                ),
                ("danh_sach", lambda a: app.actions.list(actor()), False, {}, []),
                (
                    "de_xuat",
                    lambda a: app.actions.propose(actor(), a),
                    True,
                    {"task_id": text, "tool": text, "arguments": obj},
                    ["task_id", "tool", "arguments"],
                ),
                (
                    "duyet",
                    lambda a: app.actions.decide(actor(), a),
                    True,
                    {"id": text, "digest": text, "approve": boolean},
                    ["id", "digest", "approve"],
                ),
            ],
            "phoi_hop": [
                (
                    "danh_sach",
                    lambda a: app.delegation.list(actor(), a.get("task_id")),
                    False,
                    {"task_id": text},
                    ["task_id"],
                ),
                (
                    "giao_viec",
                    lambda a: app.delegation.delegate(actor(), a),
                    True,
                    {"task_id": text, "recipient": text, "prompt": text},
                    ["task_id", "recipient", "prompt"],
                ),
            ],
            "lich": [
                ("danh_sach", lambda a: app.schedules.list(actor()), False, {}, []),
                (
                    "tao",
                    lambda a: app.schedules.create(actor(), a),
                    True,
                    {"name": text, "interval_seconds": integer, "task": obj},
                    ["name", "interval_seconds", "task"],
                ),
                (
                    "bat_tat",
                    lambda a: app.schedules.toggle(actor(), a),
                    True,
                    {"id": text, "enabled": boolean},
                    ["id", "enabled"],
                ),
            ],
            "van_hanh": [
                (
                    "tong_quan",
                    lambda a: self._tong_quan(app),
                    False,
                    {},
                    [],
                )
            ],
        }
        # Preserve all existing grants; extend via the public policy interface.
        grants = {}
        for role in ("operator", "quan-tri"):
            old = self.nhan.danh_sach_cong_cu(
                self.danh_tinh({"id": "policy-check", "name": "Policy", "role": role})
            )
            grants[role] = (
                [x["ten"] for x in old if not x["ghi"]],
                [x["ten"] for x in old if x["ghi"]],
            )
        for namespace, entries in declarations.items():
            self.nhan.dang_ky(
                namespace,
                CongCu(
                    [
                        BanKhaiCongCu(
                            name,
                            func,
                            ghi=write,
                            mo_ta=(
                                "Lập dự thảo, chưa thực hiện. Thao tác trình duyệt dùng tool=trinh_duyet.hanh_dong; arguments gồm task_id, action (fill/select/click/key), node và nonce từ quan sát mới nhất, text nếu cần. Chỉ dữ liệu nghiệp vụ thông thường; không gửi mật khẩu, OTP hoặc thanh toán. Chủ quản duyệt riêng."
                                if namespace == "hanh_dong" and name == "de_xuat"
                                else namespace + "." + name
                            ),
                            luoc_do=schema(fields, required),
                        )
                        for name, func, write, fields, required in entries
                    ]
                ),
            )
            for role, (reads, writes) in grants.items():
                for name, func, write, fields, required in entries:
                    if (
                        role != "quan-tri"
                        and namespace == "hanh_dong"
                        and name == "duyet"
                    ):
                        continue
                    if role != "quan-tri" and namespace == "nguoi_dung":
                        continue
                    (writes if write else reads).append(namespace + "." + name)
        for role, (reads, writes) in grants.items():
            self.nhan.chinh_sach.khai_vai(role, doc=reads, ghi=writes)

    def _tong_quan(self, app):
        actor = self.actor.get()
        jobs = app.tasks.list(actor)["tasks"]
        requests = self.kho.yeu_cau(actor["id"], actor["role"] == "quan-tri")
        stages = {
            s: sum(1 for r in requests if r["stage"] == s)
            for s in ("tu-van", "trien-khai", "van-hanh", "kinh-doanh")
        }
        day = ((time.time() + 25200) // 86400) * 86400 - 25200
        with self.kho.ket_noi() as db:
            count = db.execute(
                "SELECT count(*) FROM model_calls WHERE created>=?"
                + ("" if actor["role"] == "quan-tri" else " AND owner=?"),
                (day,) if actor["role"] == "quan-tri" else (day, actor["id"]),
            ).fetchone()[0]
        return {
            "tasks": jobs,
            "model": app.tasks.model.public_status(),
            "business": {"request_count": len(requests), "stages": stages},
            "reserved_api_calls_today": count,
            "limits": {
                "model_turns": 8,
                "model_deadline_seconds": 180,
                "daily_requests_per_identity": 100,
                "daily_requests_total": 200,
                "python_deadline_seconds": 15,
                "file_bytes": 1048576,
                "browser_sessions": 2,
            },
        }

    def _thu_hoi_nguoi_dung(self, actor, args):
        if actor.get("role") != "quan-tri":
            raise PermissionError("Cần chủ quản")
        self.kho.thu_hoi_agent(args.get("id", ""))
        callback = getattr(self, "on_revoke", None)
        if callback:
            callback(args.get("id", ""))
        return {"revoked": True}

    def danh_tinh(self, actor):
        return DanhTinh(
            ma=actor["id"],
            ten=actor["name"],
            vai=(actor["role"],),
            nguon="cong-thanhhoa",
        )

    def goi(self, actor, name, args):
        if self.verify_actor and not self.verify_actor(actor):
            return {
                "ok": False,
                "ly_do": "Danh tính đã bị thu hồi",
                "loai_loi": "xac-thuc",
            }
        token = self.actor.set(actor)
        try:
            result = self.nhan.goi(self.danh_tinh(actor), name, args).thanh_dict()
            if self.verify_actor and not self.verify_actor(actor):
                return {
                    "ok": False,
                    "ly_do": "Danh tính đã bị thu hồi",
                    "loai_loi": "xac-thuc",
                }
            return result
        finally:
            self.actor.reset(token)

    def mcp(self, actor, payload):
        if self.verify_actor and not self.verify_actor(actor):
            return {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "error": {"code": -32001, "message": "Danh tính đã bị thu hồi"},
            }
        token = self.actor.set(actor)
        try:
            identity = self.danh_tinh(actor)
            server = MayChuMCP(
                self.nhan,
                giai_danh_tinh=lambda p: identity,
                ten_may="bdsg-thanhhoa",
                phien_ban="0.2.0",
            )
            server.danh_tinh = identity
            server.da_bat_tay = True
            result = server.xu_ly(payload)
            if self.verify_actor and not self.verify_actor(actor):
                return {
                    "jsonrpc": "2.0",
                    "id": payload.get("id"),
                    "error": {"code": -32001, "message": "Danh tính đã bị thu hồi"},
                }
            return result
        finally:
            self.actor.reset(token)
