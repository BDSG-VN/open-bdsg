"""Kiểm phạm vi đơn vị qua giao diện công khai, bằng dữ liệu tổng hợp."""
import tempfile
import unittest
import threading

from kho import Kho
from don_vi import DonVi

OWNER = {"id": "chu-quan", "role": "quan-tri"}
A = {"id": "operator-a", "role": "operator"}
B = {"id": "operator-b", "role": "operator"}


class ThuDonVi(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kho = Kho(self.temp.name)
        self.kho.tao_chu("synthetic-password-only")
        self.kho.tao_agent(A["id"], "A thử nghiệm", "operator")
        self.kho.tao_agent(B["id"], "B thử nghiệm", "operator")
        self.units = DonVi(self.kho)

    def test_tao_don_vi_khong_tu_cap_quyen_du_lieu_cho_chu_quan_he_thong(self):
        unit = self.units.create(OWNER, {"name": "Đơn vị A thử nghiệm", "admin": A["id"]})
        self.assertEqual(self.units.list(OWNER), {"units": []})
        self.assertEqual(self.units.list(A)["units"][0]["id"], unit["id"])
        self.assertEqual(self.units.list(B), {"units": []})
        with self.assertRaises(PermissionError):
            self.units.bind(OWNER, unit["id"])
        bound = self.units.bind(A, unit["id"])
        with self.kho.ket_noi() as db:
            self.assertEqual(self.units.require(bound, db).unit_id, unit["id"])

    def test_thu_hoi_va_cap_lai_khong_phuc_hoi_context_cu(self):
        unit = self.units.create(OWNER, {"name": "Đơn vị thử nghiệm", "admin": A["id"]})
        admin = self.units.bind(A, unit["id"])
        self.units.set_member(admin, {"unit_id": unit["id"], "identity": B["id"], "role": "member"})
        before = self.units.bind(B, unit["id"])
        self.units.set_member(admin, {"unit_id": unit["id"], "identity": B["id"], "role": "revoke"})
        with self.kho.ket_noi() as db:
            with self.assertRaises(PermissionError): self.units.require(before, db)
        self.units.set_member(admin, {"unit_id": unit["id"], "identity": B["id"], "role": "member"})
        with self.kho.ket_noi() as db:
            with self.assertRaises(PermissionError): self.units.require(before, db)
            self.assertNotEqual(self.units.require(self.units.bind(B, unit["id"]), db).epoch,
                                before["unit_scope"].epoch)

    def test_quan_tri_don_vi_khong_quan_tri_don_vi_khac_hoac_tu_bo_nguoi_cuoi(self):
        one = self.units.create(OWNER, {"name": "Đơn vị A", "admin": A["id"]})
        two = self.units.create(OWNER, {"name": "Đơn vị B", "admin": B["id"]})
        admin = self.units.bind(A, one["id"])
        with self.assertRaises(PermissionError): self.units.members(admin, two["id"])
        with self.assertRaises(PermissionError):
            self.units.set_member(admin, {"unit_id": two["id"], "identity": A["id"], "role": "admin"})
        with self.assertRaises(ValueError):
            self.units.set_member(admin, {"unit_id": one["id"], "identity": A["id"], "role": "revoke"})
        self.assertEqual(self.units.members(admin, one["id"])["members"][0]["role"], "admin")

    def test_khong_tin_context_json_quan_tri_gia_hoac_context_tu_registry_khac(self):
        unit = self.units.create(OWNER, {"name": "Đơn vị A", "admin": A["id"]})
        valid = self.units.bind(A, unit["id"])
        for forged in ({**A, "unit_scope": {"unit_id": unit["id"]}},
                       {**valid, "id": B["id"]}, {**valid, "role": "quan-tri"}):
            with self.kho.ket_noi() as db:
                with self.assertRaises(PermissionError): self.units.require(forged, db)
        other = DonVi(self.kho)
        with self.kho.ket_noi() as db:
            with self.assertRaises(PermissionError): other.require(valid, db)
        with self.assertRaises(PermissionError): self.units.create(A, {"name":"Đơn vị giả", "admin":A["id"]})

    def test_thu_hoi_danh_tinh_toan_cong_vo_hieu_scope_con_membership(self):
        unit = self.units.create(OWNER,{"name":"Đơn vị thử", "admin":A["id"]})
        bound = self.units.bind(A,unit["id"])
        self.kho.thu_hoi_agent(A["id"])
        with self.kho.ket_noi() as db:
            with self.assertRaises(PermissionError): self.units.require(bound,db)
        with self.assertRaises(PermissionError): self.units.bind(A,unit["id"])

    def test_hai_quan_tri_cung_ha_quyen_van_giu_it_nhat_mot_nguoi(self):
        unit = self.units.create(OWNER,{"name":"Đơn vị thử", "admin":A["id"]})
        self.units.set_member(OWNER,{"unit_id":unit["id"],"identity":B["id"],"role":"admin"})
        actors = [self.units.bind(actor,unit["id"]) for actor in (A,B)]
        barrier, lock = threading.Barrier(2),threading.Lock()
        results = []
        def demote(actor):
            barrier.wait(timeout=5)
            try:
                self.units.set_member(actor,{"unit_id":unit["id"],"identity":actor["id"],"role":"member"})
                result = "changed"
            except ValueError: result = "kept-admin"
            with lock: results.append(result)
        threads = [threading.Thread(target=demote,args=(actor,)) for actor in actors]
        for thread in threads: thread.start()
        for thread in threads:
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
        self.assertEqual(sorted(results),["changed","kept-admin"])
        self.assertEqual(sum(member["role"]=="admin" for member in self.units.members(OWNER,unit["id"])["members"]),1)


if __name__ == "__main__":
    unittest.main()
