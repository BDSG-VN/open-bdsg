"""Chữ ký theo từng hợp đồng; không dùng công thức của cổng này cho cổng khác."""

import hashlib
import hmac
import json
import re

from vn_transport import LoiTichHop


def _js_value(value):
    if value is None or value in ("null", "undefined"):
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    return str(value)


def payos_preimage(data):
    if not isinstance(data, dict) or any(not isinstance(key, str) for key in data):
        raise LoiTichHop("invalid_response")
    return "&".join(key + "=" + _js_value(data[key]) for key in sorted(data))


def verify_payos(data, signature, checksum_key):
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature):
        raise LoiTichHop("invalid_response")
    expected = hmac.new(
        checksum_key.encode(), payos_preimage(data).encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise LoiTichHop("invalid_response")


def momo_query_signature(partner_code, order_id, access_key, secret_key):
    # Thứ tự/các trường của query khác IPN; requestId không thuộc preimage query.
    raw = (
        "accessKey="
        + access_key
        + "&orderId="
        + order_id
        + "&partnerCode="
        + partner_code
    )
    return hmac.new(secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()
