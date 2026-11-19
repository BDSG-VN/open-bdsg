"""Tác vụ giữ đơn vị và quyền đã giao, không dùng chứng thư provider toàn cổng."""
import tempfile
import threading
import time
import unittest
from pathlib import Path

from kho import Kho
from don_vi import DonVi
from du_an import DuAn
from cong_viec import CongViec
from thu_cong_viec import NhanThu, MoHinhTat, A, B, OWNER


class ThuCongViecDonVi(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kho = Kho(Path(self.temp.name)/'data')
        self.kho.tao_chu('synthetic-password-only')
        for actor in (A,B): self.kho.tao_agent(actor['id'],actor['name'],'operator')
        self.units = DonVi(self.kho)
        self.one = self.units.create(OWNER,{'name':'Đơn vị A thử','admin':A['id']})['id']
        self.two = self.units.create(OWNER,{'name':'Đơn vị B thử','admin':A['id']})['id']
        self.units.set_member(OWNER,{'unit_id':self.one,'identity':B['id'],'role':'admin'})
        self.a1,self.a2 = self.units.bind(A,self.one),self.units.bind(A,self.two)
        self.core = NhanThu()
        self.tasks = CongViec(self.kho,self.core,units=self.units)
        self.tasks.model = MoHinhTat()
        self.tasks.projects = DuAn(self.kho,units=self.units)
        self.addCleanup(self.stop)

    def stop(self):
        if self.core.block: self.core.block.set()
        self.tasks.close()

    def create(self,actor,**extra):
        return self.tasks.create(actor,{'prompt':'Tạo đề xuất kinh doanh bằng danh mục công khai','template':'de-xuat-giai-phap',**extra})['id']

    def finished(self,actor,identifier):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            task=self.tasks.detail(actor,identifier)
            if task['status'] in ('completed','failed','cancelled','interrupted'): return task
            time.sleep(.01)
        self.fail('Tác vụ không kết thúc trong thời gian kiểm')

    def test_cung_identity_khong_doc_hoac_dieu_khien_tac_vu_don_vi_khac(self):
        one=self.create(self.a1);two=self.create(self.a2)
        self.assertEqual(self.finished(self.a1,one)['status'],'completed')
        self.assertEqual(self.finished(self.a2,two)['status'],'completed')
        self.assertEqual([t['id'] for t in self.tasks.list(self.a1)['tasks']],[one])
        self.assertEqual([t['id'] for t in self.tasks.list(self.a2)['tasks']],[two])
        for operation in (lambda:self.tasks.detail(self.a2,one),lambda:self.tasks.cancel(self.a2,one),
                          lambda:self.tasks.followup(self.a2,one,'Yêu cầu bổ sung từ đơn vị sai')):
            with self.assertRaises(ValueError): operation()
        self.assertNotIn('nen_tang.ket_noi',[call[1] for call in self.core.calls])

    def test_json_khong_tu_chon_don_vi_va_thieu_scope_bi_chan(self):
        with self.assertRaises(PermissionError): self.create(A,unit_id=self.one)
        identifier=self.create(self.a1,unit_id=self.two)
        self.assertEqual(self.finished(self.a1,identifier)['unit_id'],self.one)

    def pause(self,actor,**extra):
        self.core.block=threading.Event()
        identifier=self.create(actor,**extra)
        self.assertTrue(self.core.entered.wait(3),'Worker không tới giao diện công cụ đọc')
        return identifier

    def test_doi_don_vi_tren_caller_khong_doi_don_vi_worker(self):
        identifier=self.pause(self.a1)
        self.a1['unit_scope']=self.a2['unit_scope']
        self.core.block.set()
        result=self.finished(self.units.bind(A,self.one),identifier)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['unit_id'],self.one)

    def test_revoke_rejoin_chan_ket_qua_cu_va_chi_tiep_tuc_khi_cap_lai_ro_rang(self):
        identifier=self.pause(self.a1)
        args={'unit_id':self.one,'identity':A['id']}
        self.units.set_member(OWNER,{**args,'role':'revoke'})
        self.units.set_member(OWNER,{**args,'role':'member'})
        renewed=self.units.bind(A,self.one)
        self.core.block.set()
        stopped=self.finished(renewed,identifier)
        self.assertEqual(stopped['status'],'failed')
        self.assertEqual(stopped['artifacts'],[])
        with self.assertRaises(PermissionError): self.tasks.detail(self.a1,identifier)
        self.tasks.followup(renewed,identifier,'Tiếp tục sau khi đã cấp quyền lại rõ ràng')
        self.assertEqual(self.finished(renewed,identifier)['status'],'completed')

    def test_doi_vai_vong_khong_phuc_hoi_quyen_worker(self):
        identifier=self.pause(self.a1)
        args={'unit_id':self.one,'identity':A['id']}
        self.units.set_member(OWNER,{**args,'role':'member'})
        self.units.set_member(OWNER,{**args,'role':'admin'})
        self.core.block.set()
        stopped=self.finished(self.units.bind(A,self.one),identifier)
        self.assertEqual(stopped['status'],'failed')
        self.assertEqual(stopped['artifacts'],[])

    def test_rut_chia_se_du_an_chan_xuat_ban_tu_snapshot_da_chup(self):
        project=self.tasks.projects.create(self.a1,{'name':'Dự án nguồn thử','context':'Ngữ cảnh tổng hợp riêng'})
        grant={'id':project['id'],'unit_id':self.two,'identity':A['id']}
        self.tasks.projects.share(self.a1,{**grant,'role':'viewer'})
        identifier=self.pause(self.a2,project_id=project['id'])
        self.tasks.projects.share(self.a1,{**grant,'role':'revoke'})
        self.core.block.set()
        stopped=self.finished(self.a2,identifier)
        self.assertEqual(stopped['status'],'failed')
        self.assertEqual(stopped['artifacts'],[])

    def test_huy_van_giu_ket_qua_den_muon_khong_duoc_xuat_ban(self):
        identifier=self.pause(self.a1)
        self.tasks.cancel(self.a1,identifier)
        self.core.block.set()
        self.assertEqual(self.finished(self.a1,identifier)['artifacts'],[])
        self.assertEqual(self.finished(self.a1,identifier)['status'],'cancelled')

    def test_quan_tri_he_thong_khong_doc_tac_vu_cua_nguoi_khac(self):
        identifier=self.create(self.a1)
        self.finished(self.a1,identifier)
        self.units.set_member(OWNER,{'unit_id':self.one,'identity':OWNER['id'],'role':'member'})
        root=self.units.bind(OWNER,self.one)
        self.assertEqual(self.tasks.list(root),{'tasks':[]})
        with self.assertRaises(ValueError): self.tasks.detail(root,identifier)

    def test_khong_dung_mo_hinh_hoac_ngan_sach_toan_cong(self):
        class Configured(MoHinhTat): configured=True
        self.tasks.model=Configured()
        with self.assertRaises(PermissionError): self.create(self.a1)
        with self.assertRaises(PermissionError): self.tasks.reserve_model(self.a1)
        self.assertEqual(self.tasks.list(self.a1),{'tasks':[]})

    def test_restart_giu_pham_vi_va_followup_dung_danh_tinh_da_luu(self):
        identifier=self.create(self.a1)
        self.finished(self.a1,identifier)
        self.tasks.close()
        units=DonVi(self.kho)
        restarted=CongViec(self.kho,NhanThu(),units=units)
        self.addCleanup(restarted.close)
        restarted.projects=DuAn(self.kho,units=units)
        restarted.model=MoHinhTat()
        actor=units.bind(A,self.one)
        self.assertEqual(restarted.detail(actor,identifier)['unit_id'],self.one)
        with self.assertRaises(ValueError): restarted.detail(units.bind(A,self.two),identifier)
        restarted.followup(actor,identifier,'Tiếp tục sau khởi động lại với phạm vi đã lưu')
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            result=restarted.detail(actor,identifier)
            if result['status'] in ('completed','failed'): break
            time.sleep(.01)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['run'],2)

    def test_future_da_huy_khong_chay_trung_luot_duoc_cap_lai(self):
        self.core.block=threading.Event()
        first=self.create(self.a1);second=self.create(self.a2)
        deadline=time.monotonic()+3
        while len(self.core.calls)<2 and time.monotonic()<deadline: time.sleep(.01)
        self.assertEqual(len(self.core.calls),2)
        queued=self.create(self.a1)
        self.tasks.cancel(self.a1,queued)
        self.tasks.followup(self.a1,queued,'Chạy lượt mới sau khi đã hủy lượt đang xếp hàng')
        self.core.block.set()
        self.finished(self.a1,first);self.finished(self.a2,second)
        self.finished(self.a1,queued)
        self.tasks.close()
        result=self.tasks.detail(self.a1,queued)
        self.assertEqual(result['status'],'completed')
        self.assertEqual([artifact['run'] for artifact in result['artifacts']],[2])
        self.assertEqual(len([step for step in result['steps'] if step['run']==2]),3)
