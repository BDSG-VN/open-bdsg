"""Đọc biên nhận bản sao ngoài máy, không đọc chứng thư hoặc gọi dịch vụ ngoài."""

import json
import math
import os
import re
import stat
import time
from pathlib import Path

FIELDS = frozenset(("format", "status", "verified_at", "snapshot_at",
    "encrypted_sha256", "encrypted_bytes", "destination", "verification"))


def _number(value):
    return type(value) in (float, int) and math.isfinite(value) and value >= 0


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Trùng trường")
        result[key] = value
    return result


def read_offsite_status(path, now=None, max_age_seconds=172800):
    """Biên nhận chỉ chứng minh một bản đã kiểm; không suy ra lịch tự động."""
    unknown = {"status": "unknown", "reason": "not_configured",
               "automatic_upload": "not_verified"}
    if not path:
        return unknown
    now = time.time() if now is None else now
    try:
        if not _number(now) or not _number(max_age_seconds):
            raise ValueError("Mốc thời gian không hợp lệ")
        path = Path(os.path.abspath(path))
        if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
               for p in (path, *path.parents)):
            raise ValueError("Không nhận liên kết")
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError("Chỉ nhận tệp thường")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 8192:
                raise ValueError("Biên nhận không hợp lệ")
            raw = stream.read(8193)
        if len(raw) > 8192:
            raise ValueError("Biên nhận quá lớn")
        report = json.loads(raw, object_pairs_hook=_object)
        if not isinstance(report, dict) or set(report) != FIELDS:
            raise ValueError("Sai schema")
        if type(report["format"]) is not int or report["format"] != 1:
            raise ValueError("Sai phiên bản")
        if report["status"] != "verified" or report["destination"] != "google-drive":
            raise ValueError("Chưa xác minh")
        if report["verification"] not in ("download-sha256", "download-sha256-and-decrypt"):
            raise ValueError("Chưa kiểm tải lại")
        if not all(_number(report[name]) for name in ("snapshot_at", "verified_at")):
            raise ValueError("Mốc thời gian không hợp lệ")
        if not report["snapshot_at"] <= report["verified_at"] <= now:
            raise ValueError("Mốc thời gian không hợp lệ")
        if type(report["encrypted_bytes"]) is not int or not 0 < report["encrypted_bytes"] <= 2**40:
            raise ValueError("Kích thước không hợp lệ")
        if not isinstance(report["encrypted_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", report["encrypted_sha256"]):
            raise ValueError("Thiếu checksum")
        verification_age = now - report["verified_at"]
        backup_age = now - report["snapshot_at"]
        # Một lần tải lại bản quá cũ không làm tuổi bản sao trở thành mới.
        return {"status": "verified" if backup_age <= max_age_seconds else "stale",
                "destination": "google-drive", "verified_at": report["verified_at"],
                "verification_age_seconds": round(verification_age, 3),
                "backup_age_seconds": round(backup_age, 3),
                "encrypted_bytes": report["encrypted_bytes"],
                "decryption_verified": report["verification"] == "download-sha256-and-decrypt",
                "automatic_upload": "not_verified"}
    except OSError:
        return dict(unknown, reason="unavailable")
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return dict(unknown, reason="invalid")
