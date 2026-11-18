"""Phiên soạn thảo và nguồn ký qua giao diện công khai trên kho thử."""
import tempfile
import unittest
import time
import json
import base64
import os
import threading
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch, Mock
from urllib.parse import urlsplit, parse_qs

from may_chu import UngDung
from chu_ky_office import sign, verify
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

    def abandon_args(self,opened,intent='abandon-1'):
        return {'file_id':self.file['id'],'key':opened['key'],'request_key':intent,
                'acknowledge_unsaved_changes':True,'acknowledge_shared_session':True}

    def test_abandon_before_first_save_fences_late_write_and_retry_keeps_new_session(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        args=self.abandon_args(opened)
        result=self.editor.abandon_sessions(self.a,args)
        self.assertEqual(result['state'],'da-bo-phien')
        self.assertEqual(result['request_key'],'abandon-1')
        self.assertEqual(result['revoked_sessions'],1)
        with patch('soan_thao_office.http.client.HTTPConnection') as engine:
            with self.assertRaises(PermissionError):
                self.editor.save(self.a,{'key':opened['key'],'request_key':'late-first-save'})
        engine.assert_not_called()
        with self.assertRaises(PermissionError):self.source(opened)
        fresh=self.editor.open(self.a,{'id':self.file['id']})
        self.assertNotEqual(opened['key'],fresh['key'])
        restarted=SoanThaoOffice(self.app.office,self.app.origin);restarted.secret=SECRET
        self.assertEqual(restarted.abandon_sessions(self.a,args),result)
        self.assertTrue(self.source(fresh,restarted).startswith(b'PK'))
        self.assertEqual(self.app.office.read(self.a,{'id':self.file['id']})['file']['version'],1)

    def test_abandon_requires_both_explicit_acknowledgements_before_revoking(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        args=self.abandon_args(opened)
        invalid=[{k:v for k,v in args.items() if k!=field} for field in args]
        for field in ('acknowledge_unsaved_changes','acknowledge_shared_session'):
            invalid.extend({**args,field:value} for value in (False,1,'true',None))
        invalid.extend({**args,'request_key':value} for value in (None,'',True,'a'*129))
        invalid.append({**args,'actor':'nguoi-a'})
        with patch('soan_thao_office.http.client.HTTPConnection') as engine:
            for body in invalid:
                with self.subTest(body=body),self.assertRaises(ValueError):
                    self.editor.abandon_sessions(self.a,body)
                self.assertTrue(self.source(opened).startswith(b'PK'))
        engine.assert_not_called()
        self.assertEqual(self.editor.abandon_sessions(self.a,args)['revoked_sessions'],1)

    def test_abandon_own_unknown_save_blocks_signed_late_callback(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        connection=Mock();connection.getresponse.side_effect=TimeoutError('Synthetic timeout')
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            saved=self.editor.save(self.a,{'key':opened['key'],'request_key':'unknown-before-abandon'})
        self.assertEqual(saved['state'],'chua-ro-ket-qua')
        abandoned=self.editor.abandon_sessions(self.a,self.abandon_args(opened))
        self.assertEqual(abandoned['state'],'da-bo-phien')
        with patch.object(self.editor,'_fetch') as fetch:
            with self.assertRaises(PermissionError):self.callback(opened,request=saved['request_id'])
        fetch.assert_not_called()
        self.assertEqual(self.app.office.read(self.a,{'id':self.file['id']})['file']['version'],1)

    def test_abandon_never_cancels_peer_pending_save(self):
        from van_phong import LoiXungDotVanPhong
        self.app.kho.tao_agent('nguoi-c','Nguoi C','operator')
        member={'unit_id':self.units[0],'identity':'nguoi-c'}
        self.app.units.set_member(self.root,{**member,'role':'member'})
        self.app.projects.share(self.a,{'id':self.project,**member,'role':'editor'})
        other=self.app.units.bind({'id':'nguoi-c','role':'operator','name':'Nguoi C'},self.units[0])
        opened=self.editor.open(self.a,{'id':self.file['id']})
        shared=self.editor.open(other,{'id':self.file['id']})
        self.assertEqual(shared['key'],opened['key'])
        connection,_=self.command_connection()
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            saved=self.editor.save(other,{'key':opened['key'],'request_key':'peer-pending'})
        with self.assertRaises(LoiXungDotVanPhong):
            self.editor.abandon_sessions(self.a,self.abandon_args(opened))
        self.assertTrue(self.source(opened).startswith(b'PK'))
        self.assertEqual(self.editor.progress(other,{'key':opened['key'],'request_id':saved['request_id']})['command_state'],'accepted')
        with patch.object(self.editor,'_fetch',return_value=changed_document('Peer save survives')):
            self.assertEqual(self.callback(opened,request=saved['request_id']),{'error':0})
        self.assertEqual(self.app.office.read(self.a,{'id':self.file['id']})['file']['version'],2)

    def test_abandon_during_callback_download_prevents_commit(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        connection,_=self.command_connection()
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            saved=self.editor.save(self.a,{'key':opened['key'],'request_key':'download-in-flight'})
        def fetch_and_abandon(url,key):
            self.editor.abandon_sessions(self.a,self.abandon_args(opened))
            return changed_document('Late download must not commit')
        with patch.object(self.editor,'_fetch',side_effect=fetch_and_abandon):
            with self.assertRaises(PermissionError):self.callback(opened,request=saved['request_id'])
        self.assertEqual(self.app.office.read(self.a,{'id':self.file['id']})['file']['version'],1)

    def test_abandon_is_bound_to_participating_unit_and_file_even_with_write_access(self):
        self.app.projects.share(self.a,{'id':self.project,'unit_id':self.units[1],'identity':'nguoi-a','role':'editor'})
        opened=self.editor.open(self.a,{'id':self.file['id']})
        other_unit=self.editor.open(self.b,{'id':self.file['id']})
        args=self.abandon_args(opened)
        with self.assertRaises(PermissionError):self.editor.abandon_sessions(self.b,args)
        other_file=self.editor.create(self.a,{'name':'khac.docx','project_id':self.project})
        with self.assertRaises(PermissionError):
            self.editor.abandon_sessions(self.a,{**args,'file_id':other_file['id']})
        with self.assertRaises(PermissionError):self.editor.abandon_sessions(self.root,args)
        self.assertTrue(self.source(opened).startswith(b'PK'))
        self.assertTrue(self.source(other_unit).startswith(b'PK'))
        self.editor.abandon_sessions(self.a,args)
        with self.assertRaises(PermissionError):self.source(opened)
        self.assertTrue(self.source(other_unit).startswith(b'PK'))

    def test_abandon_receipt_rejects_changed_payload_and_regranted_authority(self):
        from van_phong import LoiXungDotVanPhong
        opened=self.editor.open(self.a,{'id':self.file['id']})
        args=self.abandon_args(opened)
        self.editor.abandon_sessions(self.a,args)
        fresh=self.editor.open(self.a,{'id':self.file['id']})
        other_file=self.editor.create(self.a,{'name':'bien-nhan-khac.docx','project_id':self.project})
        with self.assertRaises(LoiXungDotVanPhong):
            self.editor.abandon_sessions(self.a,{**args,'file_id':other_file['id']})
        with self.assertRaises(LoiXungDotVanPhong):
            self.editor.abandon_sessions(self.a,{**args,'key':fresh['key']})
        self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'chu-quan','role':'admin'})
        member={'unit_id':self.units[0],'identity':'nguoi-a'}
        self.app.units.set_member(self.root,{**member,'role':'revoke'})
        self.app.units.set_member(self.root,{**member,'role':'admin'})
        actor=self.actor(self.units[0])
        with self.assertRaises(PermissionError):self.editor.abandon_sessions(actor,args)
        with self.assertRaises(PermissionError):self.source(fresh)
        fenced=self.editor.abandon_sessions(actor,{**args,'key':fresh['key'],'request_key':'after-regrant'})
        self.assertEqual(fenced['state'],'da-bo-phien')
        newest=self.editor.open(actor,{'id':self.file['id']})
        self.assertTrue(self.source(newest).startswith(b'PK'))

    def test_abandon_receipt_restore_does_not_revoke_new_issuer_session(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        args=self.abandon_args(opened)
        self.editor.abandon_sessions(self.a,args)
        with tempfile.TemporaryDirectory() as area:
            bundle,target=Path(area)/'bundle',Path(area)/'restored'
            backup(self.app.kho.root,bundle)
            restore(bundle,target)
            restored=UngDung(target/'data','https://office-scope.test',True,unit_preview=True)
            try:
                restored.office_editor.secret=SECRET;restored.office.scanner=Scanner()
                actor=restored.units.bind({'id':'nguoi-a','role':'operator','name':'Nguoi A'},self.units[0])
                fresh=restored.office_editor.open(actor,{'id':self.file['id']})
                with self.assertRaises(PermissionError):restored.office_editor.abandon_sessions(actor,args)
                self.assertTrue(self.source(fresh,restored.office_editor).startswith(b'PK'))
                self.assertEqual(restored.office.read(actor,{'id':self.file['id']})['file']['version'],1)
            finally:
                restored.tasks.close();restored.core.audit.close()

    def test_save_intent_returns_same_commit_without_second_engine_command(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        self.assertTrue(opened['save_intents'])
        args={'key':opened['key'],'request_key':'intent-save-1'}
        connection,payload=self.command_connection()
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            first=self.editor.save(self.a,args)
            with patch.object(self.editor,'_fetch',return_value=changed_document('Intent committed')):
                self.assertEqual(self.callback(opened,request=first['request_id']),{'error':0})
            again=self.editor.save(self.a,args)
            restarted=SoanThaoOffice(self.app.office,self.app.origin);restarted.secret=SECRET
            self.assertEqual(restarted.save(self.a,args),again)
            self.assertEqual(restarted.progress(self.a,args)['command_state'],'committed')
        self.assertEqual(again,{'state':'da-luu','request_id':first['request_id']})
        self.assertEqual(connection.request.call_count,1)
        progress=self.editor.progress(self.a,args)
        self.assertEqual(progress['request_id'],first['request_id'])
        self.assertEqual(progress['command_state'],'committed')
        self.assertEqual(self.app.office.read(self.a,{'id':self.file['id']})['file']['version'],2)

    def test_unknown_intent_survives_restart_without_redispatch(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        args={'key':opened['key'],'request_key':'intent-timeout'}
        connection=Mock();connection.getresponse.side_effect=TimeoutError('Synthetic timeout')
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            first=self.editor.save(self.a,args)
            restarted=SoanThaoOffice(self.app.office,self.app.origin);restarted.secret=SECRET
            self.assertEqual(restarted.save(self.a,args),first)
            progress=restarted.progress(self.a,args)
        self.assertEqual(connection.request.call_count,1)
        self.assertEqual(progress['command_state'],'unknown')
        self.assertEqual(progress['request_id'],first['request_id'])
        self.assertEqual(progress['request_key'],'intent-timeout')

    def test_new_intent_does_not_borrow_pending_or_previous_commit(self):
        from van_phong import LoiXungDotVanPhong
        opened=self.editor.open(self.a,{'id':self.file['id']})
        connection,payload=self.command_connection()
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            first=self.editor.save(self.a,{'key':opened['key'],'request_key':'first'})
            with self.assertRaises(LoiXungDotVanPhong):
                self.editor.save(self.a,{'key':opened['key'],'request_key':'second'})
            self.assertEqual(connection.request.call_count,1)
        with patch.object(self.editor,'_fetch',return_value=changed_document('First only')):
            self.assertEqual(self.callback(opened,request=first['request_id']),{'error':0})
        progress=self.editor.progress(self.a,{'key':opened['key'],'request_key':'second'})
        self.assertEqual(progress['command_state'],'not-started')
        self.assertIsNone(progress['request_id'])
        self.assertEqual(progress['request_key'],'second')

    def test_intent_never_bypasses_scope_or_membership_generation(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        args={'key':opened['key'],'request_key':'scoped-intent'}
        connection,payload=self.command_connection(4)
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            self.editor.save(self.a,args)
            for method in (self.editor.save,self.editor.progress):
                with self.assertRaises((PermissionError,ValueError)):method(self.b,args)
            self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'chu-quan','role':'admin'})
            member={'unit_id':self.units[0],'identity':'nguoi-a'}
            self.app.units.set_member(self.root,{**member,'role':'revoke'})
            self.app.units.set_member(self.root,{**member,'role':'admin'})
            for method in (self.editor.save,self.editor.progress):
                with self.assertRaises((PermissionError,ValueError)):method(self.actor(self.units[0]),args)
        self.assertEqual(connection.request.call_count,1)

    def test_intent_input_and_ambiguous_progress_are_rejected_before_engine(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        with patch('soan_thao_office.http.client.HTTPConnection') as connection:
            for intent in ('',None,True,[],{},'a'*129,'white space','ý-định'):
                for method in (self.editor.save,self.editor.progress):
                    with self.subTest(intent=intent,method=method.__name__),self.assertRaises(ValueError):
                        method(self.a,{'key':opened['key'],'request_key':intent})
            with self.assertRaises(ValueError):
                self.editor.progress(self.a,{'key':opened['key'],'request_key':'valid','request_id':'a'*32})
        connection.assert_not_called()

    def test_shared_key_keeps_each_actors_intent_separate_from_latest_command(self):
        self.app.kho.tao_agent('nguoi-c','Nguoi C','operator')
        member={'unit_id':self.units[0],'identity':'nguoi-c'}
        self.app.units.set_member(self.root,{**member,'role':'member'})
        self.app.projects.share(self.a,{'id':self.project,**member,'role':'editor'})
        other=self.app.units.bind({'id':'nguoi-c','role':'operator','name':'Nguoi C'},self.units[0])
        opened=self.editor.open(self.a,{'id':self.file['id']})
        self.assertEqual(self.editor.open(other,{'id':self.file['id']})['key'],opened['key'])
        args={'key':opened['key'],'request_key':'same-external-intent'}
        connection,payload=self.command_connection()
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            first=self.editor.save(self.a,args)
            with patch.object(self.editor,'_fetch',return_value=changed_document('First actor')):
                self.assertEqual(self.callback(opened,request=first['request_id']),{'error':0})
            self.assertEqual(self.editor.progress(other,args)['command_state'],'not-started')
            second=self.editor.save(other,args)
            self.assertNotEqual(first['request_id'],second['request_id'])
            self.assertEqual(self.editor.save(self.a,args)['request_id'],first['request_id'])
        self.assertEqual(connection.request.call_count,2)
        self.assertEqual(self.editor.progress(self.a,args)['command_state'],'committed')
        self.assertEqual(self.editor.progress(other,args)['command_state'],'accepted')

    def test_same_intent_concurrent_calls_issue_one_command(self):
        import concurrent.futures
        opened=self.editor.open(self.a,{'id':self.file['id']})
        args={'key':opened['key'],'request_key':'simultaneous'}
        started,release=threading.Event(),threading.Event()
        def command(payload):
            started.set()
            if not release.wait(5):raise TimeoutError('Test did not release command')
            return 0
        with patch.object(self.editor,'_command',side_effect=command) as transport:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                first=executor.submit(self.editor.save,self.a,args)
                self.assertTrue(started.wait(3))
                try:second=executor.submit(self.editor.save,self.a,args).result(timeout=3)
                finally:release.set()
                initial=first.result(timeout=3)
            self.assertEqual(transport.call_count,1)
        self.assertEqual(second['request_id'],initial['request_id'])
        self.assertEqual(second['state'],'chua-ro-ket-qua')

    def test_reopen_exposes_only_current_actors_pending_intent(self):
        self.app.kho.tao_agent('nguoi-c','Nguoi C','operator')
        member={'unit_id':self.units[0],'identity':'nguoi-c'}
        self.app.units.set_member(self.root,{**member,'role':'member'})
        self.app.projects.share(self.a,{'id':self.project,**member,'role':'editor'})
        other=self.app.units.bind({'id':'nguoi-c','role':'operator','name':'Nguoi C'},self.units[0])
        opened=self.editor.open(self.a,{'id':self.file['id']})
        connection,payload=self.command_connection()
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            saved=self.editor.save(self.a,{'key':opened['key'],'request_key':'reopen-pending'})
        reopened=self.editor.open(self.a,{'id':self.file['id']})
        self.assertEqual(reopened['pending_save'],{'request_key':'reopen-pending','request_id':saved['request_id']})
        self.assertIsNone(self.editor.open(other,{'id':self.file['id']})['pending_save'])

    def test_configured_engine_port_routes_command_and_snapshot_over_real_loopback_http(self):
        requests=[];raw=changed_document('Tai lieu qua cong engine thu rieng')
        class Engine(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                claims=verify(body['token'],SECRET,'command')
                requests.append(('POST',self.path,claims))
                self.send_response(200);self.end_headers();self.wfile.write(b'{"error":0}')
            def do_GET(self):
                requests.append(('GET',self.path))
                self.send_response(200);self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Engine)
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        with patch.dict(os.environ,{'BDSG_OFFICE_INTERNAL_PORT':str(server.server_port)}):
            editor=SoanThaoOffice(self.app.office,self.app.origin)
        editor.secret=SECRET
        opened=editor.open(self.a,{'id':self.file['id']})
        original=http.client.HTTPConnection
        def connect(host,port,**kwargs):
            self.assertEqual((host,port),('127.0.0.1',server.server_port))
            return original(host,port,**kwargs)
        with patch('soan_thao_office.http.client.HTTPConnection',side_effect=connect):
            saved=editor.save(self.a,{'key':opened['key']})
            self.assertEqual(saved['state'],'dang-luu')
            payload={'key':opened['key'],'status':6,'userdata':saved['request_id'],
                'url':'http://127.0.0.1:'+str(server.server_port)+'/cache/files/'+opened['key']+'/output.docx',
                'exp':time.time()+60}
            wrong={**payload,'url':'http://127.0.0.1:8088/cache/files/'+opened['key']+'/output.docx'}
            with self.assertRaises(ValueError):
                editor.callback({'token':sign(wrong,SECRET)},'')
            self.assertEqual(len(requests),1)
            self.assertEqual(editor.callback({'token':sign(payload,SECRET)},''),{'error':0})
            another=editor.save(self.a,{'key':opened['key']})
            proxied={**payload,'userdata':another['request_id'],
                'url':self.app.origin+'/office-docs/cache/files/'+opened['key']+'/output.docx'}
            self.assertEqual(editor.callback({'token':sign(proxied,SECRET)},''),{'error':0})
        result=self.app.office.read(self.a,{'id':self.file['id']})
        self.assertEqual(result['version'],2)
        self.assertEqual(base64.b64decode(result['content_base64']),raw)
        self.assertEqual([item[0] for item in requests],['POST','GET','POST','GET'])
        self.assertEqual(requests[0][0:2],('POST','/command'))
        self.assertEqual(requests[0][2]['key'],opened['key'])
        self.assertEqual(requests[1],('GET','/cache/files/'+opened['key']+'/output.docx'))
        self.assertEqual(editor.progress(self.a,{'key':opened['key'],
            'request_id':saved['request_id']})['command_state'],'committed')

    def test_invalid_engine_port_stops_initialization_without_default_fallback(self):
        for value in ('','0','65536','-1','8088 ',' 8088','1.0','http://127.0.0.1:8088',
                      '１２３４','8_088','999999999999999999999999999999'):
            with self.subTest(value=value),patch.dict(os.environ,{'BDSG_OFFICE_INTERNAL_PORT':value}):
                with self.assertRaises(ValueError):
                    SoanThaoOffice(self.app.office,self.app.origin)

    def command_connection(self,code=0,during=None):
        connection,response=Mock(),Mock()
        payload={}
        response.status=200;response.read.return_value=json.dumps({'error':code}).encode()
        def posted(method,path,body,headers):
            payload.update(verify(json.loads(body)['token'],SECRET,'command'))
        def answered():
            if during:during(payload)
            return response
        connection.request.side_effect=posted
        connection.getresponse.side_effect=answered
        return connection,payload

    def callback(self,session,status=6,request=None):
        payload={'key':session['key'],'status':status,'users':['nguoi-a'],
                 'url':'https://unused.test/fixture','exp':time.time()+60}
        if request is not None:payload['userdata']=request
        return self.editor.callback({'token':sign(payload,SECRET)},'')

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

    def test_timeout_does_not_resend_after_pending_age_exceeds_120_seconds(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        connection=Mock()
        connection.getresponse.side_effect=TimeoutError('Synthetic command timeout')
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            result=self.editor.save(self.a,{'key':opened['key']})
            self.assertEqual(result['state'],'chua-ro-ket-qua')
            later=time.time()+121
            with patch('soan_thao_office.time.time',return_value=later):
                again=self.editor.save(self.a,{'key':opened['key']})
            self.assertEqual(again,result)
            self.assertEqual(connection.request.call_count,1)
            progress=self.editor.progress(self.a,{'key':opened['key']})
            self.assertTrue(progress['pending'])
            self.assertEqual(progress['command_state'],'unknown')

    def test_accepted_command_requires_callback_receipt_and_no_change_is_separate(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        connection,_=self.command_connection()
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            accepted=self.editor.save(self.a,{'key':opened['key']})
        self.assertEqual(accepted['state'],'dang-luu')
        self.assertEqual(self.app.office.read(self.a,{'id':self.file['id']})['version'],1)
        with patch.object(self.editor,'_fetch',return_value=changed_document('Da commit callback')):
            self.assertEqual(self.callback(opened,request=accepted['request_id']),{'error':0})
            self.assertEqual(self.callback(opened,request=accepted['request_id']),{'error':0})
        self.assertEqual(self.app.office.read(self.a,{'id':self.file['id']})['version'],2)
        progress=self.editor.progress(self.a,{'key':opened['key'],'request_id':accepted['request_id']})
        self.assertFalse(progress['pending'])
        self.assertEqual(progress['command_state'],'committed')
        connection,_=self.command_connection(4)
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            unchanged=self.editor.save(self.a,{'key':opened['key']})
        self.assertEqual(unchanged['state'],'khong-co-thay-doi')
        self.assertEqual(self.editor.progress(self.a,{'key':opened['key']})['command_state'],'unchanged')

    def test_committed_callback_wins_over_late_response_or_timeout(self):
        for callback_status,outcome in ((s,o) for s in (2,6) for o in (0,4,'timeout')):
            with self.subTest(callback_status=callback_status,outcome=outcome):
                opened=self.editor.open(self.a,{'id':self.file['id']})
                def during(payload):
                    self.callback(opened,callback_status,payload['userdata'] if callback_status==6 else None)
                    if outcome=='timeout':raise TimeoutError('Synthetic after commit')
                connection,_=self.command_connection(0 if outcome=='timeout' else outcome,during)
                with (patch('soan_thao_office.http.client.HTTPConnection',return_value=connection),
                      patch.object(self.editor,'_fetch',return_value=changed_document('Ban luu '+str(callback_status)+str(outcome)))):
                    result=self.editor.save(self.a,{'key':opened['key']})
                self.assertEqual(result['state'],'da-luu')
                progress=self.editor.progress(self.a,{'key':opened['key'],'request_id':result['request_id']})
                self.assertEqual(progress['command_state'],'committed')
                self.assertFalse(progress['pending'])

    def test_explicit_abandon_revokes_key_without_claiming_save_or_late_commit(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        connection=Mock();connection.getresponse.side_effect=TimeoutError('Synthetic')
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            result=self.editor.save(self.a,{'key':opened['key']})
        args={'key':opened['key'],'request_id':result['request_id']}
        with self.assertRaises(ValueError):self.editor.reconcile_save(self.a,args)
        self.assertTrue(self.source(opened).startswith(b'PK'))
        args['acknowledge_unsaved_changes']=True
        abandoned=self.editor.reconcile_save(self.a,args)
        self.assertEqual(abandoned['state'],'da-bo-phien')
        self.assertEqual(self.editor.reconcile_save(self.a,args),abandoned)
        with self.assertRaises(PermissionError):self.source(opened)
        with patch.object(self.editor,'_fetch') as fetch:
            with self.assertRaises(PermissionError):self.callback(opened,request=result['request_id'])
            fetch.assert_not_called()
        self.assertEqual(self.app.office.read(self.a,{'id':self.file['id']})['version'],1)
        fresh=self.editor.open(self.a,{'id':self.file['id']})
        self.assertNotEqual(fresh['key'],opened['key'])

    def test_failure_callback_wins_over_late_command_acceptance(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        connection,_=self.command_connection(0,lambda p:self.callback(opened,7,p['userdata']))
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            result=self.editor.save(self.a,{'key':opened['key']})
        self.assertEqual(result['state'],'loi-luu')
        progress=self.editor.progress(self.a,{'key':opened['key'],'request_id':result['request_id']})
        self.assertEqual(progress['command_state'],'failed')
        self.assertTrue(progress['save_error'])
        self.assertFalse(progress['pending'])
        self.assertEqual(self.app.office.read(self.a,{'id':self.file['id']})['version'],1)

    def test_regrant_during_command_response_never_returns_success(self):
        self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'chu-quan','role':'admin'})
        for code in (0,4):
            actor=self.actor(self.units[0])
            opened=self.editor.open(actor,{'id':self.file['id']})
            def during(payload):
                member={'unit_id':self.units[0],'identity':'nguoi-a'}
                self.app.units.set_member(self.root,{**member,'role':'revoke'})
                self.app.units.set_member(self.root,{**member,'role':'admin'})
            connection,_=self.command_connection(code,during)
            with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
                with self.assertRaises(PermissionError):self.editor.save(actor,{'key':opened['key']})
            fresh=self.actor(self.units[0])
            self.assertEqual(self.app.office.read(fresh,{'id':self.file['id']})['version'],1)

    def test_bad_http_json_and_boolean_responses_remain_unknown(self):
        for status,body in ((503,b'{}'),(200,b'not-json'),(200,b'{"error":false}'),(200,b'{"error":3}')):
            opened=self.editor.open(self.a,{'id':self.file['id']})
            connection,_=self.command_connection()
            response=Mock();response.status=status;response.read.return_value=body
            connection.getresponse.side_effect=None;connection.getresponse.return_value=response
            with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
                result=self.editor.save(self.a,{'key':opened['key']})
                self.assertEqual(result['state'],'chua-ro-ket-qua')
                self.assertEqual(self.editor.save(self.a,{'key':opened['key']}),result)
                self.assertEqual(connection.request.call_count,1)
            self.editor.reconcile_save(self.a,{'key':opened['key'],'request_id':result['request_id'],
                                             'acknowledge_unsaved_changes':True})

    def test_command_status_and_abandon_cannot_borrow_another_key_or_root_role(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        connection,_=self.command_connection()
        with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
            result=self.editor.save(self.a,{'key':opened['key']})
        second_file=self.editor.create(self.a,{'name':'tep-khac.docx','project_id':self.project})
        second=self.editor.open(self.a,{'id':second_file['id']})
        args={'key':second['key'],'request_id':result['request_id']}
        with self.assertRaises(PermissionError):self.editor.progress(self.a,args)
        with self.assertRaises(PermissionError):self.editor.reconcile_save(self.a,{**args,'acknowledge_unsaved_changes':True})
        with self.assertRaises(PermissionError):
            self.editor.reconcile_save(self.root,{'key':opened['key'],'request_id':result['request_id'],
                                                'acknowledge_unsaved_changes':True})

    def test_editing_and_terminal_callbacks_set_command_state_without_false_commit(self):
        for status,state,command_state in ((3,'error','failed'),(4,'closed','superseded')):
            opened=self.editor.open(self.a,{'id':self.file['id']})
            connection,_=self.command_connection()
            with patch('soan_thao_office.http.client.HTTPConnection',return_value=connection):
                result=self.editor.save(self.a,{'key':opened['key']})
            self.assertEqual(self.callback(opened,1),{'error':0})
            with self.assertRaises(ValueError):self.callback(opened,5)
            self.assertTrue(self.editor.progress(self.a,{'key':opened['key']})['pending'])
            self.assertEqual(self.callback(opened,status),{'error':0})
            self.assertEqual(self.callback(opened,status),{'error':0})
            progress=self.editor.progress(self.a,{'key':opened['key'],'request_id':result['request_id']})
            self.assertEqual(progress['state'],state)
            self.assertEqual(progress['command_state'],command_state)
            self.assertEqual(progress['save_error'],status==3)
            self.assertFalse(progress['pending'])
            self.assertEqual(self.app.office.read(self.a,{'id':self.file['id']})['version'],1)

    def test_old_pending_command_is_unknown_until_signed_callback(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        request='a'*32
        # Dữ liệu đầu vào từ schema trước command ledger, không dùng DB làm
        # assertion; mọi kết luận bên dưới qua save/progress/callback thật.
        with self.app.kho.ket_noi() as db:
            db.execute('DROP TABLE office_editor_commands')
            db.execute('INSERT INTO office_editor_requests VALUES(?,?,?,?)',(request,opened['key'],'nguoi-a','operator'))
            db.execute('UPDATE office_editors SET pending=?,pending_at=? WHERE key=?',(request,time.time()-180,opened['key']))
        self.editor=SoanThaoOffice(self.app.office,'https://office-scope.test');self.editor.secret=SECRET
        with patch('soan_thao_office.http.client.HTTPConnection') as transport:
            result=self.editor.save(self.a,{'key':opened['key']})
            self.assertEqual(result,{'state':'chua-ro-ket-qua','request_id':request})
            transport.assert_not_called()
        self.assertEqual(self.editor.progress(self.a,{'key':opened['key']})['command_state'],'unknown')
        with patch.object(self.editor,'_fetch',return_value=changed_document('Luu lenh truoc nang cap')):
            self.callback(opened,request=request)
        self.assertEqual(self.editor.progress(self.a,{'key':opened['key'],'request_id':request})['command_state'],'committed')

    def test_late_no_change_reply_does_not_clear_newer_pending_request(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        newer={}
        second_connection,_=self.command_connection()
        def during(payload):
            self.callback(opened,request=payload['userdata'])
            with patch('soan_thao_office.http.client.HTTPConnection',return_value=second_connection):
                newer.update(self.editor.save(self.a,{'key':opened['key']}))
        connection,_=self.command_connection(4,during)
        with (patch('soan_thao_office.http.client.HTTPConnection',return_value=connection),
              patch.object(self.editor,'_fetch',return_value=changed_document('Ban luu truoc lenh moi'))):
            older=self.editor.save(self.a,{'key':opened['key']})
        self.assertEqual(older['state'],'da-luu')
        self.assertNotEqual(older['request_id'],newer['request_id'])
        progress=self.editor.progress(self.a,{'key':opened['key']})
        self.assertTrue(progress['pending'])
        self.assertEqual(progress['pending_request_id'],newer['request_id'])
        self.assertEqual(progress['command_state'],'accepted')

    def test_source_restores_scope_but_cross_unit_session_does_not_reuse_key(self):
        self.app.projects.share(self.a,{'id':self.project,'unit_id':self.units[1],'identity':'nguoi-a','role':'editor'})
        first=self.editor.open(self.a,{'id':self.file['id']})
        self.assertEqual(first['save_protocol'],'request-ledger-v1')
        self.assertTrue(self.source(first).startswith(b'PK'))
        second=self.editor.open(self.b,{'id':self.file['id']})
        self.assertNotEqual(first['key'],second['key'])
        self.assertTrue(self.source(second).startswith(b'PK'))
        with self.assertRaises((PermissionError,ValueError)):
            self.editor.progress(self.b,{'key':first['key']})

    def test_engine_key_restores_cookie_actor_scope_without_trusting_global_role(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        cookie_actor={'id':'nguoi-a','role':'operator','name':'Nguoi A'}
        path='/office-docs/cache/files/'+opened['key']+'_1/output.docx'
        self.assertTrue(self.editor.engine_access(cookie_actor,path))
        self.assertTrue(self.editor.engine_access(cookie_actor,'/office-docs/10.0.0-1/doc/'+opened['key']+'/c/websocket'))
        self.assertFalse(self.editor.engine_access(self.b,path))
        self.assertFalse(self.editor.engine_access(self.root,path))

    def test_engine_data_cache_path_keeps_document_key_and_participant_checks(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        cookie={'id':'nguoi-a','role':'operator'}
        path='/office-docs/cache/files/data/'+opened['key']+'/Editor.bin/Editor.bin'
        self.assertTrue(self.editor.engine_access(cookie,path))
        self.assertTrue(self.editor.engine_access(cookie,path+'?shardkey='+opened['key']+'&expires=1&md5=synthetic'))
        for actor in (None,self.root,self.b):
            self.assertFalse(self.editor.engine_access(actor,path))
        for bad in (path.replace(opened['key'],'bdsg-'+'f'*32),
                    path+'?shardkey=bdsg-'+'f'*32,
                    path.replace('/data/','/data/data/'),
                    path.replace('/data/','/%252e%252e/')):
            self.assertFalse(self.editor.engine_access(cookie,bad))

    def test_engine_static_code_is_common_but_requires_live_web_identity(self):
        cookie_actor={'id':'nguoi-a','role':'operator','name':'Nguoi A'}
        for path in ('/office-docs/web-apps/apps/api/documents/api.js',
                     '/office-docs/10.0.0-1/sdkjs/common/AllFonts.js',
                     '/office-docs/fonts/font.woff','/office-docs/meta/formats'):
            self.assertTrue(self.editor.engine_access(cookie_actor,path),path)
            for other in (None,{}, {'id':'khong-co','role':'operator'},
                          {**cookie_actor,'mcp_delegation':None}):
                self.assertFalse(self.editor.engine_access(other,path),path)
        self.app.kho.thu_hoi_agent('nguoi-a')
        self.assertFalse(self.editor.engine_access(cookie_actor,'/office-docs/sdkjs/app.js'))

    def test_engine_metadata_catalogues_require_live_identity_and_exact_route(self):
        actor={'id':'nguoi-a','role':'operator'}
        for name in ('plugins.json','themes.json'):
            path='/office-docs/10.0.0-3bd8c44c30419ec90e50f480cadc3f8e/'+name
            self.assertTrue(self.editor.engine_access(actor,path))
            self.assertFalse(self.editor.engine_access(None,path))
            self.assertFalse(self.editor.engine_access(actor,path+'/install'))
            self.assertFalse(self.editor.engine_access(actor,path+'?key=bdsg-'+'f'*32))
        self.app.kho.thu_hoi_agent('nguoi-a')
        self.assertFalse(self.editor.engine_access(actor,'/office-docs/themes.json'))

    def test_engine_slide_theme_literal_alias_does_not_open_other_noncanonical_paths(self):
        actor={'id':'nguoi-a','role':'operator'}
        for prefix in ('/office-docs/','/office-docs/10.0.0-3bd8c44c30419ec90e50f480cadc3f8e/'):
            alias=prefix+'sdkjs/slide/themes//themes.js'
            self.assertTrue(self.editor.engine_access(actor,alias))
            self.assertFalse(self.editor.engine_access(None,alias))
            for path in (alias.replace('//themes.js','/%2fthemes.js'),
                         alias.replace('//themes.js','///themes.js'),
                         prefix+'sdkjs//slide/themes/themes.js',
                         prefix+'cache/files//data/bdsg-'+'f'*32+'/Editor.bin',
                         alias+'?key=bdsg-'+'f'*32):
                self.assertFalse(self.editor.engine_access(actor,path))

    def test_engine_unknown_routes_and_path_or_query_key_substitution_are_denied(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        actor={'id':'nguoi-a','role':'operator','name':'Nguoi A'}
        key=opened['key'];other='bdsg-'+'f'*32
        base='/office-docs/cache/files/'+key+'_1/output.docx'
        self.assertTrue(self.editor.engine_access(actor,base+'?shardkey='+key+'&expires=1&md5=synthetic'))
        bad=[None,13,'https://elsewhere.test'+base,base+'#fragment',base+'#',
             '/office-docs/web-apps/../cache/files/'+key+'/output.docx',
             '/office-docs/web-apps/%2e%2e/cache/files/'+key+'/output.docx',
             '/office-docs/web-apps/%252e%252e/cache/files/'+key+'/output.docx',
             '/office-docs//cache/files/'+key+'/output.docx',base+'?docid='+other,
             base+'?shardkey='+other,base+'?key='+key+'&key='+key,
             base+'?%256bey='+other,base+'?WOPISrc=https://unused.test',
             base+'?token=%252e%252e%252f',
             '/office-docs/sdkjs/app.js?x=%252e%252e%252f',
             '/office-docs/sdkjs/app.js?shardkey='+other,
             '/office-docs/document_editor_service_worker.js',
             '/office-docs/10.0.0-1/document_editor_service_worker.js',
             '/office-docs/sdkjs/common/serviceworker/document_editor_service_worker.js',
             '/office-docs/cache/files/'+key+'/'+other+'/output.docx',
             '/office-docs/doc/'+key+'_1/c/websocket',
             '/office-docs/cache/files/not-issued/output.docx',
             '/office-docs/web-apps/..\\cache/secret',
             '/office-docs/web-apps/%0aasset.js']
        bad.extend('/office-docs/'+p for p in ('command','internal/status','info/status','ai-proxy/chat','uploadimage','ConvertService.ashx','wopi/files/x'))
        for path in bad:
            with self.subTest(path=path):self.assertFalse(self.editor.engine_access(actor,path))

    def test_engine_lease_does_not_revive_after_membership_rejoin(self):
        opened=self.editor.open(self.a,{'id':self.file['id']})
        actor={'id':'nguoi-a','role':'operator','name':'Nguoi A'}
        path='/office-docs/doc/'+opened['key']+'/c/websocket'
        self.assertTrue(self.editor.engine_access(actor,path))
        self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'chu-quan','role':'admin'})
        member={'unit_id':self.units[0],'identity':'nguoi-a'}
        self.app.units.set_member(self.root,{**member,'role':'revoke'})
        self.app.units.set_member(self.root,{**member,'role':'admin'})
        self.assertFalse(self.editor.engine_access(actor,path))
        fresh=self.editor.open(self.actor(self.units[0]),{'id':self.file['id']})
        self.assertTrue(self.editor.engine_access(actor,'/office-docs/doc/'+fresh['key']+'/c/websocket'))

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
