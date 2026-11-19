"""Tạo dữ liệu tổng hợp trong thư mục MỚI rồi đo backup/phục hồi cục bộ.

Không dùng cấu hình, bí mật, dữ liệu hoặc mạng của máy chủ đang vận hành.
Không xóa thư mục sau diễn tập để người vận hành kiểm lại bằng chứng.
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "he-dieu-hanh"))
from kiem_tra_khoi_phuc import drill, write_status
from sao_luu_he_thong import backup, digest


def run(workspace):
    workspace.mkdir(mode=0o700, parents=False, exist_ok=False)
    source = workspace / "synthetic-data"
    source.mkdir(mode=0o700)
    with closing(sqlite3.connect(source / "van-hanh.db")) as db:
        db.executescript("""
            CREATE TABLE office_files(id TEXT PRIMARY KEY, name TEXT);
            INSERT INTO office_files VALUES('file-demo', 'tep-tong-hop.txt');
            CREATE TABLE office_versions(file_id TEXT, version INTEGER, content BLOB);
            INSERT INTO office_versions VALUES('file-demo', 1, X'64656d6f');
            INSERT INTO office_versions VALUES('file-demo', 2, X'64656d6f32');
            CREATE TABLE du_an(id TEXT PRIMARY KEY, name TEXT);
            INSERT INTO du_an VALUES('project-demo', 'Du an tong hop');
            CREATE TABLE cong_viec_tasks(id TEXT PRIMARY KEY, status TEXT);
            INSERT INTO cong_viec_tasks VALUES('task-demo-a', 'completed');
            INSERT INTO cong_viec_tasks VALUES('task-demo-b', 'interrupted');
        """)
    bundle = workspace / "backup"
    source_hash = digest(source / "van-hanh.db")
    started = time.perf_counter()
    backup(source, bundle)
    backup_duration = round(time.perf_counter() - started, 6)
    report, code = drill(bundle, workspace / "restored-new")
    write_status(workspace / "recovery-status.json", report)
    _, existing_code = drill(bundle, workspace / "restored-new")
    tampered = workspace / "tampered-synthetic-backup"
    shutil.copytree(bundle, tampered)
    with (tampered / "data/van-hanh.db").open("ab") as output:
        output.write(b"tamper-synthetic-only")
    _, tampered_code = drill(tampered, workspace / "must-not-exist")
    checks = {
        "restored_metadata_matches": report["counts"] == {"files": 1, "versions": 2, "projects": 1, "tasks": 2},
        "existing_destination_refused": existing_code == 1,
        "tampered_backup_refused": tampered_code == 1 and not (workspace / "must-not-exist").exists(),
        "source_preserved": digest(source / "van-hanh.db") == source_hash,
    }
    print(json.dumps({"scope": "synthetic_restore_drill", "observed_at": time.time(),
        "backup_duration_seconds": backup_duration, "restore": report, "assertions": checks,
        "application_started": False, "external_network_used": False}, allow_nan=False))
    return 0 if code == 0 and all(checks.values()) else 1


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True,
                        help="Thư mục chưa tồn tại, cha đã tồn tại, nằm ngoài web/Git")
    args = parser.parse_args()
    try:
        return run(args.workspace)
    except (OSError, ValueError, sqlite3.Error, TimeoutError, KeyError, TypeError):
        print(json.dumps({"scope": "synthetic_restore_drill", "status": "failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
