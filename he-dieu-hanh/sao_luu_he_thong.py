"""Snapshot SQLite đang chạy, kiểm SHA và phục hồi vào thư mục mới ngoài web.

Gói chứa dữ liệu riêng và có thể có bí mật. Chỉ dùng cục bộ bởi người vận hành;
không cấp qua HTTP/MCP, không tự ghi đè kho đang hoạt động.
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import time
from contextlib import closing
from pathlib import Path

DATA_FILES = (
    "model-private.json",
    "connections-private.json",
    "chatgpt-registration.json",
    "web-status.json",
)
SECRET_FILES = ("gateway.env", "google-client.json", "google-vault.key", "office.env")
ALLOWED = {
    "data/van-hanh.db",
    *("data/" + n for n in DATA_FILES),
    *("secrets/" + n for n in SECRET_FILES),
}


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def private_copy(source, target):
    if source.is_symlink() or not stat.S_ISREG(source.stat().st_mode):
        raise ValueError("Không sao lưu liên kết hoặc tệp đặc biệt")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with source.open("rb") as original, target.open("xb") as output:
        os.chmod(target, 0o600)
        shutil.copyfileobj(original, output, 1024 * 1024)
        output.flush()
        os.fsync(output.fileno())


def verify(bundle):
    bundle = Path(bundle)
    if bundle.is_symlink() or (bundle / "manifest.json").is_symlink():
        raise ValueError("Gói sao lưu không hợp lệ")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest.get("files", {})
    if (
        manifest.get("format") != 1
        or not isinstance(entries, dict)
        or "data/van-hanh.db" not in entries
        or set(entries) - ALLOWED
    ):
        raise ValueError("Manifest không hợp lệ")
    actual = set()
    for path in bundle.rglob("*"):
        if path.is_symlink():
            raise ValueError("Gói có liên kết không được phép")
        if path.is_file() and path.relative_to(bundle).as_posix() != "manifest.json":
            actual.add(path.relative_to(bundle).as_posix())
    if actual != set(entries):
        raise ValueError("Gói thiếu hoặc thừa tệp")
    for name, expected in entries.items():
        path = bundle / name
        if (
            path.stat().st_size != expected["bytes"]
            or digest(path) != expected["sha256"]
        ):
            raise ValueError("Dấu kiểm sao lưu không khớp")
    with closing(
        sqlite3.connect(
            (bundle / "data/van-hanh.db").resolve().as_uri() + "?mode=ro&immutable=1",
            uri=True,
        )
    ) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Cơ sở dữ liệu sao lưu bị lỗi")
    return manifest


def backup(data, destination, secrets_dir=None):
    data, destination = Path(data).resolve(), Path(destination).resolve()
    if destination == data or data in destination.parents:
        raise ValueError("Bản sao phải nằm ngoài kho nguồn")
    if (data / "van-hanh.db").is_symlink():
        raise ValueError("Không nhận CSDL liên kết")
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    folder = destination / "data"
    folder.mkdir(mode=0o700)
    db_path = folder / "van-hanh.db"
    db_path.touch(mode=0o600, exist_ok=False)
    # Giu goi do de dieu tra, khong tu xoa du lieu.
    with (
        closing(
            sqlite3.connect(
                (data / "van-hanh.db").as_uri() + "?mode=ro", uri=True, timeout=5
            )
        ) as source,
        closing(sqlite3.connect(db_path)) as target,
    ):
        deadline = time.monotonic() + 120

        def progress(*_):
            if time.monotonic() > deadline:
                raise TimeoutError("Quá thời gian sao lưu")

        source.backup(target, pages=256, progress=progress, sleep=0.05)
        target.execute("PRAGMA journal_mode=DELETE")
    for name in DATA_FILES:
        if (data / name).exists():
            private_copy(data / name, folder / name)
    if secrets_dir:
        for name in SECRET_FILES:
            source_path = Path(secrets_dir) / name
            if source_path.exists():
                private_copy(source_path, destination / "secrets" / name)
    files = {
        p.relative_to(destination).as_posix(): {
            "bytes": p.stat().st_size,
            "sha256": digest(p),
        }
        for p in destination.rglob("*")
        if p.is_file()
    }
    manifest = {
        "format": 1,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": files,
        "limits": [
            "configuration-files-copied-after-database",
            "audit-log-and-editor-cache-excluded",
            "local-copy-not-offsite",
        ],
    }
    path = destination / "manifest.json"
    path.touch(mode=0o600, exist_ok=False)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    verify(destination)
    return manifest


def restore(bundle, destination):
    manifest = verify(bundle)
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name in manifest["files"]:
        private_copy(Path(bundle) / name, destination / name)
    # Chỉ bản sao vào nơi mới; không chạy cấu hình hoặc thay dịch vụ đang hoạt động.
    return {"restored_files": len(manifest["files"]), "live_service_changed": False}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("backup", "verify", "restore"))
    parser.add_argument("--data", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--secrets-dir", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "backup" and args.data and args.destination:
            result = backup(args.data, args.destination, args.secrets_dir)
            result = {"verified": True, "files": len(result["files"])}
        elif args.action == "verify" and args.bundle:
            result = {"verified": True, "files": len(verify(args.bundle)["files"])}
        elif args.action == "restore" and args.bundle and args.destination:
            result = restore(args.bundle, args.destination)
        else:
            parser.error("Thiếu tham số cho thao tác")
        print(json.dumps(result))
    except (OSError, ValueError, sqlite3.Error, TimeoutError, KeyError, TypeError):
        raise SystemExit(
            "Thao tác sao lưu bị từ chối; kiểm quyền, gói và đường dẫn riêng"
        ) from None


if __name__ == "__main__":
    main()
