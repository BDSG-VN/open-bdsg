"""Hạn mức AI theo phạm vi sống; toàn bộ dữ liệu kiểm thử là tổng hợp."""
import json
import tempfile
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from sao_luu_he_thong import backup, restore
from du_an import DuAn

from kho import Kho
from don_vi import DonVi
from ngan_sach_ai import DEFAULT_POLICY, NganSachAI
from mo_hinh_bdsg import LoiMoHinhBDSG

ROOT = {'id':'chu-quan','role':'quan-tri'}
USER = {'id':'budget-user','role':'operator'}
PRICES = {'input_per_million':'1','output_per_million':'1'}


class ThuNganSachDonVi(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kho = Kho(self.temp.name)
        self.kho.tao_chu('synthetic-password-only')
        self.kho.tao_agent(USER['id'],'Người thử','operator')
        self.units = DonVi(self.kho)
        self.a, self.b = [self.units.create(ROOT,{'name':name,'admin':USER['id']})['id']
                          for name in ('Đơn vị A','Đơn vị B')]
        self.aa, self.bb = [self.units.bind(USER,u) for u in (self.a,self.b)]
        self.policy = {**DEFAULT_POLICY,'tasks_per_user':1,'calls_per_user':1}
        self.now = 1000000

    def budget(self, **kwargs):
        return NganSachAI(self.kho,clock=lambda:self.now,units=self.units,**kwargs)

    def task(self,budget,actor,identifier,project_id=''):
        # Dữ liệu tác vụ đáng tin cậy được ghi theo đúng thứ tự của CongViec.create.
        with self.kho.ket_noi() as db:
            db.execute('CREATE TABLE IF NOT EXISTS cong_viec_tasks(id TEXT PRIMARY KEY, owner TEXT, created REAL, updated REAL, status TEXT, document TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS cong_viec_units(task_id TEXT PRIMARY KEY,unit_id TEXT,epoch INTEGER,revision INTEGER)')
            db.execute('BEGIN IMMEDIATE')
            budget.claim_task(db,actor,identifier,1,self.policy,project_id=project_id)
            scope = self.units.require(actor,db)
            document = {'id':identifier,'owner':actor['id'],'unit_id':scope.unit_id,'run':1,'project_id':project_id}
            db.execute('INSERT INTO cong_viec_tasks VALUES(?,?,?,?,?,?)',(identifier,actor['id'],self.now,self.now,'queued',json.dumps(document)))
            db.execute('INSERT INTO cong_viec_units VALUES(?,?,?,?)',(identifier,scope.unit_id,scope.epoch,scope.revision))

    def reserve(self,budget,actor,identifier,**kwargs):
        kwargs.setdefault('run',1)
        return budget.reserve(actor,identifier,'synthetic-model',10,20,PRICES,self.policy,**kwargs)

    def test_cung_danh_tinh_hai_don_vi_co_han_muc_doc_lap(self):
        budget = self.budget()
        self.task(budget,self.aa,'task-a')
        self.reserve(budget,self.aa,'task-a')
        self.assertEqual(budget.status(self.bb,self.policy)['calls_used'],0)
        self.task(budget,self.bb,'task-b')
        self.reserve(budget,self.bb,'task-b')
        self.assertEqual(budget.status(self.aa,self.policy)['tasks_used'],1)
        self.assertEqual(budget.status(self.bb,self.policy)['calls_used'],1)

    def test_tac_vu_don_vi_khac_khong_duoc_cap_luot_moi(self):
        budget = self.budget()
        self.task(budget,self.aa,'task-a')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaises(PermissionError):
                budget.claim_task(db,self.bb,'task-a',2,self.policy)

    def test_thieu_bang_rang_buoc_tac_vu_dong_mac_dinh(self):
        budget = self.budget()
        self.task(budget,self.aa,'task-a')
        with self.kho.ket_noi() as db: db.execute('DROP TABLE cong_viec_units')
        with self.assertRaises(PermissionError): self.reserve(budget,self.aa,'task-a')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaises(PermissionError): budget.claim_task(db,self.aa,'task-a',2,self.policy)

    def test_metadata_du_an_khong_hop_le_khong_tro_thanh_tac_vu_khong_du_an(self):
        budget = self.budget()
        self.task(budget,self.aa,'task-a')
        with self.kho.ket_noi() as db:
            db.execute("UPDATE cong_viec_tasks SET document=json_set(document,'$.project_id',null) WHERE id='task-a'")
        with self.assertRaises(PermissionError): self.reserve(budget,self.aa,'task-a')

    def test_reserve_don_vi_can_luot_chay_ro_rang(self):
        budget = self.budget()
        self.task(budget,self.aa,'task-a')
        for run in (None,True,0,'1'):
            with self.subTest(run=run):
                with self.assertRaises(PermissionError): self.reserve(budget,self.aa,'task-a',run=run)

    def test_scope_moi_khong_cap_quyen_luot_cu_sau_doi_vai_va_cap_lai(self):
        self.policy = {**self.policy,'tasks_per_user':5,'calls_per_user':20}
        budget = self.budget()
        self.task(budget,self.aa,'task-a')
        self.reserve(budget,self.aa,'task-a')
        helper = {'id':'helper-admin','role':'operator'}
        self.kho.tao_agent(helper['id'],'Quản trị thử','operator')
        self.units.set_member(ROOT,{'unit_id':self.a,'identity':helper['id'],'role':'admin'})
        for role in ('member','admin','revoke','admin'):
            self.units.set_member(ROOT,{'unit_id':self.a,'identity':USER['id'],'role':role})
            if role == 'revoke': continue
            fresh = self.units.bind(USER,self.a)
            with self.assertRaises(PermissionError): self.reserve(budget,fresh,'task-a')
            self.assertEqual(budget.status(fresh,self.policy)['calls_used'],1)
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            budget.claim_task(db,fresh,'task-a',2,self.policy)
            scope = self.units.require(fresh,db)
            db.execute("UPDATE cong_viec_tasks SET document=json_set(document,'$.run',2) WHERE id='task-a'")
            db.execute('UPDATE cong_viec_units SET epoch=?,revision=? WHERE task_id=?',(scope.epoch,scope.revision,'task-a'))
        with self.assertRaises(PermissionError): self.reserve(budget,fresh,'task-a',run=1)
        self.reserve(budget,fresh,'task-a',run=2)
        self.assertEqual(budget.status(fresh,self.policy)['calls_used'],2)

    def test_credit_va_reserve_khong_dung_lai_xuyen_don_vi(self):
        budget = self.budget()
        self.task(budget,self.aa,'task-a')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaises(PermissionError):
                budget.claim_task(db,self.bb,'task-a',1,self.policy)
        with self.assertRaises(PermissionError): self.reserve(budget,self.bb,'task-a')
        with self.assertRaises(PermissionError): self.reserve(budget,self.aa,'task-a',run=2)

    def test_json_gia_root_va_scope_registry_khac_bi_chan(self):
        budget = self.budget()
        actors = [USER,ROOT,{**USER,'unit_scope':{'unit_id':self.a}},
                  DonVi(self.kho).bind(USER,self.a),{**self.aa,'role':'quan-tri'}]
        for actor in actors:
            with self.subTest(actor=actor.get('id')):
                with self.assertRaises(PermissionError): budget.status(actor,self.policy)

    def test_luong_cu_dung_kho_co_don_vi_dong_mac_dinh(self):
        budget = NganSachAI(self.kho)
        with self.assertRaises(PermissionError): budget.status(USER,self.policy)
        with self.assertRaises(PermissionError): self.reserve(budget,USER,'legacy')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaises(PermissionError): budget.claim_task(db,USER,'legacy',1,self.policy)

    def test_du_an_chia_se_lay_theo_tac_vu_va_kiem_lai_quyen(self):
        projects = DuAn(self.kho,units=self.units)
        project = projects.create(self.aa,{'name':'Dự án chia sẻ'})['id']
        projects.share(self.aa,{'id':project,'unit_id':self.b,'identity':USER['id'],'role':'editor'})
        budget = self.budget(projects=projects)
        self.task(budget,self.bb,'shared-task',project)
        with self.assertRaises(PermissionError): self.reserve(budget,self.bb,'shared-task',project_id='forged-project')
        with self.assertRaises(PermissionError): self.reserve(self.budget(),self.bb,'shared-task')
        self.reserve(budget,self.bb,'shared-task')
        projects.share(self.aa,{'id':project,'unit_id':self.b,'identity':USER['id'],'role':'revoke'})
        with self.assertRaises((PermissionError,ValueError)): self.reserve(budget,self.bb,'shared-task')

    def test_tac_vu_da_dung_khong_duoc_giu_them_chi_phi(self):
        budget = self.budget()
        self.task(budget,self.aa,'stopped-task')
        with self.kho.ket_noi() as db:
            db.execute("UPDATE cong_viec_tasks SET status='cancelled' WHERE id='stopped-task'")
        with self.assertRaises(PermissionError): self.reserve(budget,self.aa,'stopped-task')

    def test_yeu_cau_dung_da_luu_chan_reservation_ke_tiep(self):
        budget = self.budget()
        self.task(budget,self.aa,'cancel-requested')
        with self.kho.ket_noi() as db:
            db.execute("UPDATE cong_viec_tasks SET document=json_set(document,'$.cancel_requested',json('true')) WHERE id='cancel-requested'")
        with self.assertRaises(PermissionError): self.reserve(budget,self.aa,'cancel-requested')

    def test_quyen_cu_thu_hoi_va_cap_lai_khong_lam_moi_scope_hay_so_cai(self):
        budget = self.budget()
        self.task(budget,self.aa,'task-a')
        self.reserve(budget,self.aa,'task-a')
        helper = {'id':'helper-admin','role':'operator'}
        self.kho.tao_agent(helper['id'],'Quản trị thử','operator')
        self.units.set_member(ROOT,{'unit_id':self.a,'identity':helper['id'],'role':'admin'})
        self.units.set_member(ROOT,{'unit_id':self.a,'identity':USER['id'],'role':'revoke'})
        with self.assertRaises(PermissionError): budget.status(self.aa,self.policy)
        with self.assertRaises(PermissionError): self.reserve(budget,self.aa,'task-a')
        self.units.set_member(ROOT,{'unit_id':self.a,'identity':USER['id'],'role':'member'})
        with self.assertRaises(PermissionError): budget.status(self.aa,self.policy)
        fresh = self.units.bind(USER,self.a)
        self.assertEqual(budget.status(fresh,self.policy)['calls_used'],1)
        with self.assertRaises(LoiMoHinhBDSG): self.task(budget,fresh,'new-task')

    def test_credit_chua_phan_loai_va_owner_khac_khong_duoc_mien_phi(self):
        budget = self.budget()
        with self.kho.ket_noi() as db:
            db.execute('INSERT INTO ai_task_credits VALUES(?,?,?,?)',(USER['id'],'legacy-credit',1,budget.day()))
            db.execute('INSERT INTO ai_task_credits VALUES(?,?,?,?)',('other-owner','foreign-credit',1,budget.day()))
        for identifier in ('legacy-credit','foreign-credit'):
            with self.kho.ket_noi() as db:
                db.execute('BEGIN IMMEDIATE')
                with self.assertRaises(PermissionError): budget.claim_task(db,self.aa,identifier,1,self.policy)
        self.assertEqual(budget.status(self.aa,self.policy)['tasks_used'],0)

    def test_canh_tranh_chi_con_mot_suat_trong_don_vi(self):
        budget = self.budget()
        self.task(budget,self.aa,'task-a')
        self._race(budget,[self.aa]*8,['task-a']*8)
        self.assertEqual(budget.status(self.aa,self.policy)['calls_used'],1)

    def test_canh_tranh_hai_don_vi_chi_con_mot_suat_may_chu(self):
        host_policy = {**DEFAULT_POLICY,'calls_global':1}
        budget = self.budget(host_policy=host_policy)
        host_policy['calls_global'] = 999
        self.task(budget,self.aa,'task-a')
        self.task(budget,self.bb,'task-b')
        self._race(budget,[self.aa,self.bb],['task-a','task-b'])
        statuses = [budget.status(a,self.policy) for a in (self.aa,self.bb)]
        self.assertEqual(sum(s['calls_used'] for s in statuses),1)
        self.assertTrue(all(s['policy']['calls_global']==500 for s in statuses))

    def _race(self,budget,actors,tasks):
        barrier = threading.Barrier(len(actors))
        def reserve(pair):
            barrier.wait(timeout=5)
            try:
                self.reserve(budget,*pair)
                return True
            except LoiMoHinhBDSG:
                return False
        with ThreadPoolExecutor(max_workers=len(actors)) as pool:
            self.assertEqual(sum(pool.map(reserve,zip(actors,tasks))),1)

    def test_lich_su_cu_chi_chan_tran_may_chu_khong_ro_thong_ke(self):
        budget = self.budget(host_policy={**DEFAULT_POLICY,'calls_global':1})
        self.task(budget,self.aa,'task-a')
        with self.kho.ket_noi() as db:
            db.execute('CREATE TABLE model_calls(owner TEXT,created REAL,project_id TEXT,output_reserved INTEGER)')
            db.execute('INSERT INTO model_calls VALUES(?,?,?,?)',('unknown-legacy-owner',self.now,'unknown-project',100))
        status = budget.status(self.aa,self.policy)
        self.assertEqual(status['calls_used'],0)
        self.assertEqual(status['output_tokens_reserved'],0)
        self.assertEqual(status['usd_reserved'],'0')
        with self.assertRaises(LoiMoHinhBDSG): self.reserve(budget,self.aa,'task-a')

    def test_token_chi_phi_cua_cung_actor_tach_theo_don_vi(self):
        self.policy = {**self.policy,'calls_per_user':20,'input_tokens_per_user':10,
                       'output_tokens_per_user':20,'usd_per_user':'0.00003'}
        budget = self.budget()
        self.task(budget,self.aa,'task-a')
        self.task(budget,self.bb,'task-b')
        for actor,identifier in ((self.aa,'task-a'),(self.bb,'task-b')):
            self.reserve(budget,actor,identifier)
            with self.assertRaises(LoiMoHinhBDSG): self.reserve(budget,actor,identifier)
            status = budget.status(actor,self.policy)
            self.assertEqual(status['input_tokens_reserved'],10)
            self.assertEqual(status['output_tokens_reserved'],20)
            self.assertEqual(status['usd_reserved'],'0.00003')

    def test_khoi_dong_lai_sao_luu_phuc_hoi_giu_so_cai_va_nua_dem_viet_nam(self):
        self.now = 86400-25200-1
        budget = self.budget()
        self.task(budget,self.aa,'task-a')
        self.reserve(budget,self.aa,'task-a')
        backup_temp = tempfile.TemporaryDirectory()
        self.addCleanup(backup_temp.cleanup)
        bundle = Path(backup_temp.name)/'bundle'
        restored_path = Path(backup_temp.name)/'restored'
        backup(self.kho.root,bundle)
        restore(bundle,restored_path)
        restored = Kho(restored_path/'data')
        units = DonVi(restored)
        actor = units.bind(USER,self.a)
        restarted = NganSachAI(restored,clock=lambda:self.now,units=units)
        self.assertEqual(restarted.status(actor,self.policy)['calls_used'],1)
        self.assertEqual(restarted.status(actor,self.policy)['tasks_used'],1)
        self.assertEqual(restarted.status(actor,self.policy)['resets_at_unix'],61200)
        self.now += 1
        self.assertEqual(restarted.status(actor,self.policy)['calls_used'],0)
        self.assertEqual(restarted.status(actor,self.policy)['tasks_remaining'],1)
        self.assertEqual(restarted.status(actor,self.policy)['resets_at_unix'],147600)

if __name__ == '__main__': unittest.main()
