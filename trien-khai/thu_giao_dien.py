#!/usr/bin/env python3
"""Kiểm ranh giới xuất bản: bí mật, dữ liệu máy chủ và mã thực thi không ra docroot."""
import json
import tempfile
import unittest
from pathlib import Path
from dung_giao_dien import GOC, dung


class ThuDongGoi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ra = Path(self.tmp.name) / "web"
        self.cfg = json.loads((GOC / "trien-khai/thuc-the/thanhhoa.json").read_text(encoding="utf-8"))

    def test_chi_xuat_giao_dien(self):
        self.cfg["mat_khau"] = "khong-duoc-xuat"
        dung(self.cfg, self.ra)
        files = [p for p in self.ra.rglob("*") if p.is_file()]
        self.assertTrue((self.ra / "index.html").is_file())
        self.assertFalse(any(p.suffix in (".py", ".db", ".env") for p in files))
        self.assertFalse(any(b"khong-duoc-xuat" in p.read_bytes() for p in files))
        self.assertIn('/dien-mao.css', (self.ra / 'index.html').read_text(encoding='utf-8'))
        self.assertIn('/ios.css', (self.ra / 'index.html').read_text(encoding='utf-8'))
        self.assertTrue((self.ra / 'workspace.html').is_file())
        self.assertTrue((self.ra / 'trinh-duyet.html').is_file())
        for name in ('mo-soan-thao.js', 'quyen-ket-noi.js', 'quyen-ket-noi.css', 'hop-thu-ui.js', 'hop-thu-ui.css', 'yeu-cau-ui.js', 'yeu-cau-ui.css'):
            self.assertTrue((self.ra/name).is_file())
            self.assertIn('/'+name,(self.ra/'workspace.html').read_text(encoding='utf-8'))
        self.assertNotIn('canonical', (self.ra / 'workspace.html').read_text(encoding='utf-8'))
        for ten_font in ('lora-latin.woff2', 'lora-vietnamese.woff2'):
            self.assertTrue((self.ra / 'fonts' / ten_font).read_bytes().startswith(b'wOF2'))
        self.assertNotIn("/chat.js", (self.ra / "tro-chuyen/index.html").read_text(encoding="utf-8"))

    def test_khong_ghi_de(self):
        self.ra.mkdir()
        (self.ra / "giu.txt").write_text("giu", encoding="utf-8")
        with self.assertRaises(ValueError):
            dung(self.cfg, self.ra)
        self.assertEqual((self.ra / "giu.txt").read_text(encoding="utf-8"), "giu")

    def test_chan_ten_mien_chen_noi_dung(self):
        self.cfg["ten_mien"] = 'site.test\"; alert(1)'
        with self.assertRaises(ValueError):
            dung(self.cfg, self.ra)
        self.assertFalse(self.ra.exists())

    def test_khong_tu_nhan_da_ket_noi(self):
        dung(self.cfg, self.ra)
        trang_thai = json.loads((self.ra / "cong/trang-thai-linh-vuc.json").read_text(encoding="utf-8"))
        self.assertIsNone(trang_thai["do_luc"])
        self.assertTrue(all(m["trang_thai"] == "chua-do" for m in trang_thai["muc"]))


if __name__ == "__main__":
    unittest.main()
