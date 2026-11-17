"""Mã hóa bản sao đã kiểm, gửi Drive và công bố biên nhận đã lọc.

CLI không nhận đường dẫn/tham số. Cấu hình OAuth do quản trị cấp riêng;
module không cấp quyền hoặc lấy chứng thư từ kết nối Codex.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time

from v28_dien_tap_dinh_ky import _plain, publish_status, select_latest
from v28_drive_transport import upload_age
from v28_ma_hoa import encrypt_bundle
from sao_luu_he_thong import digest, verify


@dataclass(frozen=True)
class Paths:
    backups: Path = Path("/var/backups/bdsg-thanhhoa")
    staging: Path = Path("/var/backups/bdsg-thanhhoa/offsite-staging")
    config: Path = Path("/etc/bdsg-thanhhoa-backup/rclone.conf")
    recipients: Path = Path("/etc/bdsg-thanhhoa-backup/recipients.txt")
    age: Path = Path("/opt/bdsg-age-v1.3.2/age/age")
    rclone: Path = Path("/opt/bdsg-rclone-v1.76.0/rclone")
    status: Path = Path("/var/lib/bdsg-thanhhoa-status/offsite.json")


JOB_SECONDS = 840


def failure_report():
    return {"format": 1, "status": "failed", "reason": "offsite_job_failed"}


def _controlled(path, owner_uid, directory=False, private=False):
    path = _plain(path)
    info = path.stat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError("Sai loại tệp vận hành")
    if os.name == "posix":
        mask = 0o077 if private else 0o022
        if info.st_uid != owner_uid or stat.S_IMODE(info.st_mode) & mask:
            raise ValueError("Quyền vận hành không phù hợp")
    return path


def run(paths=Paths(), *, group_gid=None, owner_uid=0, now=None,
        encryptor=encrypt_bundle, uploader=upload_age):
    """Paths/uid/seams chỉ cho fixture; CLI luôn dùng hằng số sản xuất.

    Không tin biên nhận adapter một cách độc lập: đối chiếu hash/size với
    ciphertext vừa tạo trước khi đưa trạng thái ra ứng dụng.
    """
    started = time.monotonic()
    clock = time.time if now is None else lambda: now
    try:
        if group_gid is None:
            import grp
            group_gid = grp.getgrnam("bdsg-thanhhoa").gr_gid
        # Thu hồi xanh cũ trước công việc có thể bị timeout/SIGKILL. Chỉ lượt
        # hoàn tất đọc lại mới được thay biên nhận này bằng trạng thái verified.
        publish_status(failure_report(), paths.status, group_gid, owner_uid)
        for directory in (paths.backups, paths.staging, paths.config.parent):
            _controlled(directory, owner_uid, directory=True,
                        private=directory != paths.backups)
        for private in (paths.config, paths.recipients):
            _controlled(private, owner_uid, private=True)
        for executable in (paths.age, paths.rclone):
            _controlled(executable, owner_uid)
        bundle = select_latest(paths.backups, clock())
        manifest = verify(bundle)
        snapshot_at = datetime.strptime(manifest["created_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc).timestamp()

        def remaining():
            value = JOB_SECONDS - (time.monotonic() - started)
            if value <= 0:
                raise TimeoutError("Hết thời hạn")
            return value

        with tempfile.TemporaryDirectory(prefix="v28-offsite-", dir=paths.staging) as temporary:
            workspace = _plain(temporary)
            os.chmod(workspace, 0o700)
            ciphertext = workspace / "backup.age"
            encryptor(bundle, ciphertext, paths.recipients, paths.age, timeout=remaining())
            _controlled(ciphertext, owner_uid, private=True)
            with ciphertext.open("rb") as stream:
                if stream.read(22) != b"age-encryption.org/v1\n":
                    raise ValueError("Đầu ra không phải age")
            size, sha256 = ciphertext.stat().st_size, digest(ciphertext)
            receipt = uploader(ciphertext, config=paths.config, executable=paths.rclone,
                               remote="bdsg-th01", prefix="daily",
                               allowed_destination="bdsg-th01:daily", timeout=remaining())
            if (not isinstance(receipt, dict) or receipt.get("format") != 1
                    or receipt.get("status") != "verified"
                    or receipt.get("destination") != "google-drive"
                    or receipt.get("verification") != "download-sha256"
                    or type(receipt.get("encrypted_bytes")) is not int
                    or receipt["encrypted_bytes"] != size
                    or receipt.get("encrypted_sha256") != sha256):
                raise ValueError("Biên nhận không khớp ciphertext")
            remaining()
            report = {"format": 1, "status": "verified", "verified_at": clock(),
                      "snapshot_at": snapshot_at, "encrypted_sha256": sha256,
                      "encrypted_bytes": size, "destination": "google-drive",
                      "verification": "download-sha256"}
            if report["verified_at"] < snapshot_at:
                raise ValueError("Đồng hồ không hợp lệ")
            publish_status(report, paths.status, group_gid, owner_uid)
        return report, 0
    except Exception:
        # Không đưa nội dung ngoại lệ từ filesystem/OAuth/adapter ra stdout.
        report = failure_report()
        try:
            if group_gid is not None:
                publish_status(report, paths.status, group_gid, owner_uid)
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
