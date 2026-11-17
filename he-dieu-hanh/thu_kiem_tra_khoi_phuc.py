"""Diễn tập bằng dữ liệu tổng hợp; không khởi động ứng dụng hoặc đọc nội dung."""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from sao_luu_he_thong import backup, digest
from kiem_tra_khoi_phuc import drill, read_status


class ThuKhoiPhuc(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "nguon-rieng"
        self.source.mkdir()
        with closing(sqlite3.connect(self.source / "van-hanh.db")) as db:
            db.executescript("""
                CREATE TABLE office_files(id TEXT);
                INSERT INTO office_files VALUES('tep-tong-hop');
                CREATE TABLE office_versions(content TEXT);
                INSERT INTO office_versions VALUES('NOI-DUNG-KHONG-DUOC-XUAT');
                INSERT INTO office_versions VALUES('PHIEN-BAN-TONG-HOP');
                CREATE TABLE du_an(id TEXT);
                INSERT INTO du_an VALUES('du-an-tong-hop');
                CREATE TABLE cong_viec_tasks(id TEXT);
                INSERT INTO cong_viec_tasks VALUES('viec-a'),('viec-b'),('viec-c');
                PRAGMA user_version=7;
            """)
        self.bundle = self.root / "ban-sao-rieng"
        backup(self.source, self.bundle)
        self.destination = self.root / "khoi-phuc-moi"
        self.status = self.root / "trang-thai.json"

    def cli(self):
        return subprocess.run(
            [sys.executable, str(Path(__file__).with_name("kiem_tra_khoi_phuc.py")),
             "--bundle", str(self.bundle), "--destination", str(self.destination),
             "--status-file", str(self.status)],
            capture_output=True, text=True, encoding="utf-8",
        )

    def test_phuc_hoi_do_thoi_gian_va_dem_metadata_khong_lo_noi_dung(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["counts"], {"files": 1, "versions": 2, "projects": 1, "tasks": 3})
        self.assertEqual(report["database_user_version"], 7)
        self.assertEqual(report["integrity"], "ok")
        self.assertEqual(report["restored_files"], 1)
        self.assertGreaterEqual(report["restore_duration_seconds"], 0)
        self.assertGreaterEqual(report["backup_age_seconds"], 0)
        self.assertFalse(report["service_recovery_tested"])
        self.assertEqual(report["offsite"], {"configured": False})
        self.assertEqual(json.loads(self.status.read_text(encoding="utf-8")), report)
        self.assertTrue((self.destination / "data/van-hanh.db").is_file())
        for secret in (str(self.root), "NOI-DUNG-KHONG-DUOC-XUAT", "sha256", "manifest", "du-an-tong-hop"):
            self.assertNotIn(secret, result.stdout + result.stderr)

    def test_goi_bi_sua_bi_chan_truoc_khi_tao_dich(self):
        with (self.bundle / "data/van-hanh.db").open("ab") as output:
            output.write(b"noi-dung-them")
        result = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "failed")
        self.assertFalse(self.destination.exists())
        self.assertNotIn(str(self.root), result.stdout + result.stderr)

    def test_dich_da_ton_tai_khong_bi_ghi_de(self):
        self.destination.mkdir()
        marker = self.destination / "giu-nguyen.txt"
        marker.write_text("du-lieu-cu", encoding="utf-8")
        result = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(marker.read_text(encoding="utf-8"), "du-lieu-cu")
        self.assertEqual(list(self.destination.iterdir()), [marker])

    def test_reader_cap_nhat_tuoi_va_chan_bao_cao_cu(self):
        self.assertEqual(self.cli().returncode, 0)
        report = json.loads(self.status.read_text(encoding="utf-8"))
        status = read_status(self.status, now=report["observed_at"] + 30)
        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["restore_age_seconds"], 30)
        self.assertGreaterEqual(status["backup_age_seconds"], 30)
        stale = read_status(self.status, now=report["observed_at"] + 172801)
        self.assertEqual(stale["status"], "unknown")
        self.assertEqual(stale["reason"], "stale")
        self.assertNotIn("counts", stale)

    def test_reader_khong_phan_chieu_noi_dung_ngoai_schema(self):
        self.assertEqual(self.cli().returncode, 0)
        report = json.loads(self.status.read_text(encoding="utf-8"))
        report["private_path"] = "BI-MAT-KHONG-DUOC-XUAT"
        self.status.write_text(json.dumps(report), encoding="utf-8")
        status = read_status(self.status)
        self.assertEqual(status["reason"], "invalid")
        self.assertNotIn("BI-MAT", json.dumps(status))
        self.assertEqual(read_status(None)["reason"], "not_configured")
        self.assertEqual(read_status(self.root / "thieu.json")["reason"], "unavailable")

    def test_manifest_sai_kieu_tra_loi_da_loc_khong_traceback(self):
        (self.bundle / "manifest.json").write_text('["BI-MAT-KHONG-DUOC-XUAT"]', encoding="utf-8")
        result = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "failed")
        self.assertEqual(result.stderr, "")

    def test_khong_tao_dich_nam_trong_goi(self):
        self.destination = self.bundle / "dich-lam-hong-goi"
        result = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.destination.exists())

    def test_dien_tap_khong_sua_nguon_va_bang_thieu_la_chua_do(self):
        source_hash = digest(self.source / "van-hanh.db")
        with closing(sqlite3.connect(self.bundle / "data/van-hanh.db")) as db:
            db.execute("DROP TABLE office_versions")
            db.commit()
        manifest_path = self.bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["data/van-hanh.db"] = {
            "bytes": (self.bundle / "data/van-hanh.db").stat().st_size,
            "sha256": digest(self.bundle / "data/van-hanh.db"),
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        report, code = drill(self.bundle, self.destination)
        self.assertEqual(code, 0)
        self.assertIsNone(report["counts"]["versions"])
        self.assertEqual(digest(self.source / "van-hanh.db"), source_hash)

    def test_doc_schema_sai_va_moc_tuong_lai_la_unknown(self):
        self.assertEqual(self.cli().returncode, 0)
        baseline = json.loads(self.status.read_text(encoding="utf-8"))
        for field, invalid in (("observed_at", float("nan")), ("counts", {"files": "NOI-DUNG"}),
                               ("restored_files", True), ("offsite", {"configured": True}),
                               ("service_recovery_tested", True), ("status", "BI-MAT")):
            with self.subTest(field=field):
                report = dict(baseline, **{field: invalid})
                self.status.write_text(json.dumps(report), encoding="utf-8")
                result = read_status(self.status)
                self.assertEqual(result["reason"], "invalid")
                self.assertNotIn("BI-MAT", json.dumps(result))
        self.status.write_text(json.dumps(baseline), encoding="utf-8")
        self.assertEqual(read_status(self.status, now=baseline["observed_at"] - 1)["reason"], "invalid")

    def test_khong_cong_bo_status_bi_ghi_that_bai(self):
        self.status = self.root / "cha-khong-co" / "status.json"
        result = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "failed")
        self.assertNotIn(str(self.root), result.stdout + result.stderr)
        self.assertTrue((self.destination / "data/van-hanh.db").is_file())

    @unittest.skipIf(os.name == "nt", "Windows cần quyền tạo symlink riêng")
    def test_reader_tu_choi_symlink(self):
        self.assertEqual(self.cli().returncode, 0)
        link = self.root / "link-status.json"
        link.symlink_to(self.status)
        self.assertEqual(read_status(link)["reason"], "invalid")


if __name__ == "__main__":
    unittest.main()
