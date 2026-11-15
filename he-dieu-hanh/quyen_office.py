"""Khóa phiên chung cùng giao dịch thu hồi quyền; ngắt mạng sau commit."""

import http.client
import json
import os
import time

from chu_ky_office import sign


def khoa_phien(db, identity=None, project_id=None):
    if not db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='office_editors'"
    ).fetchone():
        return []
    rows = db.execute(
        "SELECT DISTINCT e.key FROM office_editors e JOIN office_files f ON f.id=e.file_id "
        "JOIN office_editor_members m ON m.key=e.key WHERE e.state='active' "
        "AND (? IS NULL OR m.actor=?) AND (? IS NULL OR f.project_id=?)",
        (identity, identity, project_id, project_id),
    ).fetchall()
    keys = [row[0] for row in rows]
    for key in keys:
        db.execute(
            "UPDATE office_editors SET state='revoked',pending=NULL WHERE key=?", (key,)
        )
    return keys


def ngat_phien(keys, secret=None):
    secret = secret or os.environ.get("BDSG_OFFICE_JWT_SECRET", "")
    if not secret:
        return
    for key in keys:
        payload = {
            "c": "drop",
            "key": key,
            "operation": "command",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        }
        connection = http.client.HTTPConnection("127.0.0.1", 8088, timeout=3)
        try:
            connection.request(
                "POST",
                "/command",
                json.dumps({"token": sign(payload, secret)}),
                {"Content-Type": "application/json"},
            )
            connection.getresponse().read(8192)
        except (OSError, http.client.HTTPException):
            # Kho đã khóa mọi lần ghi; lỗi mạng không mở lại phiên bị thu hồi.
            pass
        finally:
            connection.close()
