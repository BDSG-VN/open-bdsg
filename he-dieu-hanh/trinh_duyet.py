"""Authenticated gateway to the separate browser worker; no browser port is public."""

import json
import os
import socket
import contextvars
import hashlib
import re
from contextlib import contextmanager


def exchange(data):
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
    return json.loads(reply)


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
    def __init__(self, kho, tasks, transport=None):
        self.kho, self.tasks = kho, tasks
        self.transport = transport or exchange
        self.approved = contextvars.ContextVar("bdsg_browser_approval", default=None)

    @staticmethod
    def validate_action(args):
        if not isinstance(args, dict) or set(args) - {
            "task_id",
            "action",
            "node",
            "nonce",
            "text",
        }:
            raise ValueError("Tham số thao tác không hợp lệ")
        if (
            args.get("action") not in ("click", "fill", "select", "key")
            or type(args.get("node")) is not int
            or not 0 <= args["node"] < 80
            or not isinstance(args.get("nonce"), str)
            or not 1 <= len(args["nonce"]) <= 100
        ):
            raise ValueError("Cần chọn thành phần từ quan sát hiện tại")
        if (
            not isinstance(args.get("text", ""), str)
            or len(args.get("text", "")) > 4000
        ):
            raise ValueError("Nội dung nhập vượt giới hạn")
        if args["action"] == "key" and args.get("text") not in (
            "Enter",
            "Tab",
            "Escape",
            "ArrowDown",
            "ArrowUp",
        ):
            raise ValueError("Phím chưa hỗ trợ")

    def _request(self, actor, task, data):
        data = {
            **data,
            "owner": actor["id"],
            "task_id": task["id"] + ":" + str(task["run"]),
            "hosts": task["browser_hosts"],
        }
        reply = self.transport(data)
        if not reply.get("ok"):
            raise ValueError(
                "Phiên hoặc biểu mẫu đã thay đổi; cần quan sát và tạo đề xuất mới"
            )
        return reply["result"]

    def inspect(self, actor, args, image=False):
        self.validate_action(args)
        task = self.tasks.detail(actor, args.get("task_id", ""))
        if (
            task["owner"] != actor["id"]
            or not task.get("browser_hosts")
            or task.get("cancel_requested")
        ):
            raise PermissionError("Ngoài phạm vi trình duyệt của tác vụ")
        result = self._request(
            actor,
            task,
            {
                "action": "inspect",
                "intent": args["action"],
                "node": args["node"],
                "nonce": args["nonce"],
                "image": image,
            },
        )
        target = result.get("target")
        if (
            not isinstance(target, dict)
            or not re.fullmatch("[a-f0-9]{64}", str(target.get("signature", "")))
            or len(json.dumps(target).encode()) > 4096
        ):
            raise ValueError("Không có bằng chứng thành phần hợp lệ")
        return result

    def _digest(self, actor, args):
        task = self.tasks.detail(actor, args.get("task_id", ""))
        return hashlib.sha256(
            json.dumps(
                [actor["id"], task["run"], args],
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            ).encode()
        ).hexdigest()

    @contextmanager
    def authorization(self, actor, args, signature):
        token = self.approved.set(
            {"digest": self._digest(actor, args), "signature": signature}
        )
        try:
            yield
        finally:
            self.approved.reset(token)

    def approved_action(self, actor, args):
        self.validate_action(args)
        permit = self.approved.get()
        if not permit or permit["digest"] != self._digest(actor, args):
            raise PermissionError("Cần phê duyệt đúng nội dung trước khi thực hiện")
        task = self.tasks.detail(actor, args["task_id"])
        if (
            task.get("cancel_requested")
            or task["owner"] != actor["id"]
            or not task.get("browser_hosts")
        ):
            raise PermissionError("Tác vụ đã dừng hoặc ngoài phạm vi")
        result = self._request(
            actor,
            task,
            {
                **args,
                "action": "approved",
                "intent": args["action"],
                "expected_target": permit["signature"],
            },
        )
        self.kho.su_kien(actor["id"], "thuc-hien-browser-da-duyet", task["id"])
        return result

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
        result = self.transport(data)
        if not result.get("ok"):
            raise ValueError(
                "Trình duyệt chưa thực hiện được; kiểm phiên và phạm vi đã cấp"
            )
        self.kho.su_kien(actor["id"], "trinh-duyet-" + action, task["id"])
        return result["result"]
