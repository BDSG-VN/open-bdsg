"""Hợp đồng đọc được đối chiếu nguồn chính chủ ngày 16/11/2026.

Mã đầu nối khác với tài khoản đã kết nối. Không nhận URL/phương thức tùy ý.
"""

import copy
import re

from vn_transport import LoiTichHop

PROVIDERS = {
    "zalo_oa": {
        "name": "Zalo Official Account",
        "category": "social",
        "version": "OA v2/v3",
        "docs": "https://docs.zaloplatforms.com/docs/OA/quan-ly/quan-ly-thong-tin-oa/lay-thong-tin-zalo-official-account",
        "settings": {},
        "secrets": ["access_token"],
        "operations": {"oa_info": "Đọc thông tin OA"},
        "requires": "OA cấp quyền cho ứng dụng; token OAuth chính thức",
    },
    "zalo_zbs": {
        "name": "Zalo ZBS Template",
        "category": "social",
        "version": "Template API",
        "docs": "https://docs.zaloplatforms.com/docs/ZBS/quan-ly-template/template-api/api-lay-du-lieu-mau-cua-template",
        "settings": {},
        "secrets": ["access_token"],
        "operations": {"template_sample": "Đọc dữ liệu mẫu template"},
        "requires": "OA cấp nhóm quyền ZBS; quyền ZNS cũ không tự chuyển thành ZBS",
    },
    "meta_pages": {
        "name": "Facebook Pages / Messenger",
        "category": "social",
        "version": "pin trong cấu hình",
        "docs": "https://developers.facebook.com/docs/graph-api/reference/page/conversations",
        "settings": {"page_id": "numeric", "graph_version": "graph_version"},
        "secrets": ["access_token"],
        "operations": {
            "page_info": "Đọc thông tin Page",
            "conversations": "Đọc hội thoại Page",
        },
        "requires": "Page token và task/quyền hợp lệ; App Review khi phục vụ bên ngoài",
    },
    "tiktok_display": {
        "name": "TikTok Display",
        "category": "social",
        "version": "v2",
        "docs": "https://developers.tiktok.com/docs/en/tiktok-api-v2-video-list",
        "settings": {},
        "secrets": ["access_token"],
        "operations": {
            "profile": "Đọc hồ sơ đã cấp quyền",
            "videos": "Đọc danh sách video",
        },
        "requires": "Login Kit, scope user.info.basic/video.list và người dùng đồng ý",
    },
    "kiotviet": {
        "name": "KiotViet Retail",
        "category": "commerce",
        "version": "Public API",
        "docs": "https://www.kiotviet.vn/huong-dan-su-dung-kiotviet/retail-ket-noi-api/public-api/",
        "settings": {"retailer": "tenant"},
        "secrets": ["access_token"],
        "operations": {
            "products": "Đọc sản phẩm",
            "orders": "Đọc đơn hàng",
            "invoices": "Đọc hóa đơn bán hàng",
        },
        "requires": "Quản trị bật Public API; token cấp từ ClientId/mã bảo mật của gian hàng",
    },
    "sapo_web": {
        "name": "Sapo Web",
        "category": "commerce",
        "version": "Web Admin API",
        "docs": "https://support.sapo.vn/phuong-thuc-get-cua-product",
        "settings": {"store": "store"},
        "secrets": ["access_token"],
        "operations": {"products": "Đọc sản phẩm", "orders": "Đọc đơn hàng"},
        "requires": "Shop cấp OAuth read_products/read_orders; không phải hợp đồng Sapo POS/FnB",
    },
    "haravan": {
        "name": "Haravan Omni",
        "category": "commerce",
        "version": "com API",
        "docs": "https://docs.haravan.com/docs/omni-apis/orders/",
        "settings": {},
        "secrets": ["access_token"],
        "operations": {"products": "Đọc sản phẩm", "orders": "Đọc đơn hàng"},
        "requires": "Partner app và OAuth com.read_products/com.read_orders",
    },
    "amis_act": {
        "name": "MISA AMIS Kế toán",
        "category": "accounting",
        "version": "ACT Open API g2",
        "docs": "https://actdocs.misa.vn/g2/graph/ACTOpenAPIHelp/index.html",
        "settings": {"app_id": "identifier"},
        "secrets": ["access_token"],
        "operations": {"inventory": "Đọc danh mục vật tư"},
        "requires": "MISA cấp app_id, doanh nghiệp cấp access_code; token ACT của đúng đơn vị",
    },
    "payos": {
        "name": "payOS",
        "category": "payments",
        "version": "v2 payment requests",
        "docs": "https://payos.vn/docs/api/",
        "settings": {},
        "secrets": ["client_id", "api_key", "checksum_key"],
        "operations": {"payment_status": "Tra cứu trạng thái yêu cầu thanh toán"},
        "requires": "Kênh thanh toán đăng ký hợp lệ; payOS không có sandbox riêng",
    },
    "vietqr": {
        "name": "VietQR — danh mục ngân hàng",
        "category": "payments",
        "version": "v2 banks",
        "docs": "https://www.vietqr.io/api-bank",
        "settings": {},
        "secrets": [],
        "operations": {"banks": "Đọc danh mục ngân hàng công khai"},
        "requires": "Không đọc số dư, không tra cứu chủ tài khoản, không chuyển tiền",
    },
    "momo": {
        "name": "MoMo Business",
        "category": "payments",
        "version": "v2 query",
        "docs": "https://developers.momo.vn/v3/vi/docs/payment/api/payment-api/query/",
        "settings": {"partner_code": "identifier", "environment": "environment"},
        "secrets": ["access_key", "secret_key"],
        "operations": {"payment_status": "Tra cứu giao dịch MoMo"},
        "requires": "Tài khoản đối tác, khóa đúng môi trường; chỉ truy vấn trạng thái",
    },
    "meinvoice": {
        "name": "MISA meInvoice",
        "category": "accounting",
        "version": "chờ xác nhận hợp đồng hiện hành",
        "docs": "https://app.meinvoice.vn/api/v2/Description/ConnectByAjax.html",
        "settings": {},
        "secrets": [],
        "operations": {},
        "pending": True,
        "requires": "MISA xác nhận phiên bản/gói, tenant, auth và môi trường thử; chưa bật phát hành/ký/hủy hóa đơn",
    },
    "vnpay": {
        "name": "VNPAY",
        "category": "payments",
        "version": "querydr 2.1.0",
        "docs": "https://sandbox.vnpayment.vn/apis/docs/truy-van-hoan-tien/querydr%26refund.html",
        "settings": {},
        "secrets": [],
        "operations": {},
        "pending": True,
        "requires": "Đã có tài liệu sandbox; cần hợp đồng merchant, host production và chứng thư do VNPAY cấp",
    },
    "bank_openapi": {
        "name": "Open API ngân hàng Việt Nam",
        "category": "banking",
        "version": "theo hợp đồng ngân hàng",
        "docs": "https://openapi.bidv.com.vn/",
        "settings": {},
        "secrets": [],
        "operations": {},
        "pending": True,
        "requires": "Ngân hàng cấp đặc tả, tài khoản sandbox, scope, mTLS/chứng thư nếu yêu cầu; chưa có API số dư/chuyển tiền chung",
    },
}

PATTERNS = {
    "numeric": r"[0-9]{1,40}\Z",
    "graph_version": r"v[1-9][0-9]?\.[0-9]\Z",
    "store": r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z",
    "tenant": r"[A-Za-z0-9_-]{1,100}\Z",
    "identifier": r"[A-Za-z0-9._-]{1,160}\Z",
    "environment": r"(?:sandbox|production)\Z",
}


def provider(identifier):
    if not isinstance(identifier, str) or identifier not in PROVIDERS:
        raise LoiTichHop("invalid_arguments")
    return copy.deepcopy(PROVIDERS[identifier])


def validate_settings(identifier, values):
    contract = provider(identifier)
    if contract.get("pending"):
        raise LoiTichHop("contract_pending")
    if not isinstance(values, dict) or set(values) != set(contract["settings"]):
        raise LoiTichHop("invalid_arguments")
    for name, kind in contract["settings"].items():
        if not isinstance(values[name], str) or not re.fullmatch(
            PATTERNS[kind], values[name]
        ):
            raise LoiTichHop("invalid_arguments")
    return copy.deepcopy(values)


def validate_secrets(identifier, values):
    contract = provider(identifier)
    if not isinstance(values, dict) or set(values) != set(contract["secrets"]):
        raise LoiTichHop("configuration_required")
    for value in values.values():
        if (
            not isinstance(value, str)
            or not 1 <= len(value) <= 8192
            or any(char in value for char in "\r\n\0")
        ):
            raise LoiTichHop("configuration_required")
    return copy.deepcopy(values)


def catalogue():
    return {
        "providers": [
            {
                "id": key,
                **provider(key),
                "implementation": "contract_pending"
                if value.get("pending")
                else "read_adapter",
                "live_connection_verified": False,
                "checked_docs_date": "2026-11-16",
            }
            for key, value in PROVIDERS.items()
        ],
        "external_writes_enabled": False,
    }
