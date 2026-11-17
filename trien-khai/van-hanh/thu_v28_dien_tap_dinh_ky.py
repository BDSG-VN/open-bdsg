"""Diễn tập định kỳ dùng kho tổng hợp mới; không dùng đường dẫn vận hành."""

import io
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from contextlib import closing, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import v28_dien_tap_dinh_ky as periodic
from kiem_tra_khoi_phuc import read_status
from sao_luu_he_thong import backup, digest


class ThuDienTapDinhKy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        with closing(sqlite3.connect(self.source / "van-hanh.db")) as db:
            db.executescript("CREATE TABLE du_an(id TEXT); INSERT INTO du_an VALUES('TONG-HOP');")
        self.backups = self.root / "backups"
        self.backups.mkdir()
        self.drills = self.backups / "drills"
        self.drills.mkdir()
        self.status_dir = self.root / "status"
        self.status_dir.mkdir()
        self.status_dir.chmod(0o750)
        self.status = self.status_dir / "recovery.json"
        self.now = time.time() + 1
        self.uid = os.getuid() if os.name == "posix" else 0
        self.gid = os.getgid() if os.name == "posix" else 0
        self.old = self.make_bundle(self.now - 120)
        self.new = self.make_bundle(self.now - 60)

    def make_bundle(self, timestamp):
        name = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.backups / name
        backup(self.source, path)
        return path

    def run_fixture(self):
        return periodic.run(self.backups, self.status, self.now, self.gid, self.uid)

    def test_chon_moi_nhat_bo_qua_ten_khong_phai_timestamp(self):
        (self.backups / "khong-phai-ban-sao").mkdir()
        self.assertEqual(periodic.select_latest(self.backups, self.now), self.new)

    def test_ban_moi_nhat_hong_khong_am_tham_lui_ban_cu(self):
        with (self.new / "data/van-hanh.db").open("ab") as stream:
            stream.write(b"tampered")
        with self.assertRaises(ValueError):
            periodic.select_latest(self.backups, self.now)
        report, code = self.run_fixture()
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(read_status(self.status)["status"], "failed")

    def test_ten_ban_sao_cu_hoac_tuong_lai_bi_chan(self):
        for now in (self.now + 172801, self.now - 300):
            with self.subTest(now=now), self.assertRaises(ValueError):
                periodic.select_latest(self.backups, now)

    def test_manifest_cu_du_ten_moi_van_bi_chan(self):
        path = self.new / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["created_utc"] = "2020-01-01T00:00:00Z"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError):
            periodic.select_latest(self.backups, self.now)

    def test_dien_tap_cong_bo_schema_va_chi_don_tmp_so_huu(self):
        marker = self.drills / "giu-nguyen.txt"
        marker.write_text("KEEP", encoding="utf-8")
        source_hash = digest(self.source / "van-hanh.db")
        backup_hash = digest(self.new / "data/van-hanh.db")
        report, code = self.run_fixture()
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["counts"]["projects"], 1)
        self.assertEqual(read_status(self.status)["status"], "ok")
        self.assertEqual(json.loads(self.status.read_text(encoding="utf-8")), report)
        self.assertEqual(list(self.drills.iterdir()), [marker])
        self.assertEqual(digest(self.source / "van-hanh.db"), source_hash)
        self.assertEqual(digest(self.new / "data/van-hanh.db"), backup_hash)
        self.assertNotIn(str(self.root), json.dumps(report))
        self.assertNotIn("TONG-HOP", json.dumps(report))
        if os.name == "posix":
            self.assertEqual(self.status.stat().st_mode & 0o777, 0o640)
            self.assertEqual(self.status.stat().st_uid, self.uid)
            self.assertEqual(self.status.stat().st_gid, self.gid)

    def test_cli_tham_so_khong_duoc_duyet_chi_tra_bao_cao_loc(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["job.py", str(self.source)]), redirect_stdout(output):
            self.assertEqual(periodic.main(), 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "failed")
        self.assertNotIn(str(self.root), output.getvalue())

    @unittest.skipIf(os.name == "nt", "Windows cần quyền tạo symlink riêng")
    def test_ban_timestamp_lien_ket_bi_chan(self):
        link_name = datetime.fromtimestamp(self.now, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (self.backups / link_name).symlink_to(self.new, target_is_directory=True)
        with self.assertRaises(ValueError):
            periodic.select_latest(self.backups, self.now)

    @unittest.skipIf(os.name == "nt", "Windows cần quyền tạo symlink riêng")
    def test_status_symlink_khong_bi_ghi_de(self):
        protected = self.root / "protected.json"
        protected.write_text("KEEP", encoding="utf-8")
        self.status.symlink_to(protected)
        report, code = self.run_fixture()
        self.assertEqual(code, 1)
        self.assertEqual(protected.read_text(encoding="utf-8"), "KEEP")
        self.assertEqual(list(self.drills.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
