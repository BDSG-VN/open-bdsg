"""Tác vụ AI theo đơn vị kiểm qua giao diện giao việc, dữ liệu tổng hợp."""
import copy
import json
import threading
import unittest
import thu_cong_viec_don_vi as task_fixture
from ai_don_vi import AITheoDonVi
from mo_hinh_bdsg import LoiMoHinhBDSG
from thu_ai_don_vi import config
from thu_cong_viec import A, OWNER


class ProviderThu:
    def __init__(self, alias, calls, gate=None):
        self.alias,self.calls,self.gate=alias,calls,gate
    def run(self,prompt,context,core,actor,on_event,cancelled):
        if self.gate: self.gate.wait(4)
        on_event('model-reserve','Giữ trước lượt thử',input_bytes=120)
        self.calls.append((self.alias,copy.deepcopy(context)))
        on_event('model-usage','Usage thử',input_tokens=10,output_tokens=20)
        if 'workforce_catalogue' in context:
            skill=context['workforce_catalogue'][0]['id']
            return json.dumps({'summary':'Phân công tổng hợp','assignments':[{'skill_id':skill,
                'mission':'Tổng hợp danh mục công khai','deliverable':'Báo cáo thử','depends_on':[]}]})
        return '# Kết quả tổng hợp '+self.alias


class ThuCongViecAITheoDonVi(unittest.TestCase):
    setUp=task_fixture.ThuCongViecDonVi.setUp
    stop=task_fixture.ThuCongViecDonVi.stop
    create=task_fixture.ThuCongViecDonVi.create
    finished=task_fixture.ThuCongViecDonVi.finished

    def configure(self):
        self.calls=[]
        self.ai=AITheoDonVi(self.kho,self.units,self.tasks.projects,probe=lambda key,aliases:True,
            adapter_factory=lambda alias,key:ProviderThu(alias,self.calls))
        self.tasks.scoped_ai=self.ai
        self.ai.save(self.a1,config('synthetic-unit-one'))
        self.ai.save(self.a2,config('synthetic-unit-two'))

    def test_giao_viec_cung_nguoi_hai_don_vi_khong_tron_mo_hinh_va_ngan_sach(self):
        self.configure()
        self.tasks.model.configuration_error='Cấu hình chung không được đọc'
        one=self.create(self.a1,model_selection='same-model')
        two=self.create(self.a2,model_selection='same-model')
        for actor,identifier,unit in ((self.a1,one,self.one),(self.a2,two,self.two)):
            task=self.finished(actor,identifier)
            self.assertEqual(task['status'],'completed')
            self.assertIn(unit,task['artifacts'][0]['content'])
            self.assertEqual(task['usage']['requests'],1)
            self.assertEqual(self.ai.quota(actor)['calls_used'],1)
            call=next(context for alias,context in self.calls if alias.startswith(unit))
            self.assertEqual((call['task_id'],call['run'],call['project_id'],call['model_selection']),
                             (identifier,1,'','same-model'))
        self.assertNotIn('nen_tang.ket_noi',[call[1] for call in self.core.calls])
        with self.kho.ket_noi() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM model_calls').fetchone()[0],0)

    def test_followup_lay_cau_hinh_moi_va_giu_nguyen_ket_qua_cu(self):
        self.configure()
        identifier=self.create(self.a1)
        first=self.finished(self.a1,identifier)
        self.assertEqual(first['status'],'completed')
        self.ai.save(self.a1,config('synthetic-rotated-one'))
        self.tasks.followup(self.a1,identifier,'Bổ sung từ cấu hình AI đã đổi rõ ràng')
        second=self.finished(self.a1,identifier)
        self.assertEqual(second['status'],'completed')
        self.assertEqual([a['run'] for a in second['artifacts']],[1,2])
        self.assertNotEqual(self.calls[0][0],self.calls[1][0])
        self.assertEqual(self.calls[1][1]['run'],2)
        self.assertEqual(self.ai.quota(self.a1)['tasks_used'],2)

    def test_doi_cau_hinh_khi_xep_hang_khong_goi_provider_cu(self):
        self.configure()
        self.core.block=threading.Event()
        first=self.create(self.a1);second=self.create(self.a2)
        import time
        deadline=time.monotonic()+3
        while len(self.core.calls)<2 and time.monotonic()<deadline: time.sleep(.01)
        queued=self.create(self.a1)
        self.ai.save(self.a1,config('synthetic-rotated-one'))
        self.core.block.set()
        for actor,identifier in ((self.a1,first),(self.a2,second),(self.a1,queued)):
            self.finished(actor,identifier)
        self.assertEqual(self.tasks.detail(self.a1,queued)['status'],'failed')
        self.assertEqual(len(self.calls),1)
        self.assertTrue(self.calls[0][0].startswith(self.two))
        self.assertEqual(self.ai.quota(self.a1)['calls_used'],0)

    def test_thu_hoi_thanh_vien_truoc_provider_khong_giu_ngan_sach(self):
        self.configure()
        self.core.block=threading.Event()
        identifier=self.create(self.a1)
        self.assertTrue(self.core.entered.wait(3))
        self.units.set_member(OWNER,{'unit_id':self.one,'identity':A['id'],'role':'revoke'})
        self.units.set_member(OWNER,{'unit_id':self.one,'identity':A['id'],'role':'admin'})
        renewed=self.units.bind(A,self.one)
        self.core.block.set()
        result=self.finished(renewed,identifier)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(self.calls,[])
        self.assertEqual(self.ai.quota(renewed)['calls_used'],0)
        self.tasks.followup(renewed,identifier,'Tiếp tục sau khi cấp lại tư cách rõ ràng')
        self.assertEqual(self.finished(renewed,identifier)['status'],'completed')
        self.assertEqual(self.ai.quota(renewed)['calls_used'],1)

    def test_rut_chia_se_du_an_chan_provider_sau_khi_da_chup_context(self):
        self.configure()
        project=self.tasks.projects.create(self.a1,{'name':'Dự án chia sẻ thử','context':'Ngữ cảnh tổng hợp'})
        grant={'id':project['id'],'unit_id':self.two,'identity':A['id']}
        self.tasks.projects.share(self.a1,{**grant,'role':'viewer'})
        self.core.block=threading.Event()
        identifier=self.create(self.a2,project_id=project['id'])
        self.assertTrue(self.core.entered.wait(3))
        self.tasks.projects.share(self.a1,{**grant,'role':'revoke'})
        self.core.block.set()
        self.assertEqual(self.finished(self.a2,identifier)['status'],'failed')
        self.assertEqual(self.calls,[])
        self.assertEqual(self.ai.quota(self.a2)['calls_used'],0)

    def test_huy_luot_xep_hang_va_followup_chi_gui_luot_moi(self):
        self.configure()
        self.core.block=threading.Event()
        first=self.create(self.a1);second=self.create(self.a2)
        import time
        deadline=time.monotonic()+3
        while len(self.core.calls)<2 and time.monotonic()<deadline: time.sleep(.01)
        queued=self.create(self.a1)
        self.tasks.cancel(self.a1,queued)
        self.tasks.followup(self.a1,queued,'Chạy lượt mới sau khi hủy lượt xếp hàng')
        self.core.block.set()
        self.finished(self.a1,first);self.finished(self.a2,second)
        result=self.finished(self.a1,queued)
        self.assertEqual(result['status'],'completed')
        self.assertEqual([c['run'] for alias,c in self.calls if c['task_id']==queued],[2])
        self.assertEqual([a['run'] for a in result['artifacts']],[2])

    def test_callback_luot_cu_khong_ghi_vao_luot_followup(self):
        self.configure()
        callbacks=[]
        def factory(alias,key):
            adapter=ProviderThu(alias,self.calls)
            execute=adapter.run
            def run(prompt,context,core,actor,event,cancelled):
                callbacks.append(event)
                return execute(prompt,context,core,actor,event,cancelled)
            adapter.run=run
            return adapter
        self.ai.factory=factory
        identifier=self.create(self.a1)
        self.assertEqual(self.finished(self.a1,identifier)['status'],'completed')
        self.tasks.followup(self.a1,identifier,'Bổ sung lượt mới giữ an toàn callback cũ')
        self.assertEqual(self.finished(self.a1,identifier)['status'],'completed')
        with self.assertRaises(RuntimeError): callbacks[0]('model-usage','Callback đã cũ',input_tokens=999,output_tokens=999)
        task=self.tasks.detail(self.a1,identifier)
        self.assertEqual(task['usage']['requests'],2)
        self.assertEqual(task['usage']['output_tokens'],40)
        self.assertFalse(any(e['message']=='Callback đã cũ' for e in task['events']))

    def test_tu_choi_han_muc_khong_luu_tac_vu_hoac_nang_luot_do_dang(self):
        self.configure()
        limited=config('synthetic-limited-key')
        limited['policy']['tasks_per_user']=1
        self.ai.save(self.a1,limited)
        identifier=self.create(self.a1)
        self.assertEqual(self.finished(self.a1,identifier)['status'],'completed')
        with self.assertRaises(LoiMoHinhBDSG): self.create(self.a1)
        with self.assertRaises(LoiMoHinhBDSG):
            self.tasks.followup(self.a1,identifier,'Lượt thêm phải bị hạn mức từ chối')
        task=self.tasks.detail(self.a1,identifier)
        self.assertEqual(task['run'],1)
        self.assertEqual(task['status'],'completed')
        self.assertEqual(len(self.tasks.list(self.a1)['tasks']),1)
        self.assertEqual(self.ai.quota(self.a1)['tasks_used'],1)
        self.assertEqual(len(self.calls),1)

    def test_chon_mo_hinh_ro_rang_khi_ai_tat_khong_chuyen_qua_quy_trinh(self):
        self.configure()
        identifier=self.create(self.a1,model_selection='same-model')
        self.assertEqual(self.finished(self.a1,identifier)['status'],'completed')
        disabled=config();disabled['enabled']=False
        self.ai.save(self.a1,disabled)
        before=self.ai.quota(self.a1)
        with self.assertRaises(ValueError): self.create(self.a1,model_selection='same-model')
        with self.assertRaises(ValueError):
            self.tasks.followup(self.a1,identifier,'Không chuyển lựa chọn AI rõ ràng thành quy trình')
        self.assertEqual(len(self.tasks.list(self.a1)['tasks']),1)
        task=self.tasks.detail(self.a1,identifier)
        self.assertEqual((task['run'],task['status']),(1,'completed'))
        after=self.ai.quota(self.a1)
        self.assertEqual((after['tasks_used'],after['calls_used']),
                         (before['tasks_used'],before['calls_used']))
        self.assertEqual(len(self.calls),1)

    def test_ai_don_vi_tat_bo_qua_cau_hinh_chung_da_bat(self):
        self.configure()
        disabled=config();disabled['enabled']=False
        self.ai.save(self.a1,disabled)
        self.tasks.model.configured=True
        self.tasks.model.configuration_error='Cấu hình chung sai không được đọc'
        identifier=self.create(self.a1)
        self.assertEqual(self.finished(self.a1,identifier)['status'],'completed')
        self.assertEqual(self.tasks.detail(self.a1,identifier)['mode'],'quy-trinh')
        self.assertEqual(self.calls,[])
        self.assertEqual(self.ai.quota(self.a1)['tasks_used'],0)

    def test_quyen_chua_chuyen_theo_don_vi_van_bi_chan(self):
        self.configure()
        for key,value in (('allow_python',True),('allow_action_drafts',True),
                          ('allow_delegation',True),('allow_module_reads',True),('browser_hosts',['example.com'])):
            with self.subTest(key=key),self.assertRaises(PermissionError): self.create(self.a1,**{key:value})
        self.assertEqual(self.ai.quota(self.a1)['tasks_used'],0)

    def test_ke_hoach_chuyen_mon_tong_hop_cung_luot_va_du_an(self):
        self.configure()
        project=self.tasks.projects.create(self.a1,{'name':'Dự án tổng hợp thử','context':'Ngữ cảnh tổng hợp'})
        identifier=self.create(self.a1,template='nhan-su-chuyen-mon',project_id=project['id'])
        task=self.finished(self.a1,identifier)
        self.assertEqual(task['status'],'completed')
        self.assertEqual(len(self.calls),3)
        for alias,context in self.calls:
            self.assertEqual((context['task_id'],context['run'],context['project_id']),
                             (identifier,1,project['id']))
        self.assertEqual(self.ai.quota(self.a1)['calls_used'],3)
        self.assertEqual(len(task['artifacts']),2)


if __name__=='__main__': unittest.main()
