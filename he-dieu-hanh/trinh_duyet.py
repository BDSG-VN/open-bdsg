"""Authenticated gateway to the separate browser worker; no browser port is public."""

import json
import os
import socket


def revoke_browser(owner, task_id=None):
    path = os.environ.get("BDSG_BROWSER_SOCKET", "/run/bdsg-browser/worker.sock")
    if not os.path.exists(path):
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(path)
            s.sendall(
                json.dumps(
                    {
                        "owner": owner,
                        "task_id": task_id,
                        "action": "revoke-task" if task_id else "revoke-owner",
                    }
                ).encode()
                + b"\n"
            )
            s.recv(2048)
    except (OSError, ValueError):
        pass


class TrinhDuyet:
    def __init__(self, kho, tasks):
        self.kho, self.tasks = kho, tasks

    def call(self, actor, args, manual=False):
        task = self.tasks.detail(actor, args.get("task_id", ""))
        if task["owner"] != actor["id"] or not task.get("browser_hosts"):
            raise PermissionError("Tác vụ chưa cấp phạm vi trình duyệt")
        if task.get("cancel_requested") and args.get("action") != "close":
            raise ValueError("Tác vụ đã dừng")
        action = args.get("action", "observe")
        if action not in (
            ("open", "observe", "close", "link", "click", "fill", "key", "select")
            if manual
            else ("open", "observe", "close", "link")
        ):
            raise PermissionError(
                "Agent chỉ đọc và mở liên kết; thao tác biểu mẫu do người dùng tiếp quản"
            )
        data = {
            k: args[k]
            for k in ("url", "action", "nonce", "node", "text", "image")
            if k in args
        }
        data.update(
            owner=actor["id"],
            task_id=task["id"] + ":" + str(task["run"]),
            hosts=task["browser_hosts"],
        )
        raw = json.dumps(data, ensure_ascii=False).encode()
        if len(raw) > 60000:
            raise ValueError("Thao tác quá lớn")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(40)
            s.connect(
                os.environ.get("BDSG_BROWSER_SOCKET", "/run/bdsg-browser/worker.sock")
            )
            s.sendall(raw + b"\n")
            with s.makefile("rb") as stream:
                reply = stream.readline(2 * 1024 * 1024)
        result = json.loads(reply)
        if not result.get("ok"):
            raise ValueError(
                "Trình duyệt chưa thực hiện được; kiểm phiên và phạm vi đã cấp"
            )
        self.kho.su_kien(actor["id"], "trinh-duyet-" + action, task["id"])
        return result["result"]
