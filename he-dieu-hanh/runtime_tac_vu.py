"""Bounded namespace runner; returns validated text, never reads job paths on host."""

import json
import os
import secrets
import signal
import subprocess
import tempfile
import threading
import time
import re
from pathlib import Path
from co_lap import command_for


class RuntimeTacVu:
    def __init__(self, kho, tasks):
        self.kho, self.tasks = kho, tasks
        self.capacity = threading.BoundedSemaphore(1)

    def run(self, actor, args):
        task = self.tasks.detail(actor, args.get("task_id", ""))
        if task["owner"] != actor["id"] or not task.get("allow_python"):
            raise PermissionError("Tác vụ chưa cấp quyền chạy Python")
        if (
            len(task["artifacts"]) >= 80
            or sum(len(a.get("content", "").encode()) for a in task["artifacts"])
            >= 8 * 1024 * 1024
        ):
            raise ValueError("Tác vụ đạt hạn tệp kết quả")
        code = args.get("code")
        output_names = args.get(
            "output_names", ["ket-qua.csv", "ket-qua.txt", "ket-qua.md"]
        )
        if (
            not isinstance(output_names, list)
            or len(output_names) > 8
            or any(
                not isinstance(n, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", n)
                or n.startswith("input-")
                for n in output_names
            )
            or len(set(output_names)) != len(output_names)
        ):
            raise ValueError("Chọn tối đa 8 tên tệp kết quả, không chứa đường dẫn")
        if not isinstance(code, str) or not 1 <= len(code) <= 16000:
            raise ValueError("Mã Python cần 1–16000 ký tự")
        if task.get("cancel_requested"):
            raise ValueError("Tác vụ đã dừng; cần tiếp tục bằng lượt mới")
        if not self.capacity.acquire(blocking=False):
            raise ValueError("Vùng thực thi đang bận")
        try:
            with self.tasks.lock:
                current = self.tasks.detail(actor, task["id"])
                current["runtime_running"] = True
                self.tasks._save(current)
            return self._run(actor, task, code, output_names)
        finally:
            with self.tasks.lock:
                current = self.tasks._load(task["id"])
                current["runtime_running"] = False
                if (
                    current.get("cancel_requested")
                    and current["status"] == "cancelling"
                ):
                    current["status"] = "cancelled"
                self.tasks._save(current)
            self.capacity.release()

    def _run(self, actor, task, code, output_names):
        with tempfile.TemporaryDirectory(prefix="bdsg-result-") as directory:
            root = Path(directory)
            output = root / "stdout"
            error = root / "stderr"
            deadline = time.monotonic() + 15
            with output.open("wb") as out, error.open("wb") as err:
                p = subprocess.Popen(
                    command_for(),
                    stdin=subprocess.PIPE,
                    stdout=out,
                    stderr=err,
                    start_new_session=True,
                )
                try:
                    p.stdin.write(
                        json.dumps(
                            {
                                "code": code,
                                "documents": task.get("documents", []),
                                "output_names": output_names,
                            },
                            ensure_ascii=False,
                        ).encode()
                    )
                    p.stdin.close()
                    while p.poll() is None:
                        current = self.tasks.detail(actor, task["id"])
                        if (
                            current.get("cancel_requested")
                            or time.monotonic() > deadline
                        ):
                            raise ValueError(
                                "Đã dừng mã do hủy tác vụ hoặc hết 15 giây"
                            )
                        time.sleep(0.05)
                finally:
                    if p.poll() is None:
                        os.killpg(p.pid, signal.SIGKILL)
                        p.wait()
            result = {"ok": False, "stdout": "", "artifacts": []}
            if p.returncode == 0:
                try:
                    value = json.loads(output.read_bytes()[:1048576])
                    if (
                        not isinstance(value, dict)
                        or type(value.get("ok")) is not bool
                        or not isinstance(value.get("stdout"), str)
                        or not isinstance(value.get("artifacts"), list)
                    ):
                        raise ValueError()
                    result = value
                except (ValueError, TypeError):
                    pass
            artifacts = []
            total = 0
            for value in result["artifacts"][:8]:
                if (
                    not isinstance(value, dict)
                    or not isinstance(value.get("name"), str)
                    or not isinstance(value.get("content"), str)
                ):
                    continue
                size = len(value["content"].encode())
                if size > 256000 or total + size > 512000:
                    continue
                total += size
                artifacts.append(
                    {
                        "id": secrets.token_hex(8),
                        "name": value["name"][:100],
                        "title": "Tệp do Python tạo",
                        "mime_type": "text/plain",
                        "content": value["content"],
                        "created": time.time(),
                        "run": task["run"],
                    }
                )
            with self.tasks.lock:
                current = self.tasks.detail(actor, task["id"])
                if current.get("cancel_requested"):
                    raise ValueError("Tác vụ đã dừng")
                current["artifacts"] += artifacts
                self.tasks._event(
                    current,
                    "python-result",
                    "Đã thực thi Python trong vùng riêng.",
                    ok=result["ok"],
                    artifact_count=len(artifacts),
                )
                self.tasks._save(current)
            self.kho.su_kien(actor["id"], "chay-python", task["id"])
            return {
                "ok": result["ok"],
                "stdout": result["stdout"][:16000],
                "error": None
                if result["ok"]
                else "Mã lỗi hoặc bị giới hạn; không mở quyền máy chủ.",
                "artifacts": [{"id": a["id"], "name": a["name"]} for a in artifacts],
            }
