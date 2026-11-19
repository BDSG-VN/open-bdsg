"""JWT HS256 của Docs, tách dữ liệu đã ký khỏi JSON gửi kèm."""

import base64
import hashlib
import hmac
import json
import time


def b64(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def sign(payload, secret):
    parts = [
        b64(b'{"alg":"HS256","typ":"JWT"}'),
        b64(json.dumps(payload, separators=(",", ":")).encode()),
    ]
    raw = ".".join(parts)
    return raw + "." + b64(hmac.digest(secret.encode(), raw.encode(), "sha256"))


def verify(token, secret, operation):
    try:
        if not isinstance(token, str) or len(token) > 24000 or not secret:
            raise ValueError
        header, body, signature = token.split(".")
        expected = b64(
            hmac.digest(secret.encode(), (header + "." + body).encode(), hashlib.sha256)
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        decode = lambda part: json.loads(
            base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))
        )
        algorithm, claims = decode(header), decode(body)
        if algorithm.get("alg") != "HS256" or not isinstance(claims, dict):
            raise ValueError
        now = time.time()
        if type(claims.get("exp")) not in (int, float) or claims["exp"] < now - 30:
            raise ValueError
        if claims.get("nbf", 0) > now + 30 or claims.get("iat", 0) > now + 30:
            raise ValueError
        if claims.get("operation", operation) != operation:
            raise ValueError
        payload = claims.get("payload", claims)
        if not isinstance(payload, dict):
            raise TypeError
        return payload
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise PermissionError("Chữ ký Office không hợp lệ") from None
