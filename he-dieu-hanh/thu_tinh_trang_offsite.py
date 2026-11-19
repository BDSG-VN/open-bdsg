"""Biên nhận hợp lệ không được che bản sao cũ hoặc suy ra tự động hóa."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from tinh_trang_offsite import read_offsite_status


class ThuOffsite(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "receipt.json"
        self.receipt = {"format": 1, "status": "verified", "verified_at": 2000,
            "snapshot_at": 1000, "encrypted_sha256": "a" * 64,
            "encrypted_bytes": 12345, "destination": "google-drive",
            "verification": "download-sha256-and-decrypt"}

    def read(self, now=3000):
        self.path.write_text(json.dumps(self.receipt), encoding="utf-8")
        return read_offsite_status(self.path, now=now)

    def test_ban_sao_da_kiem_khong_tu_suy_ra_lich_tu_dong(self):
        value = self.read()
        self.assertEqual(value["status"], "verified")
        self.assertEqual(value["backup_age_seconds"], 2000)
        self.assertTrue(value["decryption_verified"])
        self.assertEqual(value["automatic_upload"], "not_verified")
        self.assertNotIn("encrypted_sha256", value)

    def test_kiem_lai_hom_nay_khong_lam_ban_cu_thanh_moi(self):
        self.receipt["verified_at"] = 300000
        self.assertEqual(self.read(now=300001)["status"], "stale")

    def test_sha_tai_lai_khong_duoc_goi_la_da_giai_ma(self):
        self.receipt["verification"] = "download-sha256"
        self.assertFalse(self.read()["decryption_verified"])

    def test_sai_thieu_thua_truong_khong_lam_lo_noi_dung(self):
        mutations = [("snapshot_at", True), ("verified_at", float("nan")),
            ("verified_at", 4000), ("snapshot_at", 2500), ("format", True),
            ("encrypted_bytes", -1), ("encrypted_sha256", "secret"),
            ("destination", "unknown"), ("token", "private-value")]
        original = self.receipt.copy()
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                self.receipt = dict(original, **{field: value})
                result = self.read()
                self.assertEqual(result["status"], "unknown")
                self.assertNotIn("private-value", str(result))
                self.assertNotIn(str(self.path), str(result))

    def test_khong_cau_hinh_mat_tep_va_json_hong(self):
        self.assertEqual(read_offsite_status(None)["reason"], "not_configured")
        self.assertEqual(read_offsite_status(self.path)["reason"], "unavailable")
        for text in ('{"format":1,"format":1}', 'x' * 8193, '[1,2,3]'):
            self.path.write_text(text)
            self.assertEqual(read_offsite_status(self.path)["reason"], "invalid")

    @unittest.skipUnless(os.name == "posix", "Symlink POSIX")
    def test_khong_theo_lien_ket(self):
        self.read()
        link = self.path.parent / "link.json"
        link.symlink_to(self.path)
        self.assertEqual(read_offsite_status(link)["reason"], "invalid")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO POSIX")
    def test_fifo_khong_duoc_lam_treo_doc_trang_thai(self):
        os.mkfifo(self.path)
        self.assertEqual(read_offsite_status(self.path)["reason"], "invalid")


if __name__ == "__main__":
    unittest.main()
