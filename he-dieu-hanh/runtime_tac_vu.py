"""Python job runner with filesystem/network/PID namespaces and syscall restrictions."""

import json
import os
import secrets
import signal
import stat
import subprocess
import tempfile
import threading
import time
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
        if len(task['artifacts'])>=80 or sum(len(a.get('content','').encode()) for a in task['artifacts'])>=8*1024*1024:
            raise ValueError('Tác vụ đạt hạn tệp kết quả; tạo công việc mới nếu cần')
        code = args.get("code")
        if not isinstance(code, str) or not 1 <= len(code) <= 16000:
            raise ValueError("Mã Python cần 1–16000 ký tự")
        if not self.capacity.acquire(blocking=False):
            raise ValueError("Vùng thực thi đang bận")
        try:
            return self._run(actor, task, code)
        finally:
            self.capacity.release()

    def _run(self, actor, task, code):
        helper = Path(__file__).with_name("python_co_lap.py").resolve()
        # TemporaryDirectory removes only the newly allocated private task directory.
        with tempfile.TemporaryDirectory(prefix="bdsg-job-") as directory:
            root = Path(directory)
            os.chmod(root, 0o700)
            work = root / "work"
            work.mkdir(mode=0o700)
            output = root / "stdout"
            error = root / "stderr"
            command = command_for(work)
            deadline = time.monotonic() + 15
            with output.open("wb") as out, error.open("wb") as err:
                p = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=out,
                    stderr=err,
                    start_new_session=True,
                )
                try:
                    p.stdin.write(
                        json.dumps(
                            {"code": code, "documents": task.get("documents", [])},
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
                            os.killpg(p.pid, signal.SIGKILL)
                            p.wait()
                            raise ValueError(
                                "Đã dừng mã do hủy tác vụ hoặc hết 15 giây"
                            )
                        time.sleep(0.05)
                finally:
                    if p.poll() is None:
                        os.killpg(p.pid, signal.SIGKILL)
                        p.wait()
            # Never follow user-created symlinks, including /proc magic links.
            artifacts = []
            total = 0
            if p.returncode == 0:
                for file in sorted(work.iterdir()):
                    if file.name.startswith("input-") or len(artifacts) >= 8:
                        continue
                    fd = None
                    try:
                        fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                        info = os.fstat(fd)
                        if (
                            not stat.S_ISREG(info.st_mode)
                            or info.st_size > 256000
                            or total + info.st_size > 512000
                        ):
                            continue
                        with os.fdopen(fd, "rb") as f:
                            fd = None
                            raw = f.read(256001)
                        content = raw.decode("utf-8")
                        if "\x00" in content:
                            continue
                        total += len(raw)
                        artifacts.append(
                            {
                                "id": secrets.token_hex(8),
                                "name": file.name[:100],
                                "title": "Tệp do Python tạo",
                                "mime_type": "text/plain",
                                "content": content,
                                "created": time.time(),
                                "run": task["run"],
                            }
                        )
                    except (OSError, UnicodeDecodeError):
                        continue
                    finally:
                        if fd is not None:
                            os.close(fd)
            with self.tasks.lock:
                current = self.tasks.detail(actor, task["id"])
                current["artifacts"] += artifacts
                self.tasks._event(
                    current,
                    "python-result",
                    "Đã thực thi Python trong vùng riêng.",
                    ok=p.returncode == 0,
                    artifact_count=len(artifacts),
                )
                self.tasks._save(current)
            self.kho.su_kien(actor["id"], "chay-python", task["id"])
            return {
                "ok": p.returncode == 0,
                "stdout": output.read_bytes()[:16000].decode("utf-8", "replace"),
                "error": None
                if p.returncode == 0
                else "Mã lỗi hoặc bị giới hạn; không mở quyền máy chủ.",
                "artifacts": [{"id": a["id"], "name": a["name"]} for a in artifacts],
            }
