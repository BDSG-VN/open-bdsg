"""Phiên soạn thảo và nguồn ký qua giao diện công khai trên kho thử."""
import tempfile
import unittest
import time
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

from may_chu import UngDung
from chu_ky_office import sign
from thu_office_tich_hop import Scanner, SECRET, changed_document


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

    def source(self,session):
        url=session['config']['document']['url']
        return self.editor.source(parse_qs(urlsplit(url).query),'Bearer '+sign({'operation':'download','url':url,'exp':time.time()+60},SECRET))

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
