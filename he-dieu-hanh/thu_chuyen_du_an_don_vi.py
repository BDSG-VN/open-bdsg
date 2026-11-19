"""Migration giữ nội dung và quyền cũ, không chọn doanh nghiệp theo tên/email."""
import tempfile
import unittest

from kho import Kho
from don_vi import DonVi
from du_an import DuAn
from van_phong import VanPhong
from chuyen_du_an_don_vi import migrate_legacy
from thu_du_an_don_vi import Scanner, A, B, OWNER


class ThuChuyenDonVi(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kho = Kho(self.temp.name)
        self.kho.tao_chu("synthetic-password-only")
        for actor in (A, B): self.kho.tao_agent(actor["id"], actor["id"], "operator")
        self.old = DuAn(self.kho)
        self.project = self.old.create(A, {"name":"Dự án cũ thử nghiệm", "context":"Giữ nguyên ngữ cảnh tổng hợp"})
        self.old.share(A, {"id":self.project["id"], "identity":B["id"], "role":"viewer"})
        self.old_office = VanPhong(self.kho, self.old, scanner=Scanner())
        self.file = self.old_office.create_bytes(A, self.project["id"], "cu.txt", b"legacy synthetic bytes")
        self.units = DonVi(self.kho)
        self.scoped = DuAn(self.kho, units=self.units)

    def test_migration_giu_id_byte_context_viewer_va_quyen_chu_quan_legacy(self):
        result = migrate_legacy(self.scoped, OWNER)
        self.assertTrue(result["changed"])
        self.assertEqual(result["projects"], 1)
        self.assertFalse(migrate_legacy(self.scoped, OWNER)["changed"])
        a = self.units.bind(A, result["unit_id"])
        b = self.units.bind(B, result["unit_id"])
        root = self.units.bind(OWNER, result["unit_id"])
        self.assertEqual(self.scoped.context_for(a,self.project["id"])["context"], self.project["context"])
        self.scoped.authorize(root,self.project["id"],owner=True)
        with self.assertRaises(ValueError): self.scoped.authorize(b,self.project["id"],write=True)
        office = VanPhong(self.kho,self.scoped,scanner=Scanner())
        self.assertEqual(office.read(b,{"id":self.file["id"]})["content_base64"], "bGVnYWN5IHN5bnRoZXRpYyBieXRlcw==")
        with self.assertRaises(PermissionError): self.old.list(OWNER)
        with self.assertRaises(PermissionError): DuAn(self.kho).list(OWNER)
        other = self.units.create(OWNER,{"name":"Đơn vị mới thử", "admin":B["id"]})
        self.assertEqual(self.scoped.list(self.units.bind(B,other["id"]))["projects"], [])

    def test_orphan_chan_migration_va_khong_sua_mat_du_lieu(self):
        # Fixture lỗi của bản cũ: schema không có khóa ngoại project.
        with self.kho.ket_noi() as db:
            db.execute("INSERT INTO office_files VALUES('orphan','missing','cu.txt','operator-a',1,1,0,0,0)")
        with self.assertRaises(ValueError): migrate_legacy(self.scoped,OWNER)
        self.assertEqual(self.units.list(A),{"units":[]})
        self.assertEqual(self.old.context_for(A,self.project["id"])["context"],self.project["context"])

    def test_operator_khong_duoc_migration(self):
        with self.assertRaises(PermissionError): migrate_legacy(self.scoped,A)
        self.assertEqual(self.units.list(A),{"units":[]})

    def test_ban_cu_chen_them_du_an_khong_duoc_tu_gan_vao_legacy(self):
        result = migrate_legacy(self.scoped,OWNER)
        # Mô phỏng writer cũ không đi qua Module sau cutover.
        with self.kho.ket_noi() as db:
            db.execute("INSERT INTO du_an VALUES('late','operator-a','Dự án chưa phân loại','','',0,0,0)")
        with self.assertRaises(ValueError): migrate_legacy(self.scoped,OWNER)
        actor = self.units.bind(A,result["unit_id"])
        self.assertEqual(len(self.scoped.list(actor)["projects"]),1)
        with self.assertRaises(ValueError): self.scoped.authorize(actor,'late')

    def test_chay_lai_migration_van_chan_orphan_moi(self):
        migrate_legacy(self.scoped,OWNER)
        with self.kho.ket_noi() as db:
            db.execute("INSERT INTO office_files VALUES('orphan','missing','cu.txt','operator-a',1,1,0,0,0)")
        with self.assertRaises(ValueError): migrate_legacy(self.scoped,OWNER)


if __name__ == "__main__": unittest.main()
