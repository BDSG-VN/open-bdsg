"""Diễn tập hằng ngày trên bản sao mới nhất; không chạy app hoặc dùng mạng.

CLI vận hành dùng đường dẫn cố định. Chỉ ghi báo cáo và thư mục tạm do chính
lượt này tạo trong drills; không sửa/xóa bản sao hay dữ liệu vận hành.
"""

import json
import os
import re
import sqlite3
import stat
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "he-dieu-hanh"))
from kiem_tra_khoi_phuc import drill
from sao_luu_he_thong import verify


BACKUP_ROOT = Path("/var/backups/bdsg-thanhhoa")
STATUS_FILE = Path("/var/lib/bdsg-thanhhoa-status/recovery.json")
STATUS_GROUP = "bdsg-thanhhoa"
MAX_BACKUP_AGE_SECONDS = 172800


def _plain(path):
    path = Path(os.path.abspath(path))
    for component in (path, *path.parents):
        if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
            raise ValueError("Không nhận liên kết")
    return path


def failure_report(duration=0):
    return {"format": 1, "observed_at": time.time(), "status": "failed",
        "last_backup_at": None, "backup_age_seconds": None,
        "restore_age_seconds": None, "restore_duration_seconds": round(duration, 6),
        "integrity": "not_measured", "counts": {"files": None, "versions": None, "projects": None, "tasks": None},
        "database_user_version": None, "restored_files": None,
        "offsite": {"configured": False}, "rpo_basis": "snapshot_age_only",
        "service_recovery_tested": False}


def select_latest(backup_root, now=None):
    """Chỉ xét tên timestamp chuẩn; mới nhất hỏng/cũ phải báo lỗi, không lùi bản."""
    backup_root = _plain(backup_root)
    now = time.time() if now is None else now
    candidates = []
    for path in backup_root.iterdir():
        if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z", path.name):
            continue
        timestamp = datetime.strptime(path.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp()
        candidates.append((timestamp, path))
    if not candidates:
        raise ValueError("Chưa có bản sao phù hợp")
    timestamp, bundle = max(candidates, key=lambda item: item[0])
    bundle = _plain(bundle)
    if not bundle.is_dir() or not 0 <= now - timestamp <= MAX_BACKUP_AGE_SECONDS:
        raise ValueError("Bản mới nhất không phù hợp")
    manifest = verify(bundle)
    created = datetime.strptime(manifest["created_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    if not 0 <= now - created <= MAX_BACKUP_AGE_SECONDS:
        raise ValueError("Mốc sao lưu cũ hoặc không hợp lệ")
    return bundle


def publish_status(report, status_file, group_gid, owner_uid=0):
    """Thay báo cáo nguyên tử sau khi đặt sở hữu/quyền, không sửa tệp đích cũ."""
    status_file = _plain(status_file)
    parent = status_file.parent
    if not parent.is_dir() or (status_file.exists() and not status_file.is_file()):
        raise ValueError("Thư mục trạng thái không hợp lệ")
    if os.name == "posix":
        info = parent.stat()
        if info.st_uid != owner_uid or info.st_gid != group_gid or stat.S_IMODE(info.st_mode) != 0o750:
            raise ValueError("Thư mục trạng thái phải thuộc người vận hành và nhóm đọc")
    fd, temporary = tempfile.mkstemp(prefix=".v28-recovery-", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            if os.name == "posix":
                os.fchown(stream.fileno(), owner_uid, group_gid)
                os.fchmod(stream.fileno(), 0o640)
            else:
                os.chmod(temporary, 0o640)
            json.dump(report, stream, ensure_ascii=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, status_file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(backup_root=BACKUP_ROOT, status_file=STATUS_FILE, now=None,
        group_gid=None, owner_uid=0):
    """Đường dẫn/uid tùy chọn dành cho fixture; CLI luôn dùng hằng số vận hành."""
    started = time.perf_counter()
    report, code = failure_report(), 1
    try:
        if group_gid is None:
            import grp
            group_gid = grp.getgrnam(STATUS_GROUP).gr_gid
        backup_root = _plain(backup_root)
        drills = _plain(backup_root / "drills")
        if not drills.is_dir():
            raise ValueError("Chưa chuẩn bị thư mục diễn tập")
        if os.name == "posix":
            for directory in (backup_root, drills):
                info = directory.stat()
                if info.st_uid != owner_uid or stat.S_IMODE(info.st_mode) & 0o022:
                    raise ValueError("Thư mục bản sao phải do người vận hành kiểm soát")
        bundle = select_latest(backup_root, now)
        with tempfile.TemporaryDirectory(prefix="v28-", dir=drills) as temporary:
            workspace = _plain(temporary)
            if workspace.parent != drills or not workspace.name.startswith("v28-"):
                raise ValueError("Phạm vi diễn tập không hợp lệ")
            report, code = drill(bundle, workspace / "restored-new")
            # Công bố trước khi cleanup; TemporaryDirectory chỉ dọn thư mục sở hữu.
            publish_status(report, status_file, group_gid, owner_uid)
        return report, code
    except (OSError, ValueError, sqlite3.Error, TimeoutError, KeyError, TypeError,
            AttributeError, RecursionError, OverflowError, ImportError):
        report = failure_report(time.perf_counter() - started)
        try:
            if group_gid is not None:
                publish_status(report, status_file, group_gid, owner_uid)
        except (OSError, ValueError, TypeError):
            pass
        return report, 1


def main():
    os.umask(0o077)
    if len(sys.argv) != 1 or os.name != "posix" or os.geteuid() != 0:
        print(json.dumps(failure_report()))
        return 1
    report, code = run()
    print(json.dumps(report, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
