"""Luồng dự án/tệp thật trong SQLite tạm; không lắp gateway đa đơn vị."""
import tempfile
import unittest

from kho import Kho
from don_vi import DonVi
from du_an import DuAn
from van_phong import VanPhong
from tai_lieu import TaiLieu
from pathlib import Path
from sao_luu_he_thong import backup, restore

OWNER = {"id": "chu-quan", "role": "quan-tri"}
A = {"id": "operator-a", "role": "operator"}
B = {"id": "operator-b", "role": "operator"}


class Scanner:
    def status(self): return {"state":"test-only"}
    def scan(self, raw):
        import hashlib
        return {"virus_state":"khong-phat-hien", "sha256":hashlib.sha256(raw).hexdigest()}


class ThuDuAnDonVi(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kho = Kho(Path(self.temp.name)/"data")
        self.kho.tao_chu("synthetic-password-only")
        for actor in (A, B): self.kho.tao_agent(actor["id"], actor["id"], "operator")
        self.units = DonVi(self.kho)
        self.one = self.units.create(OWNER, {"name":"Đơn vị A thử", "admin":A["id"]})["id"]
        self.two = self.units.create(OWNER, {"name":"Đơn vị B thử", "admin":B["id"]})["id"]
        self.units.set_member(OWNER, {"unit_id":self.two, "identity":A["id"], "role":"member"})
        self.a1, self.a2 = self.units.bind(A, self.one), self.units.bind(A, self.two)
        self.b2 = self.units.bind(B, self.two)
        self.projects = DuAn(self.kho, units=self.units)
        self.office = VanPhong(self.kho, self.projects, scanner=Scanner())

    def create(self, actor, name="Dự án thử nghiệm"):
        return self.projects.create(actor, {"name":name, "context":"Nội dung tổng hợp"})

    def test_cung_danh_tinh_o_hai_don_vi_khong_lan_du_an_va_tep(self):
        one = self.create(self.a1, "Dự án A")
        two = self.create(self.a2, "Dự án B")
        self.assertEqual([p["id"] for p in self.projects.list(self.a1)["projects"]], [one["id"]])
        self.assertEqual([p["id"] for p in self.projects.list(self.a2)["projects"]], [two["id"]])
        file = self.office.create_bytes(self.a1, one["id"], "thu.txt", b"synthetic content")
        self.assertEqual(self.office.read(self.a1, {"id":file["id"]})["content_base64"], "c3ludGhldGljIGNvbnRlbnQ=")
        for actor in (self.a2, self.b2):
            with self.assertRaises(ValueError): self.projects.authorize(actor, one["id"])
            with self.assertRaises(ValueError): self.office.read(actor, {"id":file["id"]})

    def test_chia_se_dich_danh_theo_don_vi_khong_cho_quyen_chia_se_tiep(self):
        project = self.create(self.a1)
        self.projects.share(self.a1, {"id":project["id"], "identity":B["id"], "unit_id":self.two, "role":"viewer"})
        self.assertEqual(self.projects.authorize(self.b2, project["id"])["unit_id"], self.one)
        self.assertEqual(self.projects.context_for(self.b2,project["id"])["source_unit_id"],self.one)
        self.assertEqual(self.b2["unit_scope"].unit_id,self.two)
        with self.assertRaises(ValueError): self.projects.update(self.b2, {"id":project["id"], "name":"Tên mới thử"})
        self.assertFalse(self.office.status(self.b2, {"project_id":project["id"]})["permissions"]["can_write"])
        self.projects.share(self.a1, {"id":project["id"], "identity":B["id"], "unit_id":self.two, "role":"editor"})
        self.projects.update(self.b2, {"id":project["id"], "name":"Tên mới thử"})
        self.office.create_bytes(self.b2, project["id"], "thu.txt", b"synthetic")
        with self.assertRaises(ValueError):
            self.projects.share(self.b2, {"id":project["id"], "identity":A["id"], "unit_id":self.two, "role":"viewer"})
        self.projects.share(self.a1, {"id":project["id"], "identity":B["id"], "unit_id":self.two, "role":"revoke"})
        with self.assertRaises(ValueError): self.projects.authorize(self.b2, project["id"])

    def test_quan_tri_he_thong_va_quan_tri_don_vi_khong_co_quyen_noi_dung_mac_dinh(self):
        project = self.create(self.a2)
        with self.assertRaises(ValueError): self.projects.authorize(self.b2, project["id"])
        self.units.set_member(OWNER, {"unit_id":self.two, "identity":"chu-quan", "role":"admin"})
        root = self.units.bind(OWNER, self.two)
        with self.assertRaises(ValueError): self.projects.authorize(root, project["id"])
        self.projects.share(self.a2, {"id":project["id"], "identity":"chu-quan", "unit_id":self.two, "role":"viewer"})
        self.assertFalse(self.office.status(root, {"project_id":project["id"]})["permissions"]["can_write"])
        with self.assertRaises(ValueError): self.office.create_bytes(root, project["id"], "thu.txt", b"synthetic")

    def test_cap_lai_membership_khong_lam_song_lai_grant_cu(self):
        project = self.create(self.a1)
        self.projects.share(self.a1, {"id":project["id"], "identity":A["id"], "unit_id":self.two, "role":"viewer"})
        self.projects.authorize(self.a2, project["id"])
        self.units.set_member(self.b2, {"unit_id":self.two, "identity":A["id"], "role":"revoke"})
        self.units.set_member(self.b2, {"unit_id":self.two, "identity":A["id"], "role":"member"})
        with self.assertRaises(PermissionError): self.projects.authorize(self.a2, project["id"])
        renewed = self.units.bind(A, self.two)
        with self.assertRaises(ValueError): self.projects.authorize(renewed, project["id"])

    def test_tai_lieu_kiem_lai_quyen_sau_scan_va_khong_ghi_khi_bi_thu_hoi(self):
        project = self.create(self.a1)
        self.units.set_member(self.a1, {"unit_id":self.one,"identity":B["id"],"role":"member"})
        b1 = self.units.bind(B,self.one)
        self.projects.share(self.a1,{"id":project["id"],"unit_id":self.one,"identity":B["id"],"role":"editor"})
        units, one = self.units,self.one
        class RevokeScanner(Scanner):
            def scan(self, raw):
                units.set_member(OWNER,{"unit_id":one,"identity":B["id"],"role":"revoke"})
                return super().scan(raw)
        docs = TaiLieu(self.kho,self.projects)
        docs.scanner = RevokeScanner()
        with self.assertRaises(PermissionError):
            docs.upload(b1,{"project_id":project["id"],"name":"thu.txt","content_base64":"c3ludGhldGlj"})
        self.assertEqual(docs.list(self.a1,project["id"]),{"documents":[]})

    def test_thu_hoi_trong_scan_office_chan_commit_nhung_khong_chan_nguoi_con_quyen(self):
        project = self.create(self.a1)
        self.projects.share(self.a1,{"id":project["id"],"unit_id":self.two,"identity":B["id"],"role":"editor"})
        projects, actor, target_unit = self.projects,self.a1,self.two
        class RevokeScanner(Scanner):
            def scan(self, raw):
                projects.share(actor,{"id":project["id"],"unit_id":target_unit,"identity":B["id"],"role":"revoke"})
                return super().scan(raw)
        office = VanPhong(self.kho,self.projects,scanner=RevokeScanner())
        with self.assertRaises(ValueError): office.create_bytes(self.b2,project["id"],"thu.txt",b"synthetic")
        self.office.create_bytes(self.a1,project["id"],"van-duoc.txt",b"synthetic")
        self.assertEqual(len(self.office.list(self.a1,{"project_id":project["id"]})["files"]),1)

    def test_sao_luu_phuc_hoi_giu_pham_vi_grant_va_byte_tep(self):
        project = self.create(self.a1)
        file = self.office.create_bytes(self.a1,project["id"],"thu.txt",b"synthetic content")
        self.projects.share(self.a1,{"id":project["id"],"unit_id":self.two,"identity":B["id"],"role":"viewer"})
        root = Path(self.temp.name)
        backup(self.kho.root,root/"snapshot")
        restore(root/"snapshot",root/"restore")
        restored = Kho(root/"restore/data")
        units = DonVi(restored)
        projects = DuAn(restored,units=units)
        office = VanPhong(restored,projects,scanner=Scanner())
        b = units.bind(B,self.two)
        self.assertEqual(office.read(b,{"id":file["id"]})["content_base64"],"c3ludGhldGljIGNvbnRlbnQ=")
        self.assertEqual(projects.list(units.bind(A,self.two))["projects"],[])
        with self.assertRaises(PermissionError): projects.authorize(self.a1,project["id"])

    def test_thieu_scope_va_duong_cu_khong_duoc_tu_roi_ve_quyen_toan_cong(self):
        project = self.create(self.a1)
        for actor in (A,OWNER,{**A,"unit_id":self.one}):
            with self.assertRaises(PermissionError): self.projects.authorize(actor,project["id"])
        with self.assertRaises(PermissionError): DuAn(self.kho).list(OWNER)
        with self.assertRaises(PermissionError): DuAn(self.kho).create(A,{"name":"Không được rơi về cũ"})

    def test_doi_vai_don_vi_can_scope_moi_nhung_khong_lam_mat_chia_se_dang_hop_le(self):
        project = self.create(self.a1)
        self.projects.share(self.a1,{"id":project["id"],"unit_id":self.two,"identity":A["id"],"role":"viewer"})
        self.units.set_member(self.b2,{"unit_id":self.two,"identity":A["id"],"role":"admin"})
        with self.assertRaises(PermissionError): self.projects.authorize(self.a2,project["id"])
        self.projects.authorize(self.units.bind(A,self.two),project["id"])

    def test_gateway_chua_hieu_don_vi_dung_truoc_khi_tao_worker(self):
        from may_chu import UngDung
        with self.assertRaises(PermissionError): UngDung(self.kho.root,"https://example.invalid",True)


if __name__ == "__main__": unittest.main()
