"""Yêu cầu và phiên tải Office theo đơn vị, chỉ SQLite tổng hợp tạm."""
import base64
import concurrent.futures
import hashlib
import tempfile
import unittest
from pathlib import Path

from kho import Kho
from don_vi import DonVi
from du_an import DuAn
from van_phong import VanPhong, LoiXungDotVanPhong, LoiHanMucVanPhong
from chuyen_du_an_don_vi import migrate_legacy as migrate_projects
from chuyen_yeu_cau_office_don_vi import migrate_legacy
from sao_luu_he_thong import backup, restore

OWNER = {"id":"chu-quan","role":"quan-tri"}
A = {"id":"operator-a","role":"operator"}
B = {"id":"operator-b","role":"operator"}
RAW = b"synthetic office content"
KEY = "a" * 32

class Scanner:
    def status(self): return {"state":"test-only"}
    def scan(self, raw): return {"sha256":hashlib.sha256(raw).hexdigest(),"virus_state":"khong-phat-hien"}

class ThuYeuCauOfficeDonVi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.kho = Kho(Path(self.tmp.name)/'data')
        self.kho.tao_chu('synthetic-password-only')
        for actor in (A,B): self.kho.tao_agent(actor['id'],actor['id'],'operator')
        self.units = DonVi(self.kho)
        self.one = self.units.create(OWNER,{'name':'Đơn vị A thử','admin':A['id']})['id']
        self.two = self.units.create(OWNER,{'name':'Đơn vị B thử','admin':B['id']})['id']
        self.units.set_member(OWNER,{'unit_id':self.two,'identity':A['id'],'role':'member'})
        self.a1,self.a2 = self.units.bind(A,self.one),self.units.bind(A,self.two)
        self.projects = DuAn(self.kho,units=self.units)
        self.office = VanPhong(self.kho,self.projects,Scanner())
        self.project = self.projects.create(self.a1,{'name':'Dự án tổng hợp'})['id']
        self.projects.share(self.a1,{'id':self.project,'unit_id':self.two,'identity':A['id'],'role':'editor'})

    def begin(self, actor, key=KEY, **extra):
        return self.office.begin_upload(actor,{'project_id':self.project,'name':'thu.txt',
            'total':len(RAW),'sha256':hashlib.sha256(RAW).hexdigest(),'request_key':key,**extra})

    def part(self, actor, identifier):
        return self.office.upload_part(actor,{'id':identifier,'offset':0,'content_base64':base64.b64encode(RAW).decode()})

    def test_cung_khoa_hai_don_vi_tao_doc_lap_va_retry_xung_dot(self):
        files = [self.office.create_bytes(actor,self.project,'thu.txt',RAW,KEY) for actor in (self.a1,self.a2)]
        self.assertNotEqual(files[0]['id'],files[1]['id'])
        for actor,file in zip((self.a1,self.a2),files):
            self.assertEqual(self.office.create_bytes(actor,self.project,'thu.txt',RAW,KEY)['id'],file['id'])
            with self.assertRaises(LoiXungDotVanPhong): self.office.create_bytes(actor,self.project,'khac.txt',RAW,KEY)
        uploads = [self.begin(actor) for actor in (self.a1,self.a2)]
        self.assertNotEqual(uploads[0]['id'],uploads[1]['id'])
        for actor,upload in zip((self.a1,self.a2),uploads):
            self.assertEqual(self.begin(actor)['id'],upload['id'])
            with self.assertRaises(LoiXungDotVanPhong): self.begin(actor,name='khac.txt')

    def test_du_an_chia_se_khong_cho_doc_tiep_tuc_ghi_huy_upload_don_vi_khac(self):
        upload = self.begin(self.a1)
        self.assertEqual(self.office.uploads(self.a2,{'project_id':self.project}),{'uploads':[]})
        self.assertEqual(self.office.status(self.a2,{'project_id':self.project})['transfer_usage'],{'pending':0,'reserved_bytes':0})
        for operation in (self.office.upload_status,self.office.finish_upload,self.office.cancel_upload):
            with self.assertRaises(ValueError): operation(self.a2,{'id':upload['id']})
        with self.assertRaises(ValueError): self.part(self.a2,upload['id'])
        self.part(self.a1,upload['id'])
        result = self.office.finish_upload(self.a1,{'id':upload['id']})
        self.assertEqual(self.office.finish_upload(self.a1,{'id':upload['id']})['file']['id'],result['file']['id'])
        with self.assertRaises(ValueError): self.office.finish_upload(self.a2,{'id':upload['id']})

    def test_han_muc_pending_tach_theo_danh_tinh_don_vi_va_huy_retry(self):
        self.begin(self.a1)
        self.begin(self.a1,'b'*32)
        with self.assertRaises(LoiHanMucVanPhong): self.begin(self.a1,'c'*32)
        self.units.set_member(OWNER,{'unit_id':self.one,'identity':B['id'],'role':'member'})
        self.projects.share(self.a1,{'id':self.project,'unit_id':self.one,'identity':B['id'],'role':'editor'})
        b1 = self.units.bind(B,self.one)
        self.begin(b1)
        self.assertEqual(self.office.status(b1,{'project_id':self.project})['transfer_usage']['pending'],1)
        upload = self.begin(self.a2)
        self.assertEqual(self.office.status(self.a2,{'project_id':self.project})['transfer_usage']['pending'],1)
        self.office.cancel_upload(self.a2,{'id':upload['id']})
        self.assertNotEqual(self.begin(self.a2)['id'],upload['id'])

    def test_retry_dong_thoi_chi_tao_mot_file_va_mot_upload(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(lambda _:self.office.create_bytes(self.a1,self.project,'thu.txt',RAW,KEY)['id'],range(4)))
            uploads = list(pool.map(lambda _:self.begin(self.a1)['id'],range(4)))
        self.assertEqual(len(set(ids)),1)
        self.assertEqual(len(set(uploads)),1)
        self.assertEqual(len(self.office.list(self.a1,{'project_id':self.project})['files']),1)

    def test_thu_hoi_trong_scan_chan_commit_upload(self):
        upload = self.begin(self.a2)
        self.part(self.a2,upload['id'])
        projects, a1, project, two = self.projects,self.a1,self.project,self.two
        class RevokeScanner(Scanner):
            def scan(self,raw):
                projects.share(a1,{'id':project,'unit_id':two,'identity':A['id'],'role':'revoke'})
                return super().scan(raw)
        self.office.scanner = RevokeScanner()
        with self.assertRaises(ValueError): self.office.finish_upload(self.a2,{'id':upload['id']})
        self.assertEqual(self.office.list(self.a1,{'project_id':self.project})['files'],[])

    def test_doi_scope_trong_scan_khong_chuyen_commit_sang_don_vi_khac(self):
        actor = dict(self.a1)
        other_scope = self.a2['unit_scope']
        class ChangeScanner(Scanner):
            def scan(self,raw):
                actor['unit_scope'] = other_scope
                return super().scan(raw)
        self.office.scanner = ChangeScanner()
        with self.assertRaises(PermissionError):
            self.office.create_bytes(actor,self.project,'thu.txt',RAW,KEY)
        self.assertEqual(self.office.list(self.a1,{'project_id':self.project})['files'],[])

    def test_huy_trong_scan_khong_commit_upload_da_huy(self):
        upload = self.begin(self.a1)
        self.part(self.a1,upload['id'])
        office, actor = self.office,self.a1
        class CancelScanner(Scanner):
            def scan(self,raw):
                office.cancel_upload(actor,{'id':upload['id']})
                return super().scan(raw)
        self.office.scanner = CancelScanner()
        with self.assertRaises(ValueError): self.office.finish_upload(self.a1,{'id':upload['id']})
        self.assertEqual(self.office.list(self.a1,{'project_id':self.project})['files'],[])

    def test_restart_va_backup_phuc_hoi_giu_upload_va_idempotency(self):
        file = self.office.create_bytes(self.a2,self.project,'thu.txt',RAW,KEY)
        upload = self.begin(self.a2)
        self.part(self.a2,upload['id'])
        restart = VanPhong(self.kho,self.projects,Scanner())
        self.assertEqual(restart.upload_status(self.a2,{'id':upload['id']})['received'],len(RAW))
        root = Path(self.tmp.name)
        backup(self.kho.root,root/'snapshot')
        restore(root/'snapshot',root/'restored')
        kho = Kho(root/'restored/data')
        units = DonVi(kho)
        office = VanPhong(kho,DuAn(kho,units=units),Scanner())
        actor = units.bind(A,self.two)
        self.assertEqual(office.create_bytes(actor,self.project,'thu.txt',RAW,KEY)['id'],file['id'])
        self.assertEqual(office.finish_upload(actor,{'id':upload['id']})['completed'],True)
        with self.assertRaises(ValueError): office.upload_status(units.bind(A,self.one),{'id':upload['id']})

class ThuChuyenYeuCauOfficeDonVi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.kho = Kho(Path(self.tmp.name)/'data')
        self.kho.tao_chu('synthetic-password-only')
        self.kho.tao_agent(A['id'],A['id'],'operator')
        projects = DuAn(self.kho)
        old = VanPhong(self.kho,projects,Scanner())
        self.pid = projects.create(A,{'name':'Dự án legacy tổng hợp'})['id']
        self.file = old.create_bytes(A,self.pid,'thu.txt',RAW,KEY)
        self.upload = old.begin_upload(A,{'project_id':self.pid,'name':'thu.txt','total':len(RAW),
            'sha256':hashlib.sha256(RAW).hexdigest(),'request_key':KEY})
        self.upload = old.upload_part(A,{'id':self.upload['id'],'offset':0,'content_base64':base64.b64encode(RAW).decode()})
        self.units = DonVi(self.kho)
        self.projects = DuAn(self.kho,units=self.units)
        self.legacy = migrate_projects(self.projects,OWNER)['unit_id']
        self.actor = self.units.bind(A,self.legacy)
        self.office = VanPhong(self.kho,self.projects,Scanner())

    def test_chua_phan_loai_dong_den_va_migration_giu_id_byte_expiry(self):
        with self.assertRaises(ValueError): self.office.upload_status(self.actor,{'id':self.upload['id']})
        with self.assertRaises(ValueError): self.office.create_bytes(self.actor,self.pid,'thu.txt',RAW,KEY)
        self.assertEqual(self.office.uploads(self.actor,{'project_id':self.pid}),{'uploads':[]})
        with self.assertRaises(ValueError): migrate_legacy(self.office,OWNER)
        self.assertTrue(migrate_legacy(self.office,OWNER,copy_only=True)['changed'])
        self.assertFalse(migrate_legacy(self.office,OWNER,copy_only=True)['changed'])
        self.assertEqual(self.office.create_bytes(self.actor,self.pid,'thu.txt',RAW,KEY)['id'],self.file['id'])
        upload = self.office.upload_status(self.actor,{'id':self.upload['id']})
        self.assertEqual(upload['expires'],self.upload['expires'])
        self.assertEqual(upload['received'],len(RAW))
        result = self.office.finish_upload(self.actor,{'id':self.upload['id']})
        self.assertEqual(self.office.read(self.actor,{'id':result['file']['id']})['content_base64'],base64.b64encode(RAW).decode())

    def test_nguon_da_co_don_vi_moi_khong_suy_scope_tu_du_an(self):
        self.units.create(OWNER,{'name':'Đơn vị khác tổng hợp','admin':A['id']})
        with self.assertRaises(ValueError): migrate_legacy(self.office,OWNER,copy_only=True)
        with self.assertRaises(ValueError): self.office.upload_status(self.actor,{'id':self.upload['id']})

    def test_chay_lai_marker_khong_che_yeu_cau_chua_phan_loai(self):
        migrate_legacy(self.office,OWNER,copy_only=True)
        with self.kho.ket_noi() as db:
            db.execute('INSERT INTO office_creates VALUES(?,?,?,?,?,?)',
                (A['id'],'b'*32,self.pid,'thu.txt',hashlib.sha256(RAW).hexdigest(),self.file['id']))
        with self.assertRaises(ValueError): migrate_legacy(self.office,OWNER,copy_only=True)
        with self.assertRaises(ValueError): self.office.create_bytes(self.actor,self.pid,'thu.txt',RAW,'b'*32)

    def test_chay_lai_chan_writer_cu_va_yeu_cau_mo_coi(self):
        migrate_legacy(self.office,OWNER,copy_only=True)
        # Mô phỏng writer legacy trên bản sao bằng public interface cũ đã bị chặn.
        old = VanPhong(self.kho,DuAn(self.kho),Scanner())
        with self.assertRaises(PermissionError): old.create_bytes(A,self.pid,'cu.txt',RAW,'b'*32)
        # Fixture raw giữ nguyên số cột legacy; dữ liệu hỏng không được marker che khuất.
        with self.kho.ket_noi() as db:
            db.execute('INSERT INTO office_creates VALUES(?,?,?,?,?,?)',(A['id'],'b'*32,'missing','cu.txt',hashlib.sha256(RAW).hexdigest(),self.file['id']))
        with self.assertRaises(ValueError): migrate_legacy(self.office,OWNER,copy_only=True)

if __name__ == '__main__': unittest.main()
