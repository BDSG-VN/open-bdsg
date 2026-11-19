"""Kiểm phiên web tự quản bằng dữ liệu tổng hợp và Kho đăng nhập thật."""

import json
import re
import secrets
import tempfile
import threading
import time
import unittest
from pathlib import Path

from kho import Kho, bam
from phien_web import PhienWeb
from sao_luu_he_thong import backup, restore


class ThuPhienWeb(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kho = Kho(Path(self.temp.name) / "data")
        self.kho.tao_chu("synthetic-owner-password")
        self.owner = {"id": "chu-quan", "role": "quan-tri"}
        self.kho.tao_nguoi_dung(self.owner, {"id": "operator-test", "name": "Synthetic", "password": "synthetic-operator-password"})
        self.operator = {"id": "operator-test", "role": "operator"}
        self.now = time.time()
        self.sessions = PhienWeb(self.kho, clock=lambda: self.now)
        self.current = self.login()
        self.other = self.login()
        self.operator_token = self.login("operator-test", "synthetic-operator-password")

    def login(self, identity="chu-quan", password="synthetic-owner-password"):
        token, status = self.kho.dang_nhap(identity, password, "synthetic-address")
        self.assertEqual(status, "ok")
        return token

    def owner_list(self):
        return self.sessions.list(self.owner, self.current)

    def other_id(self):
        return next(item["id"] for item in self.owner_list()["sessions"] if not item["current"])

    def test_danh_sach_chi_co_phien_cua_chinh_minh_va_ma_cong_khai(self):
        result = self.owner_list()
        self.assertEqual(len(result["sessions"]), 2)
        self.assertTrue(result["sessions"][0]["current"])
        self.assertFalse(result["has_more"])
        for item in result["sessions"]:
            self.assertRegex(item["id"], re.compile(r"^[A-Za-z0-9_-]{24}$"))
            self.assertIsNotNone(item["created_at"])
        output = json.dumps(result)
        for private in (self.current, self.other, self.operator_token, bam(self.current), "synthetic-address", self.temp.name):
            self.assertNotIn(private, output)
        operator = self.sessions.list(self.operator, self.operator_token)
        self.assertEqual(len(operator["sessions"]), 1)
        self.assertTrue(operator["sessions"][0]["current"])

    def test_thu_hoi_phien_khac_chan_ngay_lenh_xac_thuc_sau(self):
        identifier = self.other_id()
        self.assertEqual(self.sessions.revoke(self.owner, self.current, identifier), {"revoked": True})
        self.assertIsNone(self.kho.tu_phien(self.other))
        self.assertEqual(self.kho.tu_phien(self.current)["id"], "chu-quan")
        self.assertIsNotNone(self.kho.tu_phien(self.operator_token))
        self.assertEqual(len(self.owner_list()["sessions"]), 1)
        with self.assertRaises(PermissionError):
            self.sessions.list(self.owner, self.other)

    def test_phien_nguoi_khac_va_ma_khong_ton_tai_cung_loi(self):
        foreign = self.sessions.list(self.operator, self.operator_token)["sessions"][0]["id"]
        messages = []
        for identifier in (foreign, secrets.token_urlsafe(18), "bad"):
            with self.assertRaises(LookupError) as error:
                self.sessions.revoke(self.owner, self.current, identifier)
            messages.append(str(error.exception))
        self.assertEqual(len(set(messages)), 1)
        self.assertIsNotNone(self.kho.tu_phien(self.operator_token))

    def test_khong_tu_thu_hoi_phien_hien_tai(self):
        identifier = self.owner_list()["sessions"][0]["id"]
        with self.assertRaises(ValueError):
            self.sessions.revoke(self.owner, self.current, identifier)
        self.assertIsNotNone(self.kho.tu_phien(self.current))

    def test_thu_hoi_tat_ca_phien_khac_giu_dung_cookie_hien_tai(self):
        third = self.login()
        result = self.sessions.revoke_others(self.owner, self.current)
        self.assertEqual(result, {"revoked_count": 2})
        self.assertIsNone(self.kho.tu_phien(self.other))
        self.assertIsNone(self.kho.tu_phien(third))
        self.assertIsNotNone(self.kho.tu_phien(self.current))
        self.assertIsNotNone(self.kho.tu_phien(self.operator_token))
        self.assertEqual(self.sessions.revoke_others(self.owner, self.current), {"revoked_count": 0})

    def test_doi_ten_tu_quan_kiem_do_dai_va_ky_tu_dieu_khien(self):
        identifier = self.other_id()
        self.assertEqual(self.sessions.rename(self.owner, self.current, identifier, "  Máy thứ hai  "), {"renamed": True})
        item = next(item for item in self.owner_list()["sessions"] if item["id"] == identifier)
        self.assertEqual(item["label"], "Máy thứ hai")
        for invalid in ("", "  ", "a" * 81, "x\ny", "x\x7fy", "x\u202ey", "x\u2028y", None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.sessions.rename(self.owner, self.current, identifier, invalid)
        foreign = self.sessions.list(self.operator, self.operator_token)["sessions"][0]["id"]
        with self.assertRaises(LookupError):
            self.sessions.rename(self.owner, self.current, foreign, "Không được")

    def test_cookie_het_han_bi_thu_hoi_va_actor_gia_bi_tu_choi(self):
        for actor, token in ((self.owner, self.operator_token),
                ({"id": "operator-test", "role": "quan-tri"}, self.operator_token),
                ({"id": "chu-quan", "role": "operator"}, self.current),
                (None, self.current), (self.owner, "bad-token")):
            with self.subTest(actor=actor), self.assertRaises(PermissionError):
                self.sessions.list(actor, token)
        self.now += 9 * 3600
        with self.assertRaises(PermissionError):
            self.owner_list()

    def test_tai_khoan_bi_vo_hieu_hoa_khong_duoc_quan_ly_phien(self):
        self.kho.thu_hoi_agent("operator-test")
        with self.assertRaises(PermissionError):
            self.sessions.revoke_others(self.operator, self.operator_token)

    def test_rollback_cau_truc_ba_cot_va_phien_cu_khong_bia_ngay_tao(self):
        legacy = secrets.token_urlsafe(36)
        with self.kho.ket_noi() as db:
            db.execute("INSERT INTO phien VALUES(?,?,?)", (bam(legacy), "chu-quan", self.now + 1000))
        listed = self.sessions.list(self.owner, legacy)
        item = listed["sessions"][0]
        self.assertTrue(item["current"])
        self.assertIsNone(item["created_at"])
        self.assertIsNone(item["last_seen_at"])
        self.sessions.touch(self.owner, legacy, "macOS")
        item = self.sessions.list(self.owner, legacy)["sessions"][0]
        self.assertIsNone(item["created_at"])
        self.assertEqual(item["last_seen_at"], self.now)
        self.assertEqual(item["client_hint"], "macOS")

    def test_last_seen_giam_ghi_va_hint_chi_nhan_nhan_nen_tang_co_dinh(self):
        self.sessions.touch(self.owner, self.current, "Windows")
        first = self.owner_list()["sessions"][0]
        self.now += 5
        self.sessions.touch(self.owner, self.current, "raw-user-agent-or-address")
        second = self.owner_list()["sessions"][0]
        self.assertEqual(second["last_seen_at"], first["last_seen_at"])
        self.assertEqual(second["client_hint"], "Windows")
        self.now += 60
        self.sessions.touch(self.owner, self.current, "Android")
        third = self.owner_list()["sessions"][0]
        self.assertEqual(third["last_seen_at"], self.now)
        self.assertEqual(third["client_hint"], "Windows")
        self.now -= 100
        self.sessions.touch(self.owner, self.current, "macOS")
        self.assertEqual(self.owner_list()["sessions"][0]["last_seen_at"], third["last_seen_at"])

    def test_danh_sach_co_gioi_han_va_phien_hien_tai_khong_bi_day_khoi(self):
        with self.kho.ket_noi() as db:
            for offset in range(105):
                db.execute("INSERT INTO phien VALUES(?,?,?)", (bam(secrets.token_urlsafe(36)), "chu-quan", self.now + 40000 + offset))
        result = self.owner_list()
        self.assertEqual(len(result["sessions"]), 100)
        self.assertTrue(result["sessions"][0]["current"])
        self.assertTrue(result["has_more"])
        self.assertEqual(self.sessions.revoke_others(self.owner, self.current)["revoked_count"], 106)
        self.assertEqual(len(self.owner_list()["sessions"]), 1)

    def test_phien_meta_tu_don_khi_dang_xuat_bang_ma_cu(self):
        self.owner_list()
        self.kho.dang_xuat(self.other)
        with self.kho.ket_noi() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM phien_web WHERE session_hash=?", (bam(self.other),)).fetchone()[0], 0)

    def test_nhat_ky_chi_co_metadata_khong_chua_token_hash_hoac_label(self):
        identifier = self.other_id()
        self.sessions.rename(self.owner, self.current, identifier, "Tên riêng không đưa vào audit")
        self.sessions.revoke(self.owner, self.current, identifier)
        with self.kho.ket_noi() as db:
            rows = [dict(row) for row in db.execute("SELECT * FROM su_kien WHERE action LIKE '%phien-web%'")]
        serialized = json.dumps(rows, ensure_ascii=False)
        for private in (self.current, self.other, bam(self.current), bam(self.other), "Tên riêng"):
            self.assertNotIn(private, serialized)
        self.assertIn(identifier, serialized)

    def test_hai_phien_thu_hoi_dong_thoi_khong_lam_mat_ca_hai_phien(self):
        barrier, lock = threading.Barrier(2), threading.Lock()
        results = []

        def worker(token):
            barrier.wait(timeout=3)
            try:
                self.sessions.revoke_others(self.owner, token)
                result = "ok"
            except PermissionError:
                result = "denied"
            with lock:
                results.append(result)

        threads = [threading.Thread(target=worker, args=(token,)) for token in (self.current, self.other)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(sorted(results), ["denied", "ok"])
        self.assertEqual(sum(self.kho.tu_phien(token) is not None for token in (self.current, self.other)), 1)
        self.assertIsNotNone(self.kho.tu_phien(self.operator_token))

    def test_sao_luu_phuc_hoi_giu_ma_va_nhan_phien_hien_co(self):
        identifier = self.other_id()
        self.sessions.rename(self.owner, self.current, identifier, "Phiên tổng hợp")
        self.sessions.touch(self.owner, self.current, "Windows")
        before = self.owner_list()
        root = Path(self.temp.name)
        backup(self.kho.root, root / "backup")
        restore(root / "backup", root / "restore-new")
        restored = Kho(root / "restore-new/data")
        after = PhienWeb(restored, clock=lambda: self.now).list(self.owner, self.current)
        self.assertEqual(after, before)
        self.assertIsNotNone(restored.tu_phien(self.current))
        PhienWeb(restored, clock=lambda: self.now).revoke(self.owner, self.current, identifier)
        self.assertIsNone(restored.tu_phien(self.other))
        self.assertIsNotNone(self.kho.tu_phien(self.other))


if __name__ == "__main__":
    unittest.main()
