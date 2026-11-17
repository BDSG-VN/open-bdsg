"""Đóng gói bản sao đã kiểm và mã hóa qua age 1.3.2; không gửi ra mạng.

Không tạo/đọc khóa riêng. Không lưu tar rõ xuống đĩa. Chỉ công bố tệp mới
sau khi age thành công; không ghi đè và chỉ dọn tệp .part do lượt này tạo.
"""

import argparse
import hashlib
import io
import json
import math
import os
import re
import sqlite3
import stat
import subprocess
import sys
import tarfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "he-dieu-hanh"))
from sao_luu_he_thong import digest, verify


AGE_VERSION = "v1.3.2"


def _path(path):
    path = Path(os.path.abspath(path))
    for component in (path, *path.parents):
        if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
            raise ValueError("Không nhận đường dẫn liên kết")
    return path


def _regular(path):
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("Chỉ nhận tệp thường")


def _recipients(path):
    _regular(path)
    if path.stat().st_size > 65536:
        raise ValueError("Tệp người nhận quá lớn")
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    # Chỉ native recipients: plugin age có thể chạy chương trình ngoài/mạng.
    # age tự kiểm Bech32 và tính hợp lệ; ở đây chỉ chặn các loại không được duyệt.
    if not lines or len(lines) > 32 or any(not re.fullmatch(
        r"(?:age1[023456789acdefghjklmnpqrstuvwxyz]{58}|age1pq1[023456789acdefghjklmnpqrstuvwxyz]{32,4096})", line
    ) for line in lines):
        raise ValueError("Chỉ nhận khóa công khai native age")


class _HashedReader:
    def __init__(self, stream):
        self.stream, self.hash, self.count = stream, hashlib.sha256(), 0

    def read(self, size=-1):
        value = self.stream.read(size)
        self.hash.update(value)
        self.count += len(value)
        return value


def _tar_member(archive, name, size, stream):
    info = tarfile.TarInfo(name)
    info.size, info.mode, info.mtime = size, 0o600, 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    archive.addfile(info, stream)


def _archive(bundle, manifest, stream):
    with tarfile.open(mode="w|", fileobj=stream, format=tarfile.USTAR_FORMAT) as archive:
        # Manifest đã kiểm trong bộ nhớ: không đóng gói tệp bị đổi sau verify.
        content = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
        _tar_member(archive, "manifest.json", len(content), io.BytesIO(content))
        for name, expected in sorted(manifest["files"].items()):
            path = _path(bundle / name)
            _regular(path)
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
            with os.fdopen(os.open(path, flags), "rb") as original:
                info = os.fstat(original.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != expected["bytes"]:
                    raise ValueError("Gói đổi khi đóng gói")
                source = _HashedReader(original)
                _tar_member(archive, name, expected["bytes"], source)
                if source.count != expected["bytes"] or source.hash.hexdigest() != expected["sha256"]:
                    raise ValueError("Gói đổi khi đóng gói")


def _stop(process):
    try:
        process.kill()
    except OSError:
        pass


def encrypt_bundle(bundle, destination, recipients_file, age_executable, timeout=300):
    """Trả metadata ciphertext; lỗi trả ngoại lệ để CLI lọc, không ghi đè."""
    started = time.perf_counter()
    bundle, destination, recipients_file, age_executable = map(
        _path, (bundle, destination, recipients_file, age_executable))
    if not math.isfinite(timeout) or timeout <= 0 or destination.suffix != ".age":
        raise ValueError("Đích phải là tệp .age mới")
    if destination == bundle or bundle in destination.parents:
        raise ValueError("Đích phải ở ngoài gói")
    if os.path.lexists(destination):
        raise FileExistsError("Không ghi đè")
    _regular(age_executable)
    _recipients(recipients_file)
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    version = subprocess.run([str(age_executable), "--version"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=True, **options)
    if version.stdout.strip() != AGE_VERSION.encode("ascii"):
        raise ValueError("Cần age v1.3.2 đã được xác minh nguồn")
    manifest = verify(bundle)
    partial = destination.with_name(destination.name + ".part")
    created = False
    process = timer = None
    try:
        with partial.open("xb") as encrypted:
            created = True
            os.chmod(partial, 0o600)
            process = subprocess.Popen([str(age_executable), "--encrypt", "--recipients-file",
                str(recipients_file)], stdin=subprocess.PIPE, stdout=encrypted,
                stderr=subprocess.DEVNULL, **options)
            timer = threading.Timer(timeout, _stop, args=(process,))
            timer.daemon = True
            timer.start()
            try:
                _archive(bundle, manifest, process.stdin)
            finally:
                process.stdin.close()
            if process.wait(timeout=timeout) != 0:
                raise ValueError("age thất bại")
            timer.cancel()
            encrypted.flush()
            os.fsync(encrypted.fileno())
        if partial.stat().st_size == 0:
            raise ValueError("age không tạo dữ liệu")
        with partial.open("rb") as stream:
            if stream.read(22) != b"age-encryption.org/v1\n":
                raise ValueError("Đầu ra không phải định dạng age")
        result = {"format": 1, "status": "encrypted", "age_version": AGE_VERSION,
            "observed_at": time.time(), "duration_seconds": round(time.perf_counter() - started, 6),
            "encrypted_bytes": partial.stat().st_size, "encrypted_sha256": digest(partial),
            "backup_files": len(manifest["files"]), "offsite": {"configured": False},
            "decryption_verified": False}
        # link là thao tác tạo tên mới nguyên tử, thất bại nếu đích xuất hiện.
        # Không dùng replace/rename vốn có thể ghi đè trên POSIX.
        os.link(partial, destination)
        return result
    finally:
        if timer is not None:
            timer.cancel()
        try:
            if process is not None and process.poll() is None:
                _stop(process)
                process.wait(timeout=10)
        finally:
            if created:
                partial.unlink()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--recipients-file", type=Path, required=True)
    parser.add_argument("--age-executable", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    try:
        report = encrypt_bundle(args.bundle, args.destination, args.recipients_file,
                                args.age_executable, args.timeout)
    except (OSError, ValueError, sqlite3.Error, TimeoutError, KeyError, TypeError,
            AttributeError, RecursionError, subprocess.SubprocessError):
        print(json.dumps({"format": 1, "status": "failed", "observed_at": time.time(),
                          "offsite": {"configured": False}}))
        return 1
    print(json.dumps(report, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
