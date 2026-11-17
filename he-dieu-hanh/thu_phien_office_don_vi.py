"""Phiên soạn thảo và nguồn ký qua giao diện công khai trên kho thử."""
import tempfile
import unittest
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

from may_chu import UngDung
from chu_ky_office import sign
from thu_office_tich_hop import Scanner, SECRET, changed_document
from sao_luu_he_thong import backup, restore
from soan_thao_office import SoanThaoOffice


class ThuPhienOfficeDonVi(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=UngDung(self.tmp.name,'https://office-scope.test',True,unit_preview=True)
        self.addCleanup(self.close)
        self.root={'id':'chu-quan','role':'quan-tri','name':'Chu'}
        self.app.kho.tao_chu('synthetic-test-password')
        self.app.kho.tao_agent('nguoi-a','Nguoi A','operator')
        self.units=[self.app.units.create(self.root,{'name':'Don vi '+name,'admin':'nguoi-a'})['id'] for name in ('A','B')]
        self.a=self.actor(self.units[0]);self.b=self.actor(self.units[1])
        self.project=self.app.projects.create(self.a,{'name':'Du an Office thu'})['id']
        self.editor=self.app.office_editor
        self.editor.secret=SECRET
        self.app.office.scanner=Scanner()
        self.file=self.editor.create(self.a,{'name':'tep.docx','project_id':self.project})

    def close(self):
        self.app.tasks.close();self.app.core.audit.close();self.tmp.cleanup()

    def actor(self,unit):
        return self.app.units.bind({'id':'nguoi-a','role':'operator','name':'Nguoi A'},unit)

    def source(self,session,editor=None):
        url=session['config']['document']['url']
        return (editor or self.editor).source(parse_qs(urlsplit(url).query),'Bearer '+sign({'operation':'download','url':url,'exp':time.time()+60},SECRET))

    def test_restart_keeps_source_but_restore_does_not_revive_old_session(self):
        first=self.editor.open(self.a,{'id':self.file['id']})
        restarted=UngDung(self.tmp.name,'https://office-scope.test',True,unit_preview=True)
        try:
            restarted.office_editor.secret=SECRET
            self.assertTrue(self.source(first,restarted.office_editor).startswith(b'PK'))
        finally:
            restarted.tasks.close();restarted.core.audit.close()
        with tempfile.TemporaryDirectory() as area:
            bundle,target=Path(area)/'bundle',Path(area)/'restored'
            backup(self.app.kho.root,bundle)
            self.assertFalse((bundle/'data/office-editor-epoch').exists())
            restore(bundle,target)
            restored=UngDung(target/'data','https://office-scope.test',True,unit_preview=True)
            try:
                restored.office_editor.secret=SECRET
                restored.office.scanner=Scanner()
                with self.assertRaises((PermissionError,ValueError)):
                    self.source(first,restored.office_editor)
                actor=restored.units.bind({'id':'nguoi-a','role':'operator','name':'Nguoi A'},self.units[0])
                for method in (restored.office_editor.progress,restored.office_editor.save):
                    with self.assertRaises((PermissionError,ValueError)):
                        method(actor,{'key':first['key']})
                self.assertFalse(restored.office_editor.engine_access(actor,'/office-docs/cache/'+first['key']+'/doc'))
                token=sign({'key':first['key'],'status':2,'users':['nguoi-a'],
                    'url':'https://unused.test/fixture','exp':time.time()+60},SECRET)
                with patch.object(restored.office_editor,'_fetch') as fetch:
                    with self.assertRaises((PermissionError,ValueError)):
                        restored.office_editor.callback({'token':token},'')
                    fetch.assert_not_called()
                fresh=restored.office_editor.open(actor,{'id':self.file['id']})
                self.assertNotEqual(first['key'],fresh['key'])
                self.assertTrue(self.source(fresh,restored.office_editor).startswith(b'PK'))
                self.assertEqual(restored.office.read(actor,{'id':self.file['id']})['version'],1)
            finally:
                restored.tasks.close();restored.core.audit.close()

    def test_damaged_epoch_stops_live_source_and_is_not_overwritten(self):
        first=self.editor.open(self.a,{'id':self.file['id']})
        path=self.app.kho.root/'office-editor-epoch'
        path.write_bytes(b'broken-synthetic-epoch')
        with self.assertRaises((PermissionError,ValueError)):
            self.source(first)
        with self.assertRaises((PermissionError,ValueError)):
            SoanThaoOffice(self.app.office,'https://office-scope.test')
        self.assertEqual(path.read_bytes(),b'broken-synthetic-epoch')

    def test_old_schema_sessions_are_not_adopted_into_new_epoch(self):
        first=self.editor.open(self.a,{'id':self.file['id']})
        # Đây là schema đầu vào của migration R14 trước issuer, không dùng
        # truy vấn DB thay cho assertion hành vi qua giao diện soạn thảo.
        with self.app.kho.ket_noi() as db:
            db.execute('ALTER TABLE office_editor_scopes DROP COLUMN issuer_epoch')
        upgraded=SoanThaoOffice(self.app.office,'https://office-scope.test')
        upgraded.secret=SECRET
        with self.assertRaises((PermissionError,ValueError)):
            self.source(first,upgraded)
        fresh=upgraded.open(self.a,{'id':self.file['id']})
        self.assertNotEqual(first['key'],fresh['key'])
        self.assertTrue(self.source(fresh,upgraded).startswith(b'PK'))

    def test_missing_epoch_does_not_regenerate_on_source_request(self):
        first=self.editor.open(self.a,{'id':self.file['id']})
        path=self.app.kho.root/'office-editor-epoch'
        path.unlink()
        with self.assertRaises(PermissionError):
            self.source(first)
        self.assertFalse(path.exists())
        restarted=SoanThaoOffice(self.app.office,'https://office-scope.test')
        restarted.secret=SECRET
        with self.assertRaises(PermissionError):
            self.source(first,restarted)

    def test_source_restores_scope_but_cross_unit_session_does_not_reuse_key(self):
        self.app.projects.share(self.a,{'id':self.project,'unit_id':self.units[1],'identity':'nguoi-a','role':'editor'})
        first=self.editor.open(self.a,{'id':self.file['id']})
        self.assertTrue(self.source(first).startswith(b'PK'))
        second=self.editor.open(self.b,{'id':self.file['id']})
        self.assertNotEqual(first['key'],second['key'])
        self.assertTrue(self.source(second).startswith(b'PK'))
        with self.assertRaises((PermissionError,ValueError)):
            self.editor.progress(self.b,{'key':first['key']})

    def test_rejoin_does_not_revive_source_and_reopen_rotates_key(self):
        first=self.editor.open(self.a,{'id':self.file['id']})
        self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'chu-quan','role':'admin'})
        member={'unit_id':self.units[0],'identity':'nguoi-a'}
        self.app.units.set_member(self.root,{**member,'role':'revoke'})
        self.app.units.set_member(self.root,{**member,'role':'admin'})
        with self.assertRaises((PermissionError,ValueError)):
            self.source(first)
        fresh=self.actor(self.units[0])
        second=self.editor.open(fresh,{'id':self.file['id']})
        self.assertNotEqual(first['key'],second['key'])
        with self.assertRaises((PermissionError,ValueError)):
            self.source(first)
        self.assertTrue(self.source(second).startswith(b'PK'))

    def test_project_grant_generation_change_during_scan_blocks_open(self):
        self.app.projects.share(self.a,{'id':self.project,'unit_id':self.units[1],'identity':'nguoi-a','role':'editor'})
        office=self.app.office
        owner=self.a;projects=self.app.projects;project=self.project;unit=self.units[1]
        class RegrantScanner(Scanner):
            def scan(self,raw):
                for role in ('viewer','editor'):
                    projects.share(owner,{'id':project,'unit_id':unit,'identity':'nguoi-a','role':role})
                return super().scan(raw)
        office.scanner=RegrantScanner()
        with self.assertRaises((PermissionError,ValueError)):
            self.editor.open(self.b,{'id':self.file['id']})
        office.scanner=Scanner()
        self.assertTrue(self.source(self.editor.open(self.b,{'id':self.file['id']})).startswith(b'PK'))

    def test_signed_callback_saves_and_revocation_during_fetch_prevents_commit(self):
        first=self.editor.open(self.a,{'id':self.file['id']})
        def callback(session):
            return self.editor.callback({'token':sign({'key':session['key'],'status':2,
                'users':['nguoi-a'],'url':'https://unused.test/fixture',
                'operation':'callback','exp':time.time()+60},SECRET)},'')
        with patch.object(self.editor,'_fetch',return_value=changed_document('Ban moi duoc luu')):
            self.assertEqual(callback(first),{'error':0})
        self.assertEqual(self.app.office.read(self.a,{'id':self.file['id']})['version'],2)
        second=self.editor.open(self.a,{'id':self.file['id']})
        self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'chu-quan','role':'admin'})
        def fetch_and_revoke(url,key):
            member={'unit_id':self.units[0],'identity':'nguoi-a'}
            self.app.units.set_member(self.root,{**member,'role':'revoke'})
            self.app.units.set_member(self.root,{**member,'role':'admin'})
            return changed_document('Khong duoc luu sau cap lai quyen')
        with patch.object(self.editor,'_fetch',side_effect=fetch_and_revoke):
            with self.assertRaises((PermissionError,ValueError)):callback(second)
        fresh=self.actor(self.units[0])
        self.assertEqual(self.app.office.read(fresh,{'id':self.file['id']})['version'],2)

    def test_other_participant_membership_change_blocks_whole_old_session_before_fetch(self):
        self.app.kho.tao_agent('nguoi-c','Nguoi C','operator')
        member={'unit_id':self.units[0],'identity':'nguoi-c'}
        self.app.units.set_member(self.root,{**member,'role':'member'})
        self.app.projects.share(self.a,{'id':self.project,**member,'role':'editor'})
        c=self.app.units.bind({'id':'nguoi-c','role':'operator','name':'Nguoi C'},self.units[0])
        first=self.editor.open(self.a,{'id':self.file['id']})
        joined=self.editor.open(c,{'id':self.file['id']})
        self.assertEqual(first['key'],joined['key'])
        self.app.units.set_member(self.root,{**member,'role':'revoke'})
        self.app.units.set_member(self.root,{**member,'role':'member'})
        token=sign({'key':first['key'],'status':2,'users':['nguoi-a'],
                    'url':'https://unused.test/fixture','exp':time.time()+60},SECRET)
        with patch.object(self.editor,'_fetch') as fetch:
            with self.assertRaises((PermissionError,ValueError)):
                self.editor.callback({'token':token},'')
            fetch.assert_not_called()
        fresh=self.editor.open(self.a,{'id':self.file['id']})
        self.assertNotEqual(first['key'],fresh['key'])
        self.assertTrue(self.source(fresh).startswith(b'PK'))


if __name__=='__main__':unittest.main()
