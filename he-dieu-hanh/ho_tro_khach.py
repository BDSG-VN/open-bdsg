"""Hướng dẫn công khai từ danh mục; không gọi mô hình hoặc công cụ có quyền."""

import collections
import hashlib
import threading
import time
import unicodedata
from urllib.parse import urlsplit

AGENTS = [
    {
        "id": "tu-van",
        "name": "Tư vấn nền tảng",
        "description": "Tìm nền tảng phù hợp với nhu cầu của bạn.",
    },
    {
        "id": "tai-khoan",
        "name": "Hỗ trợ tài khoản",
        "description": "Hướng dẫn đăng ký, đăng nhập và khôi phục tài khoản.",
    },
    {
        "id": "mua-hang",
        "name": "Hỗ trợ mua hàng",
        "description": "Chuẩn bị các bước chọn sản phẩm và kiểm tra đơn hàng.",
    },
]


def khong_dau(text):
    return "".join(
        c
        for c in unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
        if not unicodedata.combining(c)
    )


class QuaHanHoTro(Exception):
    pass


class HoTroKhach:
    def __init__(self, catalogue):
        self.products = [
            {k: p[k] for k in ("id", "name", "url", "purpose")}
            for p in catalogue
            if urlsplit(p["url"]).scheme == "https" and not urlsplit(p["url"]).username
        ]
        self.lock = threading.Lock()
        self.windows = {}
        self.total = collections.deque()

    def catalogue(self):
        return {"agents": AGENTS, "mode": "huong-dan", "can_execute": False}

    def reply(self, args, ip):
        if set(args) - {"agent", "message", "platform_id"}:
            raise ValueError("Chỉ gửi trợ lý, nội dung và nền tảng cần hỗ trợ")
        message, agent, selected = (
            args.get("message"),
            args.get("agent"),
            args.get("platform_id", ""),
        )
        if (
            not isinstance(message, str)
            or not 1 <= len(message.strip()) <= 1000
            or not isinstance(agent, str)
            or agent not in {a["id"] for a in AGENTS}
            or not isinstance(selected, str)
        ):
            raise ValueError("Chọn trợ lý và nhập từ 1 đến 1000 ký tự")
        if selected and selected not in {p["id"] for p in self.products}:
            raise ValueError("Nền tảng không có trong danh mục BDSG")
        # Bộ đếm có giới hạn trong bộ nhớ; không ghi IP hoặc câu hỏi xuống đĩa.
        now = time.monotonic()
        key = hashlib.sha256(ip.encode()).digest()
        with self.lock:
            self.windows = {
                k: v for k, v in self.windows.items() if v and now - v[-1] < 60
            }
            while self.total and now - self.total[0] >= 60:
                self.total.popleft()
            window = self.windows.get(key, collections.deque())
            while window and now - window[0] >= 60:
                window.popleft()
            if (
                len(window) >= 20
                or len(self.total) >= 200
                or (key not in self.windows and len(self.windows) >= 1024)
            ):
                raise QuaHanHoTro(
                    "Bạn đã gửi nhiều câu hỏi. Vui lòng chờ một phút rồi thử lại."
                )
            window.append(now)
            self.windows[key] = window
            self.total.append(now)
        words = set(khong_dau(message).split()) - {
            "toi",
            "can",
            "tim",
            "nen",
            "tang",
            "cua",
            "cho",
            "voi",
            "muon",
            "mua",
            "hang",
            "tai",
            "khoan",
            "dang",
            "ky",
            "nhap",
            "bdsg",
            "giup",
            "hay",
        }
        ranked = sorted(
            self.products,
            key=lambda p: sum(
                len(w)
                for w in words
                if len(w) > 2 and w in khong_dau(p["name"] + " " + p["purpose"])
            ),
            reverse=True,
        )
        products = (
            [p for p in self.products if p["id"] == selected]
            if selected
            else ranked[:5]
        )
        steps = {
            "tu-van": [
                "Chọn nền tảng trong kết quả hoặc mô tả rõ lĩnh vực cần hỗ trợ.",
                "Đọc mục đích sử dụng và mở website gốc để xem tính năng hiện có.",
                "Giá, tình trạng dịch vụ và dữ liệu nghiệp vụ cần được kiểm tra tại nền tảng gốc.",
            ],
            "tai-khoan": [
                "Mở website gốc của nền tảng đã chọn, tìm Đăng ký hoặc Đăng nhập.",
                "Nếu đã có tài khoản, dùng chức năng khôi phục của chính nền tảng để tránh tạo trùng.",
                "Tự nhập mật khẩu và mã xác minh tại nền tảng gốc; không gửi vào cuộc trò chuyện này.",
                "Kiểm tra điều khoản và xác nhận của bạn trước khi hoàn tất tạo tài khoản.",
            ],
            "mua-hang": [
                "Mở nền tảng gốc, chọn đúng sản phẩm hoặc dịch vụ.",
                "Kiểm tra giá hiện tại, người bán, số lượng, điều kiện giao hàng và đổi trả.",
                "Đăng nhập tại nền tảng gốc và kiểm tra toàn bộ đơn hàng.",
                "Chỉ xác nhận đặt hàng hoặc thanh toán khi bạn đồng ý với tổng tiền và điều kiện.",
            ],
        }
        return {
            "agent": agent,
            "mode": "huong-dan",
            "can_execute": False,
            "source": "nen-tang/danh-muc.json",
            "platforms": products,
            "steps": steps[agent],
            "message": "Tôi hướng dẫn theo danh mục BDSG. Chưa có kết nối để tạo tài khoản hoặc đặt hàng thay bạn.",
            "privacy": "Nội dung câu hỏi không được lưu vào lịch sử máy chủ hoặc gửi tới mô hình AI.",
        }
