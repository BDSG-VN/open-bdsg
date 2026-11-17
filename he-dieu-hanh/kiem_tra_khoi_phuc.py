"""Diễn tập phục hồi cục bộ, không chạy dịch vụ hoặc ghi đè kho có sẵn.

stdout/status-file chỉ gồm metadata cho phép; không xuất manifest, đường dẫn,
nội dung, khóa hoặc thông điệp ngoại lệ. RPO chỉ là tuổi snapshot đã kiểm.
"""

import argparse
import json
import math
import os
import sqlite3
import stat
import tempfile
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from sao_luu_he_thong import digest, restore, verify


TABLES = {"files": "office_files", "versions": "office_versions",
          "projects": "du_an", "tasks": "cong_viec_tasks"}
FIELDS = frozenset(("format", "observed_at", "status", "last_backup_at",
    "backup_age_seconds", "restore_age_seconds", "restore_duration_seconds",
    "integrity", "counts", "database_user_version", "restored_files",
    "offsite", "rpo_basis", "service_recovery_tested"))


def _metadata(path):
    # Không khởi tạo UngDung: startup thay trạng thái tác vụ đang chạy.
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("CSDL không toàn vẹn")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {name: db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                  if table in tables else None for name, table in TABLES.items()}
        return counts, db.execute("PRAGMA user_version").fetchone()[0]


def _blank(now):
    return {"format": 1, "observed_at": now, "status": "failed",
        "last_backup_at": None, "backup_age_seconds": None,
        "restore_age_seconds": None, "restore_duration_seconds": None,
        "integrity": "not_measured", "counts": {name: None for name in TABLES},
        "database_user_version": None, "restored_files": None,
        "offsite": {"configured": False}, "rpo_basis": "snapshot_age_only",
        "service_recovery_tested": False}


def drill(bundle, destination):
    """Kiểm gói rồi chép vào đích mới; trả (báo cáo đã lọc, mã thoát)."""
    started = time.perf_counter()
    report = _blank(time.time())
    try:
        source, target = Path(bundle).resolve(), Path(destination).resolve()
        if target == source or source in target.parents:
            raise ValueError("Đích phải nằm ngoài gói sao lưu")
        manifest = verify(bundle)
        snapshot = datetime.strptime(manifest["created_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        if snapshot > time.time():
            raise ValueError("Mốc snapshot nằm trong tương lai")
        counts, version = _metadata(Path(bundle) / "data/van-hanh.db")
        result = restore(bundle, destination)
        for name, entry in manifest["files"].items():
            recovered = Path(destination) / name
            if recovered.stat().st_size != entry["bytes"] or digest(recovered) != entry["sha256"]:
                raise ValueError("Bản phục hồi không khớp")
        if _metadata(Path(destination) / "data/van-hanh.db") != (counts, version):
            raise ValueError("Metadata phục hồi không khớp")
        report.update(status="ok", last_backup_at=snapshot, counts=counts,
                      database_user_version=version, restored_files=result["restored_files"],
                      integrity="ok", restore_age_seconds=0)
    except (OSError, ValueError, sqlite3.Error, TimeoutError, KeyError, TypeError,
            OverflowError, AttributeError, RecursionError):
        # Không phản chiếu lỗi từ JSON/SQLite/OS: lỗi có thể chứa dữ liệu riêng.
        report["integrity"] = "failed"
    report["observed_at"] = time.time()
    report["restore_duration_seconds"] = round(time.perf_counter() - started, 6)
    if report["last_backup_at"] is not None:
        report["backup_age_seconds"] = round(report["observed_at"] - report["last_backup_at"], 3)
    return report, 0 if report["status"] == "ok" else 1


def _number(value, nullable=False):
    return (nullable and value is None) or (type(value) in (int, float) and math.isfinite(value) and value >= 0)


def _valid(report):
    if not isinstance(report, dict) or set(report) != FIELDS:
        return False
    if type(report["format"]) is not int or report["format"] != 1:
        return False
    if report["status"] not in ("ok", "failed") or report["integrity"] not in ("ok", "failed", "not_measured"):
        return False
    if report["offsite"] != {"configured": False} or report["service_recovery_tested"] is not False or report["rpo_basis"] != "snapshot_age_only":
        return False
    if not _number(report["observed_at"]):
        return False
    if not all(_number(report[name], nullable=True) for name in
               ("last_backup_at", "backup_age_seconds", "restore_age_seconds", "restore_duration_seconds")):
        return False
    if not isinstance(report["counts"], dict) or set(report["counts"]) != set(TABLES):
        return False
    if not all(value is None or (type(value) is int and value >= 0) for value in
               [*report["counts"].values(), report["restored_files"], report["database_user_version"]]):
        return False
    if report["status"] == "ok":
        if report["integrity"] != "ok" or any(report[name] is None for name in
            ("last_backup_at", "backup_age_seconds", "restore_age_seconds", "restore_duration_seconds", "restored_files", "database_user_version")):
            return False
        if report["last_backup_at"] > report["observed_at"] or report["restored_files"] < 1:
            return False
    return True


def read_status(path, now=None, max_age_seconds=172800):
    """Đọc trạng thái đã lọc cho chủ quản; thiếu/cũ/sai không được coi là OK."""
    unknown = {"configured": bool(path), "status": "unknown",
               "reason": "not_configured", "offsite": {"configured": False}}
    if not path:
        return unknown
    now = time.time() if now is None else now
    try:
        path = Path(path)
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_size > 16384:
            raise ValueError("Tệp trạng thái không hợp lệ")
        report = json.loads(path.read_text(encoding="utf-8"))
        if not _valid(report) or report["observed_at"] > now:
            raise ValueError("Báo cáo không hợp lệ")
        age = now - report["observed_at"]
        if age > max_age_seconds:
            return dict(unknown, reason="stale", report_age_seconds=round(age, 3))
        # Cập nhật tuổi từ mốc đo gốc, không làm báo cáo cũ trông như vừa đo.
        result = dict(report, configured=True, report_age_seconds=round(age, 3))
        if result["backup_age_seconds"] is not None:
            result["backup_age_seconds"] = round(now - report["last_backup_at"], 3)
        if result["restore_age_seconds"] is not None:
            result["restore_age_seconds"] = round(age + report["restore_age_seconds"], 3)
        return result
    except OSError:
        return dict(unknown, reason="unavailable")
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return dict(unknown, reason="invalid")


def write_status(path, report):
    """Thay báo cáo nguyên tử; thư mục cha do người vận hành tạo ngoài web."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Không ghi trạng thái qua liên kết")
    fd, temporary = tempfile.mkstemp(prefix=".recovery-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            os.chmod(temporary, 0o600)
            json.dump(report, output, ensure_ascii=True, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--status-file", type=Path)
    args = parser.parse_args()
    # Trạng thái không được thay bất kỳ tệp nào của gói hoặc đích phục hồi.
    if args.status_file:
        status = args.status_file.resolve()
        if any(status == p.resolve() or p.resolve() in status.parents for p in (args.bundle, args.destination)):
            print(json.dumps(_blank(time.time())))
            return 1
    report, code = drill(args.bundle, args.destination)
    if args.status_file:
        try:
            write_status(args.status_file, report)
        except (OSError, ValueError):
            report = _blank(time.time())
            code = 1
    print(json.dumps(report, ensure_ascii=True, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
