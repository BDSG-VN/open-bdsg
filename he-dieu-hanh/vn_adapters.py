"""Đầu nối đọc cố định cho từng sản phẩm, không có công cụ HTTP tùy ý."""

import json
import math
import re
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

from vn_chu_ky import momo_query_signature, verify_payos
from vn_hop_dong import provider, validate_secrets, validate_settings
from vn_transport import LoiTichHop, retry_after_seconds


@dataclass(frozen=True)
class YeuCau:
    provider_id: str
    operation: str
    host: str
    method: str
    path: str
    headers: dict
    body: dict | None
    collection: str
    limit: int
    offset: int
    identity: str = ""


def _arguments(values, allowed):
    if not isinstance(values, dict) or set(values) - set(allowed):
        raise LoiTichHop("invalid_arguments")


def _integer(values, name, default, maximum):
    value = values.get(name, default)
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= maximum
    ):
        raise LoiTichHop("invalid_arguments")
    return value


def _id(values, name):
    value = values.get(name)
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", value):
        raise LoiTichHop("invalid_arguments")
    return value


def prepare(identifier, settings, credentials, operation, arguments):
    contract = provider(identifier)
    settings = validate_settings(identifier, settings)
    credentials = validate_secrets(identifier, credentials)
    if operation not in contract["operations"]:
        raise LoiTichHop("permission_denied")
    headers = {}
    body = None
    method = "GET"
    collection = "data"
    limit, offset, identity = 100, 0, ""
    query = {}
    if identifier == "zalo_oa":
        _arguments(arguments, ())
        host, path = "openapi.zalo.me", "/v2.0/oa/getoa"
        headers["access_token"] = credentials["access_token"]
    elif identifier == "zalo_zbs":
        _arguments(arguments, ("template_id",))
        host, path = "business.openapi.zalo.me", "/template/sample-data"
        identity = _id(arguments, "template_id")
        query["template_id"] = identity
        headers["access_token"] = credentials["access_token"]
        headers["Content-Type"] = "application/json"
    elif identifier == "meta_pages":
        _arguments(
            arguments, ("limit", "after") if operation == "conversations" else ()
        )
        host = "graph.facebook.com"
        path = "/" + settings["graph_version"] + "/" + settings["page_id"]
        headers["Authorization"] = "Bearer " + credentials["access_token"]
        if operation == "conversations":
            path += "/conversations"
            limit = _integer(arguments, "limit", 20, 50)
            if not limit:
                raise LoiTichHop("invalid_arguments")
            query.update(limit=limit, fields="id,updated_time")
            if arguments.get("after"):
                after = arguments["after"]
                if (
                    not isinstance(after, str)
                    or len(after) > 2048
                    or any(c in after for c in "\r\n\0")
                ):
                    raise LoiTichHop("invalid_arguments")
                query["after"] = after
        else:
            query["fields"] = "id,name"
            collection = ""
    elif identifier == "tiktok_display":
        host = "open.tiktokapis.com"
        headers["Authorization"] = "Bearer " + credentials["access_token"]
        if operation == "profile":
            _arguments(arguments, ())
            path = "/v2/user/info/"
            query["fields"] = "open_id,display_name,avatar_url"
            collection = "data.user"
        else:
            _arguments(arguments, ("limit", "cursor"))
            path, method = "/v2/video/list/", "POST"
            query["fields"] = "id,title,cover_image_url"
            limit = _integer(arguments, "limit", 20, 20)
            offset = _integer(arguments, "cursor", 0, 2**63 - 1)
            if not limit:
                raise LoiTichHop("invalid_arguments")
            body = {"max_count": limit, "cursor": offset}
            collection = "data.videos"
    elif identifier == "kiotviet":
        _arguments(arguments, ("limit", "offset"))
        host, path = "public.kiotapi.com", "/" + operation
        headers.update(
            {
                "Retailer": settings["retailer"],
                "Authorization": "Bearer " + credentials["access_token"],
            }
        )
        limit = _integer(arguments, "limit", 50, 100)
        offset = _integer(arguments, "offset", 0, 10**9)
        if not limit:
            raise LoiTichHop("invalid_arguments")
        query = {"pageSize": limit, "currentItem": offset}
    elif identifier in ("sapo_web", "haravan"):
        _arguments(arguments, ("limit", "page"))
        limit = _integer(arguments, "limit", 50, 50)
        offset = _integer(arguments, "page", 1, 10**7)
        if not limit or not offset:
            raise LoiTichHop("invalid_arguments")
        if identifier == "sapo_web":
            host = settings["store"] + ".mysapo.net"
            path = "/admin/" + operation + ".json"
            headers["X-Sapo-Access-Token"] = credentials["access_token"]
        else:
            host, path = "apis.haravan.com", "/com/" + operation + ".json"
            headers["Authorization"] = "Bearer " + credentials["access_token"]
        query, collection = {"limit": limit, "page": offset}, operation
    elif identifier == "amis_act":
        _arguments(arguments, ("limit", "offset"))
        host, path, method = (
            "actapp.misa.vn",
            "/apir/sync/actopen/get_dictionary",
            "POST",
        )
        headers["X-MISA-AccessToken"] = credentials["access_token"]
        limit = _integer(arguments, "limit", 100, 100)
        offset = _integer(arguments, "offset", 0, 10**9)
        if not limit:
            raise LoiTichHop("invalid_arguments")
        body = {
            "app_id": settings["app_id"],
            "data_type": 2,
            "branch_id": None,
            "skip": offset,
            "take": limit,
            "last_sync_time": None,
        }
        collection = "Data"
    elif identifier == "payos":
        _arguments(arguments, ("payment_id",))
        identity = _id(arguments, "payment_id")
        host, path = "api-merchant.payos.vn", "/v2/payment-requests/" + identity
        headers = {
            "x-client-id": credentials["client_id"],
            "x-api-key": credentials["api_key"],
        }
    elif identifier == "vietqr":
        _arguments(arguments, ())
        host, path = "api.vietqr.io", "/v2/banks"
        limit = 500
    elif identifier == "momo":
        _arguments(arguments, ("order_id",))
        identity = _id(arguments, "order_id")
        host = (
            "test-payment.momo.vn"
            if settings["environment"] == "sandbox"
            else "payment.momo.vn"
        )
        path, method, collection = "/v2/gateway/api/query", "POST", ""
        body = {
            "partnerCode": settings["partner_code"],
            "requestId": secrets.token_hex(16),
            "orderId": identity,
            "lang": "vi",
            "signature": momo_query_signature(
                settings["partner_code"],
                identity,
                credentials["access_key"],
                credentials["secret_key"],
            ),
        }
    else:
        raise LoiTichHop("contract_pending")
    if query:
        path += "?" + urlencode(query)
    return YeuCau(
        identifier,
        operation,
        host,
        method,
        path,
        headers,
        body,
        collection,
        limit,
        offset,
        identity,
    )


def _extract(data, path):
    value = data
    for part in path.split(".") if path else []:
        if not isinstance(value, dict) or part not in value:
            raise LoiTichHop("invalid_response")
        value = value[part]
    if isinstance(value, str) and path == "Data":
        try:
            value = json.loads(value)
        except ValueError:
            raise LoiTichHop("invalid_response") from None
    return value


FIELDS = {
    "oa_info": ("oa_id", "name", "description"),
    "template_sample": ("template_id", "parameter", "sample_value"),
    "page_info": ("id", "name"),
    "conversations": ("id", "updated_time"),
    "profile": ("open_id", "display_name", "avatar_url"),
    "videos": ("id", "title", "cover_image_url"),
    "products": (
        "id",
        "code",
        "name",
        "title",
        "sku",
        "basePrice",
        "createdDate",
        "modifiedDate",
        "created_on",
        "modified_on",
        "updated_at",
    ),
    "orders": (
        "id",
        "code",
        "name",
        "status",
        "total",
        "total_price",
        "purchaseDate",
        "created_on",
        "created_at",
        "updated_at",
    ),
    "invoices": ("id", "code", "status", "total", "purchaseDate"),
    "inventory": (
        "inventory_item_id",
        "inventory_item_code",
        "inventory_item_name",
        "unit_name",
        "inactive",
    ),
    "banks": (
        "id",
        "name",
        "code",
        "bin",
        "shortName",
        "transferSupported",
        "lookupSupported",
    ),
    "payment_status": (
        "id",
        "orderCode",
        "orderId",
        "amount",
        "amountPaid",
        "amountRemaining",
        "status",
        "createdAt",
        "resultCode",
        "transId",
        "responseTime",
    ),
}


def _public_record(row, operation):
    if not isinstance(row, dict):
        raise LoiTichHop("invalid_response")
    required = {
        "oa_info": ("oa_id",),
        "page_info": ("id",),
        "conversations": ("id",),
        "profile": ("open_id",),
        "videos": ("id",),
        "products": ("id",),
        "orders": ("id",),
        "invoices": ("id",),
        "inventory": ("inventory_item_id",),
        "banks": ("id", "bin", "name"),
        "template_sample": ("template_id", "parameter"),
        "payment_status": (),
    }[operation]
    for field in required:
        value = row.get(field)
        if (
            isinstance(value, bool)
            or not isinstance(value, (str, int))
            or str(value).strip() == ""
        ):
            raise LoiTichHop("invalid_response")
    record = {}
    for name in FIELDS[operation]:
        value = row.get(name)
        # Không trả payload tùy ý: response Meta có thể kèm token hoặc thông tin cá nhân.
        if value is None:
            continue
        if isinstance(value, str):
            record[name] = value[:4000]
        elif isinstance(value, (int, float, bool)):
            if isinstance(value, float) and not math.isfinite(value):
                raise LoiTichHop("invalid_response")
            record[name] = value
    for name in ("id", "oa_id", "open_id", "inventory_item_id", "transId", "orderCode"):
        if name in record:
            record[name] = str(record[name])
    for name in (
        "amount",
        "amountPaid",
        "amountRemaining",
        "total",
        "total_price",
        "basePrice",
    ):
        if name in record:
            value = record[name]
            if isinstance(value, str):
                if not re.fullmatch(r"[0-9]{1,24}(?:\.[0-9]{1,8})?", value):
                    raise LoiTichHop("invalid_response")
            elif (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
            ):
                raise LoiTichHop("invalid_response")
            record[name] = str(value)
    return record


def decode(plan, response, credentials):
    data = response.data
    if not isinstance(data, dict):
        raise LoiTichHop("invalid_response")
    identifier = plan.provider_id
    if identifier.startswith("zalo_"):
        error = data.get("error")
        if identifier == "zalo_oa" and error in (-216, -220, -219):
            raise LoiTichHop("authorization_required")
        if identifier == "zalo_oa" and error == -212:
            raise LoiTichHop("permission_denied")
        if identifier == "zalo_zbs" and error == -124:
            raise LoiTichHop("authorization_required")
        if identifier == "zalo_zbs" and error == -117:
            raise LoiTichHop("permission_denied")
        if not isinstance(error, int) or isinstance(error, bool) or error != 0:
            raise LoiTichHop("invalid_response")
    if identifier == "meta_pages" and "error" in data:
        error = data["error"]
        code = error.get("code") if isinstance(error, dict) else None
        if code in (102, 190):
            raise LoiTichHop("authorization_required")
        if isinstance(code, int) and (code in (3, 10) or 200 <= code <= 299):
            raise LoiTichHop("permission_denied")
        raise LoiTichHop("invalid_response")
    if identifier == "tiktok_display" and (
        not isinstance(data.get("error"), dict) or data["error"].get("code") != "ok"
    ):
        error = data.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        if code == "access_token_invalid":
            raise LoiTichHop("authorization_required")
        if code in ("scope_not_authorized", "scope_permission_missed"):
            raise LoiTichHop("permission_denied")
        if code == "rate_limit_exceeded":
            raise LoiTichHop(
                "rate_limited", retry_after_seconds(response.headers.get("retry-after"))
            )
        raise LoiTichHop("invalid_response")
    if identifier == "amis_act" and data.get("Success") is not True:
        code = data.get("ErrorCode") or data.get("error_code")
        if code in (
            "InvalidAppID",
            "InvalidToken",
            "ExpiredToken",
            "InvalidAccessToken",
            "AppIDDisconnect",
        ):
            raise LoiTichHop("authorization_required")
        if code == "DBAmisNotConnectDBACT":
            raise LoiTichHop("configuration_required")
        raise LoiTichHop("invalid_response")
    if identifier in ("vietqr", "payos") and data.get("code") != "00":
        raise LoiTichHop("invalid_response")
    verified = False
    if identifier == "payos":
        verify_payos(
            data.get("data"), data.get("signature"), credentials["checksum_key"]
        )
        payment = data["data"]
        if (
            str(payment.get("id")) != plan.identity
            and str(payment.get("orderCode")) != plan.identity
        ):
            raise LoiTichHop("invalid_response")
        verified = True
    if identifier == "momo":
        if (
            data.get("orderId") != plan.identity
            or data.get("partnerCode") != plan.body["partnerCode"]
            or data.get("requestId") != plan.body["requestId"]
        ):
            raise LoiTichHop("invalid_response")
        if not isinstance(data.get("resultCode"), int) or isinstance(
            data.get("resultCode"), bool
        ):
            raise LoiTichHop("invalid_response")
    raw = _extract(data, plan.collection)
    if plan.operation == "template_sample":
        if not isinstance(raw, dict) or len(raw) > 100:
            raise LoiTichHop("invalid_response")
        rows = []
        for parameter, value in raw.items():
            if (
                not isinstance(parameter, str)
                or not 1 <= len(parameter) <= 100
                or any(char in parameter for char in "\0\r\n")
                or not isinstance(value, (str, int, float, bool))
            ):
                raise LoiTichHop("invalid_response")
            rows.append(
                {
                    "template_id": plan.identity,
                    "parameter": parameter,
                    "sample_value": value,
                }
            )
    else:
        rows = raw if isinstance(raw, list) else [raw]
    if len(rows) > plan.limit:
        raise LoiTichHop("response_too_large")
    items = [_public_record(row, plan.operation) for row in rows]
    next_arguments = None
    if identifier == "kiotviet":
        total = data.get("total")
        if (
            not isinstance(total, int)
            or isinstance(total, bool)
            or total < len(items)
            or (items and total < plan.offset + len(items))
        ):
            raise LoiTichHop("invalid_response")
        if items and plan.offset + len(items) < total:
            next_arguments = {"limit": plan.limit, "offset": plan.offset + len(items)}
    elif identifier in ("sapo_web", "haravan") and len(items) == plan.limit:
        next_arguments = {"limit": plan.limit, "page": plan.offset + 1}
    elif identifier == "amis_act" and len(items) == plan.limit:
        next_arguments = {"limit": plan.limit, "offset": plan.offset + len(items)}
    elif identifier == "tiktok_display" and plan.operation == "videos":
        content = data["data"]
        if content.get("has_more") is True:
            cursor = content.get("cursor")
            if (
                not isinstance(cursor, int)
                or isinstance(cursor, bool)
                or cursor <= plan.offset
            ):
                raise LoiTichHop("invalid_response")
            next_arguments = {"limit": plan.limit, "cursor": cursor}
    elif identifier == "meta_pages" and plan.operation == "conversations":
        paging = data.get("paging", {})
        cursor = paging.get("cursors", {}).get("after")
        if paging.get("next") and isinstance(cursor, str) and len(cursor) <= 2048:
            # Bỏ URL next của nhà cung cấp; chỉ mang cursor vào route cố định.
            next_arguments = {"limit": plan.limit, "after": cursor}
    encoded_items = json.dumps(items, ensure_ascii=False)
    if any(
        isinstance(value, str) and len(value) >= 6 and value in encoded_items
        for value in credentials.values()
    ):
        raise LoiTichHop("invalid_response")
    return {
        "items": items,
        "next_arguments": next_arguments,
        "signature_verified": verified,
        "provider_code": data.get("resultCode")
        if identifier == "momo"
        else data.get("code"),
        "external_write_performed": False,
        "settlement_applied": False,
    }
