"""Fixture tổng hợp kiểm điều phối; seam giả không chứng minh mã hóa/cloud."""

from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

import v28_offsite_dinh_ky as job
from sao_luu_he_thong import backup, digest
from tinh_trang_offsite import FIELDS, read_offsite_status


class OffsiteJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / "synthetic"
        source.mkdir()
        with closing(sqlite3.connect(source / "van-hanh.db")) as db:
            db.executescript("CREATE TABLE du_an(id TEXT);INSERT INTO du_an VALUES('FIXTURE');")
        self.now = time.time() + 1
        backups, staging, private, statusdir = [self.root / x for x in ("backups", "staging", "private", "status")]
        for directory in (backups, staging, private, statusdir):
            directory.mkdir()
            directory.chmod(0o700)
        statusdir.chmod(0o750)
        self.bundle = backups / datetime.fromtimestamp(self.now - 10, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup(source, self.bundle)
        config, recipients, age, rclone = [private / x for x in ("rclone.conf", "recipients.txt", "age", "rclone")]
        for path in (config, recipients, age, rclone):
            path.write_text("FIXTURE ONLY")
            path.chmod(0o600)
        self.paths = job.Paths(backups, staging, config, recipients, age, rclone, statusdir / "offsite.json")
        self.uid = os.getuid() if os.name == "posix" else 0
        self.gid = os.getgid() if os.name == "posix" else 0
        self.encrypt_calls, self.upload_calls = [], []

    def encrypt(self, bundle, destination, recipients, executable, timeout):
        self.encrypt_calls.append(bundle)
        self.assertEqual(bundle, self.bundle)
        self.assertFalse(destination.exists())
        destination.write_bytes(b"age-encryption.org/v1\nSYNTHETIC TEST SEAM")
        destination.chmod(0o600)

    def upload(self, ciphertext, **options):
        self.upload_calls.append(options)
        # Trong lúc job chạy, trạng thái cũ đã bị thu hồi cả khi job bị kill.
        self.assertEqual(json.loads(self.paths.status.read_text())["status"], "failed")
        self.assertEqual(options["allowed_destination"], "bdsg-th01:daily")
        self.assertEqual(options["remote"], "bdsg-th01")
        self.assertEqual(options["prefix"], "daily")
        self.assertGreater(options["timeout"], 0)
        self.assertLessEqual(options["timeout"], job.JOB_SECONDS)
        return {"format": 1, "status": "verified", "destination": "google-drive",
                "verification": "download-sha256", "encrypted_bytes": ciphertext.stat().st_size,
                "encrypted_sha256": digest(ciphertext)}

    def run_job(self, **changes):
        options = dict(group_gid=self.gid, owner_uid=self.uid, now=self.now,
                       encryptor=self.encrypt, uploader=self.upload)
        options.update(changes)
        return job.run(self.paths, **options)

    def test_publish_exact_schema_and_cleanup_only_own_ciphertext(self):
        marker = self.paths.staging / "KEEP.age"
        marker.write_text("KEEP")
        before = digest(self.bundle / "data/van-hanh.db")
        report, code = self.run_job()
        self.assertEqual(code, 0)
        self.assertEqual(set(report), FIELDS)
        self.assertEqual(read_offsite_status(self.paths.status, now=self.now)["status"], "verified")
        self.assertEqual(list(self.paths.staging.iterdir()), [marker])
        self.assertEqual(digest(self.bundle / "data/van-hanh.db"), before)
        self.assertNotIn(str(self.root), json.dumps(report))
        self.assertNotIn("automatic", json.dumps(report))
        if os.name == "posix":
            self.assertEqual(self.paths.status.stat().st_mode & 0o777, 0o640)

    def test_freshness_and_integrity_checked_before_encrypt(self):
        for fault in ("old", "corrupt"):
            with self.subTest(fault=fault):
                if fault == "corrupt":
                    (self.bundle / "data/van-hanh.db").write_bytes(b"broken")
                report, code = self.run_job(now=self.now + 172801 if fault == "old" else self.now)
                self.assertEqual(code, 1)
                self.assertEqual(report["status"], "failed")
                self.assertFalse(self.encrypt_calls)
                self.assertFalse(self.upload_calls)

    def test_adapter_lie_or_failure_revokes_old_green(self):
        self.assertEqual(self.run_job()[1], 0)
        def liar(ciphertext, **options):
            return self.upload(ciphertext, **options) | {"encrypted_sha256": "0" * 64}
        report, code = self.run_job(uploader=liar)
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(read_offsite_status(self.paths.status, now=self.now)["status"], "unknown")
        self.assertEqual(list(self.paths.staging.iterdir()), [])

    def test_raw_exception_is_not_published(self):
        def fail(*args, **options):
            raise RuntimeError("SECRET OAuth path customer")
        report, code = self.run_job(uploader=fail)
        self.assertEqual(code, 1)
        self.assertNotIn("SECRET", self.paths.status.read_text())
        self.assertNotIn("SECRET", json.dumps(report))
        self.assertEqual(list(self.paths.staging.iterdir()), [])

    def test_missing_private_config_does_not_run_crypto(self):
        self.paths.config.unlink()
        self.assertEqual(self.run_job()[1], 1)
        self.assertFalse(self.encrypt_calls)

    def test_cli_rejects_arguments_without_using_paths(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["job.py", "--unexpected"]), redirect_stdout(output):
            self.assertEqual(job.main(), 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
