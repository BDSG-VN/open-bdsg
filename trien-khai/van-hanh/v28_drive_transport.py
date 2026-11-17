"""Vận chuyển ciphertext age bằng cấu hình rclone do quản trị cấp riêng."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import threading
import time
import uuid


class TransportError(ValueError):
    """Lỗi đã lọc, được phép hiện trong báo cáo vận hành."""


class _BoundedOutput:
    def __init__(self, stream, limit):
        self.stream, self.remaining = stream, limit

    def write(self, data):
        if len(data) > self.remaining:
            raise TransportError("Đầu ra từ xa vượt giới hạn")
        self.remaining -= len(data)
        return self.stream.write(data)


def _regular(value):
    path = Path(value)
    if not path.is_absolute():
        raise TransportError("Cần đường dẫn tuyệt đối")
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
           for p in (path, *path.parents)):
        raise TransportError("Không nhận liên kết")
    if not stat.S_ISREG(path.stat().st_mode):
        raise TransportError("Cần tệp thường đã có")
    return path


def _hash(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def _run(argv, output, timeout):
    # Biến RCLONE_* có thể thay remote, token, endpoint hoặc bật log bí mật.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("RCLONE_")}
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    process = timer = None
    expired = threading.Event()
    try:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, shell=False, env=env, **options)

        def stop():
            expired.set()
            try:
                process.kill()
            except OSError:
                pass

        timer = threading.Timer(timeout, stop)
        timer.daemon = True
        timer.start()
        while block := process.stdout.read(65536):
            output.write(block)
        code = process.wait(timeout=timeout)
        if expired.is_set():
            raise TransportError("Vận chuyển quá thời hạn")
        if code:
            raise TransportError("rclone thất bại; chưa xác minh offsite")
    except (OSError, subprocess.SubprocessError):
        raise TransportError("rclone thất bại; chưa xác minh offsite") from None
    finally:
        if timer:
            timer.cancel()
        if process:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdout.close()


def upload_age(source, *, config, executable, remote, prefix, allowed_destination,
               timeout=300, runner=_run):
    """Upload mới rồi đọc lại toàn bộ; chỉ trả biên nhận sau khi so byte/hash.

    runner là ranh giới tiến trình: (argv, writable_binary_stream, timeout).
    Không nhận biên nhận do runner khai báo; dữ liệu đọc lại quyết định kết quả.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        raise TransportError("Thời hạn không hợp lệ")
    if not isinstance(remote, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,63}", remote):
        raise TransportError("Remote không hợp lệ")
    if not isinstance(prefix, str) or len(prefix) > 240 or not re.fullmatch(
            r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", prefix):
        raise TransportError("Thư mục từ xa không hợp lệ")
    target = remote + ":" + prefix
    if target != allowed_destination:
        raise TransportError("Đích ngoài danh sách được phép")
    source, config, executable = map(_regular, (source, config, executable))
    if source.suffix != ".age" or not 22 < source.stat().st_size <= 8 * 1024**3:
        raise TransportError("Chỉ nhận ciphertext .age")
    started = time.monotonic()
    base = [str(executable), "--config", str(config), "--ask-password=false",
            "--log-level", "ERROR", "--stats", "0", "--retries", "1"]

    def invoke(args, destination, limit=1024 * 1024):
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise TransportError("Vận chuyển quá thời hạn")
        with destination.open("wb") as stream:
            runner(base + args, _BoundedOutput(stream, limit), remaining)

    with tempfile.TemporaryDirectory(prefix="bdsg-drive-") as directory:
        private = Path(directory)
        os.chmod(private, 0o700)
        snapshot, listing, readback = (private / name for name in ("upload.age", "list.json", "readback.age"))
        invoke(["listremotes", "--name", remote, "--type", "drive", "--source", "file", "--exact"], listing)
        if listing.read_bytes().strip() != (remote + ":").encode("ascii"):
            raise TransportError("Remote không phải Google Drive trong cấu hình đã cấp")
        # Snapshot giữ đúng ciphertext đã băm dù nguồn bị đổi trong lúc tải lên.
        with source.open("rb") as original, snapshot.open("xb") as encrypted:
            copied = 0
            while block := original.read(1024 * 1024):
                copied += len(block)
                if copied > 8 * 1024**3:
                    raise TransportError("Ciphertext vượt giới hạn")
                encrypted.write(block)
        os.chmod(snapshot, 0o600)
        with snapshot.open("rb") as stream:
            if stream.read(22) != b"age-encryption.org/v1\n":
                raise TransportError("Thiếu đầu định dạng age")
        size, digest = _hash(snapshot)
        if size > 8 * 1024**3:
            raise TransportError("Ciphertext vượt giới hạn")
        name = digest + "-" + uuid.uuid4().hex + ".age"
        destination = target + "/" + name

        def objects():
            invoke(["lsjson", target, "--files-only", "--max-depth", "1"], listing)
            if listing.stat().st_size > 1024 * 1024:
                raise TransportError("Danh sách đích vượt giới hạn; cần chia thư mục")
            try:
                items = json.loads(listing.read_bytes())
                if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                    raise ValueError()
                return [item for item in items if item.get("Name") == name]
            except (ValueError, UnicodeError):
                raise TransportError("Metadata từ xa không hợp lệ") from None

        if objects():
            raise TransportError("Đối tượng đã tồn tại; không ghi đè")
        invoke(["copyto", str(snapshot), destination, "--immutable", "--ignore-existing"], listing)
        found = objects()
        if len(found) != 1 or type(found[0].get("Size")) is not int or found[0]["Size"] != size:
            raise TransportError("Metadata kích thước không khớp")
        invoke(["cat", destination], readback, size + 1)
        if _hash(readback) != (size, digest):
            raise TransportError("Đọc lại không khớp ciphertext")
        return {"format": 1, "status": "verified", "destination": "google-drive",
                "object": name, "encrypted_bytes": size, "encrypted_sha256": digest,
                "verification": "download-sha256", "observed_at": time.time(),
                "decryption_verified": False}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("source", "config", "executable", "remote", "prefix", "allowed-destination"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--timeout", type=float, default=300)
    args = vars(parser.parse_args())
    try:
        result = upload_age(**args)
    except (OSError, ValueError, TypeError):
        print(json.dumps({"status": "failed", "error": "Chưa xác minh bản sao offsite"}))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
