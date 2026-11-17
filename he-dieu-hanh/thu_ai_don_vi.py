"""AI đơn vị qua giao diện công khai, khóa và provider đều giả."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from kho import Kho
from don_vi import DonVi
from ai_don_vi import AITheoDonVi
from mo_hinh_bdsg import LoiMoHinhBDSG
from ngan_sach_ai import DEFAULT_POLICY
from sao_luu_he_thong import backup, restore

ROOT={'id':'chu-quan','role':'quan-tri'}
USER={'id':'synthetic-user','role':'operator'}

def config(key='synthetic-key-unit-a'):
    return {'enabled':True,'default_model':'same-model','models':[{
        'id':'same-model','label':'Mô hình giả','upstream_model':'openai/synthetic',
        'api_key':key,'capabilities':['general'],'skills':[],
        'prices':{'input_per_million':'1','output_per_million':'3'}}],
        'policy':dict(DEFAULT_POLICY)}

class ThuAITheoDonVi(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.kho=Kho(self.tmp.name); self.kho.tao_chu('synthetic-password-not-live')
        self.kho.tao_agent(USER['id'],'Người kiểm',USER['role'])
        self.units=DonVi(self.kho)
        self.ids=[self.units.create(ROOT,{'name':name,'admin':USER['id']})['id'] for name in ('Đơn vị A','Đơn vị B')]
        self.actors=[self.units.bind(USER,u) for u in self.ids]
        self.ai=AITheoDonVi(self.kho,self.units,None,probe=lambda key,aliases:True)

    def test_separate_configs_and_unit_admin_not_root_bypass(self):
        self.ai.save(self.actors[0],config())
        self.ai.save(self.actors[1],config('synthetic-key-unit-b'))
        for actor in self.actors:
            self.assertEqual(self.ai.catalogue(actor)['models'][0]['id'],'same-model')
            self.assertNotIn('synthetic-key',json.dumps(self.ai.admin(actor)))
        self.units.set_member(ROOT,{'unit_id':self.ids[0],'identity':ROOT['id'],'role':'member'})
        with self.assertRaises(PermissionError): self.ai.save(self.units.bind(ROOT,self.ids[0]),config())
        with self.assertRaises(PermissionError): self.ai.admin(ROOT)

    def task(self,actor,identifier,bound):
        with self.kho.ket_noi() as db:
            db.execute('CREATE TABLE IF NOT EXISTS cong_viec_tasks(id TEXT PRIMARY KEY, owner TEXT, created REAL, updated REAL, status TEXT, document TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS cong_viec_units(task_id TEXT PRIMARY KEY,unit_id TEXT,epoch INTEGER,revision INTEGER)')
            db.execute('BEGIN IMMEDIATE')
            bound.admit(db,actor,identifier,1)
            scope=self.units.require(actor,db)
            doc={'id':identifier,'owner':actor['id'],'unit_id':scope.unit_id,'run':1,'project_id':''}
            db.execute('INSERT INTO cong_viec_tasks VALUES(?,?,0,0,?,?)',(identifier,actor['id'],'queued',json.dumps(doc)))
            db.execute('INSERT INTO cong_viec_units VALUES(?,?,?,?)',(identifier,scope.unit_id,scope.epoch,scope.revision))
        return {'task_id':identifier,'run':1,'project_id':''}

    def test_concurrent_save_keeps_both_units_and_keys_independent(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda pair:self.ai.save(*pair),zip(self.actors,[config(),config('synthetic-key-unit-b')])))
        proxy=json.loads(self.ai.proxy_path.read_text(encoding='utf-8'))
        self.assertEqual(len(proxy['model_list']),2)
        self.assertEqual({m['litellm_params']['api_key'] for m in proxy['model_list']},{'synthetic-key-unit-a','synthetic-key-unit-b'})
        self.assertEqual(len({m['model_name'] for m in proxy['model_list']}),2)

    def test_actual_runs_same_actor_two_units_use_separate_alias_and_quota(self):
        calls=[]
        class Fake:
            def __init__(inner,alias): inner.alias=alias
            def run(inner,prompt,context,core,actor,event,cancelled):
                event('model-reserve','Giả',input_bytes=100)
                calls.append(inner.alias)
                return 'Kết quả giả'
        self.ai.factory=lambda alias,key:Fake(alias)
        for i,actor in enumerate(self.actors):
            settings=config('synthetic-key-unit-'+str(i)); settings['policy']['calls_per_user']=1
            self.ai.save(actor,settings)
        for i,actor in enumerate(self.actors):
            bound=self.ai.bind(actor); context=self.task(actor,'task-'+str(i),bound)
            self.assertEqual(bound.run('Kiểm',context,None,actor),'Kết quả giả')
            with self.assertRaises(LoiMoHinhBDSG): bound.run('Kiểm',context,None,actor)
            self.assertEqual(self.ai.quota(actor)['calls_used'],1)
        self.assertEqual(len(calls),2)
        self.assertTrue(calls[0].startswith(self.ids[0]+'-'))
        self.assertTrue(calls[1].startswith(self.ids[1]+'-'))

    def test_rotation_revoke_cancel_mismatch_and_not_ready_deny_before_provider(self):
        for mode in ('rotation','revoke','role','cancel','mismatch','readiness'):
            with self.subTest(mode=mode):
                self.setUp()
                actor=self.actors[0]; self.ai.save(actor,config())
                bound=self.ai.bind(actor); context=self.task(actor,'deny-task',bound)
                calls=[]
                class Fake:
                    def run(inner,prompt,ctx,core,who,event,cancelled):
                        event('model-reserve','Giả',input_bytes=100); calls.append(1)
                self.ai.factory=lambda alias,key:Fake()
                if mode=='rotation': self.ai.save(actor,config('synthetic-rotated-key'))
                if mode in ('revoke','role'):
                    self.units.set_member(ROOT,{'unit_id':self.ids[0],'identity':ROOT['id'],'role':'admin'})
                    self.units.set_member(ROOT,{'unit_id':self.ids[0],'identity':USER['id'],'role':'revoke' if mode=='revoke' else 'member'})
                if mode=='mismatch': self.ai.proxy_path.write_text('{}',encoding='utf-8')
                if mode=='readiness': self.ai.probe=lambda key,aliases:False
                with self.assertRaises((PermissionError,LoiMoHinhBDSG)):
                    bound.run('Kiểm',context,None,actor,cancelled=lambda:mode=='cancel')
                self.assertEqual(calls,[])

    def test_revocation_between_adapter_creation_and_request_is_blocked(self):
        actor=self.actors[0]; self.ai.save(actor,config()); bound=self.ai.bind(actor)
        context=self.task(actor,'guard-task',bound); calls=[]
        class Fake:
            def run(inner,prompt,ctx,core,who,event,cancelled):
                self.ai.save(actor,config('synthetic-rotated-key'))
                event('model-reserve','Giả',input_bytes=100)
                calls.append(1)
        self.ai.factory=lambda alias,key:Fake()
        with self.assertRaises(LoiMoHinhBDSG): bound.run('Kiểm',context,None,actor)
        self.assertEqual(calls,[])
        self.assertEqual(self.ai.quota(actor)['calls_used'],0)

    def test_failed_write_rolls_back_and_blank_key_same_upstream_only(self):
        actor=self.actors[0]; before=self.ai.save(actor,config()); old=self.ai.proxy_path.read_bytes()
        with patch('ai_don_vi.TrungTamAI._write',side_effect=OSError('Đĩa giả')),self.assertRaises(OSError):
            self.ai.save(actor,config('synthetic-rotated-key'))
        self.assertEqual(self.ai.admin(actor)['revision'],before['revision'])
        self.assertEqual(self.ai.proxy_path.read_bytes(),old)
        settings=config(''); self.ai.save(actor,settings)
        settings['models'][0]['upstream_model']='anthropic/synthetic'
        with self.assertRaises(ValueError): self.ai.save(actor,settings)

    def test_partial_publish_failure_restores_previous_or_blocks_admission(self):
        actor=self.actors[0]; self.ai.save(actor,config())
        before=self.ai.admin(actor); previous=self.ai.proxy_path.read_bytes()
        from trung_tam_ai import TrungTamAI
        original=TrungTamAI._write
        writes=[]
        def fail_after_replace(path,data):
            writes.append(1)
            original(path,data)
            if len(writes)==1: raise OSError('Mất kết nối đĩa sau replace')
        with patch('ai_don_vi.TrungTamAI._write',side_effect=fail_after_replace),self.assertRaises(OSError):
            self.ai.save(actor,config('synthetic-rotated-key'))
        self.assertEqual(self.ai.admin(actor),before)
        self.assertEqual(self.ai.proxy_path.read_bytes(),previous)
        def fail_all(path,data):
            path.write_text('{}',encoding='utf-8')
            raise OSError('Đĩa không phục hồi được')
        with patch('ai_don_vi.TrungTamAI._write',side_effect=fail_all),self.assertRaises(OSError):
            self.ai.save(actor,config('synthetic-rotated-key'))
        bound=self.ai.bind(actor)
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaises(LoiMoHinhBDSG): bound.admit(db,actor,'deny-broken',1)

    def test_host_model_limit_does_not_remove_other_units(self):
        actors=list(self.actors)
        for i in range(7):
            identifier=self.units.create(ROOT,{'name':'Đơn vị kiểm '+str(i),'admin':USER['id']})['id']
            actors.append(self.units.bind(USER,identifier))
        settings=config(); settings['models']=[]
        for i in range(16):
            item=copy.deepcopy(config()['models'][0]); item['id']='model-'+str(i)
            settings['models'].append(item)
        settings['default_model']='model-0'
        for actor in actors[:8]: self.ai.save(actor,settings)
        with self.assertRaises(ValueError): self.ai.save(actors[8],settings)
        for actor in actors[:8]: self.assertEqual(len(self.ai.catalogue(actor)['models']),16)
        self.assertEqual(self.ai.catalogue(actors[8])['models'],[])

    def test_owner_repairs_proxy_from_canonical_database_without_rotation(self):
        actor=self.actors[0]; before=self.ai.save(actor,config())
        bound=self.ai.bind(actor); context=self.task(actor,'repair-task',bound)
        expected=self.ai.proxy_path.read_bytes()
        self.ai.proxy_path.write_text('{}',encoding='utf-8')
        with self.assertRaises(LoiMoHinhBDSG): bound.run('Kiểm',context,None,actor)
        with self.assertRaises(LoiMoHinhBDSG): self.ai.save(actor,config())
        with self.assertRaises(PermissionError): self.ai.repair_proxy(actor)
        result=self.ai.repair_proxy(ROOT)
        self.assertEqual(result,{'repaired':True,'units':1,'models':1})
        self.assertEqual(self.ai.admin(actor),before)
        self.assertEqual(self.ai.proxy_path.read_bytes(),expected)
        calls=[]
        class Fake:
            def run(inner,prompt,ctx,core,who,event,cancelled):
                event('model-reserve','Giả',input_bytes=100); calls.append(1)
                return 'Đã phục hồi'
        self.ai.factory=lambda alias,key:Fake()
        restored=self.ai.bind(actor)
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE'); restored.admit(db,actor,'repair-task',1)
        self.assertEqual(restored.run('Kiểm',context,None,actor),'Đã phục hồi')
        self.assertEqual(calls,[1])
        with self.kho.ket_noi() as db: db.execute('DELETE FROM ai_unit_proxy')
        with self.assertRaises(ValueError): self.ai.repair_proxy(ROOT)

    def test_backup_restore_and_missing_proxy_fail_closed(self):
        actor=self.actors[0]; self.ai.save(actor,config())
        with tempfile.TemporaryDirectory() as folder:
            bundle=Path(folder)/'snapshot'; restored=Path(folder)/'restored'
            backup(self.kho.root,bundle); restore(bundle,restored)
            kho=Kho(restored/'data'); units=DonVi(kho)
            loaded=AITheoDonVi(kho,units,None,probe=lambda key,aliases:True)
            scoped=units.bind(USER,self.ids[0])
            self.assertTrue(loaded.bind(scoped).configured)
            self.assertEqual(loaded.admin(scoped),self.ai.admin(actor))
            loaded.proxy_path.unlink()
            with self.assertRaises(ValueError): backup(kho.root,Path(folder)/'broken')
            with kho.ket_noi() as db:
                db.execute('BEGIN IMMEDIATE')
                with self.assertRaises(LoiMoHinhBDSG): loaded.bind(scoped).admit(db,scoped,'absent',1)

    def test_legacy_source_blocks_save_and_startup_does_not_publish(self):
        self.assertFalse(self.ai.proxy_path.exists())
        (self.kho.root/'ai-models-private.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError): self.ai.save(self.actors[0],config())
        self.assertFalse(self.ai.proxy_path.exists())

if __name__=='__main__': unittest.main()
