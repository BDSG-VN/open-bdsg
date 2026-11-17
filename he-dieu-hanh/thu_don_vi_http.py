"""Cổng thử đơn vị: HTTP thật, đăng nhập cookie thật, chỉ dữ liệu tổng hợp."""
import base64
import hashlib
import http.client
import json
import tempfile
import threading
import time
import unittest
from urllib.parse import urlsplit
from unittest.mock import Mock, patch

from chu_ky_office import sign

from may_chu import UngDung, tao_may_chu
from ngan_sach_ai import DEFAULT_POLICY
from trung_tam_ai import MoHinhLiteLLM
from thu_mo_hinh_bdsg import Transport, answer
from thu_dau_noi_don_vi import TransportTongHop


class ThuDonViHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.provider_requests = []
        def factory(alias, key):
            transport = Transport([answer("Ket qua qua adapter thu " + alias)])
            self.provider_requests.append((alias, transport))
            return MoHinhLiteLLM(alias, key, opener=transport)
        self.app = UngDung(self.tmp.name, "https://preview.test", True, unit_preview=True,
            unit_ai_probe=lambda key, aliases: True, unit_ai_factory=factory)
        self.root = {"id": "chu-quan", "name": "Chu", "role": "quan-tri"}
        self.password = "mat-khau-tong-hop-test"
        self.app.kho.tao_chu(self.password)
        for identity in ("nguoi-a", "nguoi-b"):
            self.app.kho.tao_nguoi_dung(self.root, {
                "id": identity, "name": identity, "password": self.password})
        self.bearer = self.app.kho.tao_agent("bearer-test", "Bearer test", "operator")
        self.server = tao_may_chu(self.app, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.close)
        self.cookies = {}
        for identity in ("chu-quan", "nguoi-a", "nguoi-b"):
            status, _, headers = self.request("/api/login", {
                "username": identity, "password": self.password})
            self.assertEqual(status, 200)
            self.cookies[identity] = headers["Set-Cookie"].split(";")[0]
        self.units = []
        for name in ("Cong ty thu A", "Cong ty thu B"):
            status, body, _ = self.request("/api/units", {"name": name, "admin": "nguoi-a"}, "chu-quan")
            self.assertEqual(status, 200, body)
            self.units.append(body["id"])

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.app.tasks.close()
        self.app.core.audit.close()
        self.tmp.cleanup()

    def request(self, path, body=None, who=None, unit=None, headers=None):
        hdr = {"Content-Type": "application/json", "Origin": self.app.origin}
        if who:
            hdr["Cookie"] = self.cookies[who]
        if unit:
            hdr["X-BDSG-Unit"] = unit
        hdr.update(headers or {})
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        conn.request("POST" if body is not None else "GET", path,
                     json.dumps(body) if body is not None else None, hdr)
        response = conn.getresponse()
        raw = response.read()
        value = (raw if response.getheader("Content-Type") == "application/octet-stream" else
                 json.loads(raw) if raw else None)
        result = response.status, value, dict(response.getheaders())
        conn.close()
        return result

    def tool(self, name, args=None, who="nguoi-a", unit=None):
        return self.request("/api/tools", {"name": name, "arguments": args or {}},
                            who, unit or self.units[0])

    def value(self, response):
        status, body, _ = response
        self.assertEqual(status, 200, body)
        self.assertTrue(body["ok"], body)
        return body["ket_qua"]

    def office_session(self):
        from thu_office_tich_hop import Scanner, SECRET
        self.app.office_editor.secret=SECRET
        self.app.office.scanner=Scanner()
        actor=self.app.units.bind({'id':'nguoi-a','role':'operator','name':'Nguoi A'},self.units[0])
        project=self.app.projects.create(actor,{'name':'Du an Engine HTTP'})['id']
        file=self.app.office_editor.create(actor,{'project_id':project,'name':'thu.docx'})
        return actor,file,self.app.office_editor.open(actor,{'id':file['id']})

    def test_office_signed_source_http_without_cookie_checks_lease_and_exact_query(self):
        from thu_office_tich_hop import SECRET
        actor,file,opened=self.office_session()
        url=opened['config']['document']['url']
        parsed=urlsplit(url);path=parsed.path+'?'+parsed.query
        def headers(**claims):
            return {'Origin':'','Authorization':'Bearer '+sign({'payload':{'url':url},
                'operation':'download','exp':time.time()+60,**claims},SECRET)}
        status,raw,hdr=self.request(path,headers=headers())
        self.assertEqual(status,200)
        self.assertTrue(raw.startswith(b'PK'))
        self.assertEqual(hdr['Cache-Control'],'no-store')
        for bad in ({},headers(operation='callback'),headers(exp=time.time()-60),
                    headers(payload={'url':url+'-other'})):
            self.assertEqual(self.request(path,headers=bad)[0],403)
        for suffix in ('&key='+opened['key'],'&cap=other','&unused=1','&cap=','&unused='):
            self.assertEqual(self.request(path+suffix,headers=headers())[0],403)
        self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'chu-quan','role':'admin'})
        self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'nguoi-a','role':'revoke'})
        self.assertEqual(self.request(path,headers=headers())[0],403)
        self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'nguoi-a','role':'admin'})
        self.assertEqual(self.request(path,headers=headers())[0],403)

    def test_office_signed_callback_http_ignores_unsigned_body_and_cookie_authority(self):
        from thu_office_tich_hop import SECRET
        actor,file,opened=self.office_session()
        key=opened['key']
        payload={'key':key,'status':1}
        token=sign({'payload':payload,'operation':'callback','exp':time.time()+60},SECRET)
        status,body,_=self.request('/api/office-callback',{'key':key,'status':4},
            headers={'Origin':'','Authorization':'Bearer '+token})
        self.assertEqual((status,body),(200,{'error':0}))
        self.assertEqual(self.app.office_editor.progress(actor,{'key':key})['state'],'active')
        for headers in ({},{'Authorization':'Bearer '+self.bearer},
                        {'Authorization':'Bearer '+sign({'payload':payload,'operation':'download',
                         'exp':time.time()+60},SECRET)}):
            status,body,_=self.request('/api/office-callback',{'key':key,'status':4},'chu-quan',headers=headers)
            self.assertEqual((status,body),(200,{'error':1}))
        closed=sign({'payload':{'key':key,'status':4},'operation':'callback','exp':time.time()+60},SECRET)
        for _ in range(2):
            self.assertEqual(self.request('/api/office-callback',{'token':closed},headers={'Origin':''})[:2],
                             (200,{'error':0}))
        self.assertEqual(self.app.office_editor.progress(actor,{'key':key})['state'],'closed')
        self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'chu-quan','role':'admin'})
        self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'nguoi-a','role':'revoke'})
        # Biên nhận đã commit chỉ được ack; callback mới vẫn kiểm quyền sống.
        self.assertEqual(self.request('/api/office-callback',{'token':closed})[:2],(200,{'error':0}))
        self.assertEqual(self.request('/api/office-callback',{'token':token})[:2],(200,{'error':1}))

    def test_office_signed_callback_http_commits_once_and_rejects_new_write_after_rejoin(self):
        from thu_office_tich_hop import SECRET, changed_document
        actor,file,opened=self.office_session()
        key=opened['key'];raw=changed_document('Ban luu HTTP tong hop')
        payload={'key':key,'status':2,'users':['nguoi-a'],
                 'url':'http://127.0.0.1:8088/cache/files/'+key+'/output.docx'}
        token=sign({'payload':payload,'operation':'callback','exp':time.time()+60},SECRET)
        original=http.client.HTTPConnection
        engine=Mock();engine.getresponse.return_value.status=200
        engine.getresponse.return_value.read.return_value=raw
        def connect(host,port=None,**kwargs):
            return engine if (host,port)==('127.0.0.1',8088) else original(host,port,**kwargs)
        with patch('soan_thao_office.http.client.HTTPConnection',side_effect=connect):
            for _ in range(2):
                self.assertEqual(self.request('/api/office-callback',{'token':token},
                    headers={'Origin':''})[:2],(200,{'error':0}))
            self.assertEqual(engine.request.call_count,1)
            saved=self.app.office.read(actor,{'id':file['id']})
            self.assertEqual(saved['version'],2)
            self.assertEqual(base64.b64decode(saved['content_base64']),raw)
            fresh=self.app.office_editor.open(actor,{'id':file['id']})
            self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'chu-quan','role':'admin'})
            for role in ('revoke','admin'):
                self.app.units.set_member(self.root,{'unit_id':self.units[0],'identity':'nguoi-a','role':role})
            rejected=sign({'payload':{**payload,'key':fresh['key'],
                'url':'http://127.0.0.1:8088/cache/files/'+fresh['key']+'/output.docx'},
                'operation':'callback','exp':time.time()+60},SECRET)
            self.assertEqual(self.request('/api/office-callback',{'token':rejected})[:2],(200,{'error':1}))
            self.assertEqual(engine.request.call_count,1)
        current=self.app.units.bind({'id':'nguoi-a','role':'operator'},self.units[0])
        self.assertEqual(self.app.office.read(current,{'id':file['id']})['version'],2)

    def test_office_signed_callback_http_rejects_malformed_claims_without_changing_file(self):
        from thu_office_tich_hop import SECRET
        actor,file,opened=self.office_session()
        base={'key':opened['key'],'status':2,'users':['nguoi-a'],
              'url':'http://127.0.0.1:8088/cache/files/'+opened['key']+'/output.docx'}
        invalid=[{**base,'key':[]},{**base,'key':{}},
                 {**base,'users':[{}]},{**base,'users':[1]},
                 {**base,'url':[]},{**base,'url':{}},
                 {**base,'status':True},{**base,'status':2**100},
                 {**base,'status':6,'userdata':[]}]
        for payload in invalid:
            with self.subTest(payload=payload):
                token=sign({'payload':payload,'operation':'callback','exp':time.time()+60},SECRET)
                self.assertEqual(self.request('/api/office-callback',{'token':token})[:2],(200,{'error':1}))
        self.assertEqual(self.app.office_editor.progress(actor,{'key':opened['key']})['state'],'active')
        self.assertEqual(self.app.office.read(actor,{'id':file['id']})['version'],1)

    def test_office_engine_auth_cookie_restores_key_scope_and_rejects_substitution(self):
        actor,file,opened=self.office_session()
        path='/office-docs/doc/'+opened['key']+'/c/websocket'
        headers={'X-BDSG-Engine-Path':path}
        self.assertEqual(self.request('/api/office-engine-auth',who='nguoi-a',headers=headers)[0],200)
        for who in (None,'chu-quan','nguoi-b'):
            self.assertEqual(self.request('/api/office-engine-auth',who=who,headers=headers)[0],403)
        self.assertEqual(self.request('/api/office-engine-auth',who='nguoi-a',unit=self.units[1],headers=headers)[0],403)
        self.assertEqual(self.request('/api/office-engine-auth',who='nguoi-a',
                         headers={**headers,'X-BDSG-Unit-Epoch':'1'})[0],403)
        self.assertEqual(self.request('/api/office-engine-auth',who='nguoi-a',unit=self.units[0],
                         headers={**headers,'X-BDSG-Unit-Epoch':'1','X-BDSG-Unit-Revision':'999'})[0],409)
        self.assertEqual(self.request('/api/office-engine-auth',who='nguoi-a',
                         headers={'X-BDSG-Engine-Path':path+'?shardkey=bdsg-'+'f'*32})[0],403)
        self.assertEqual(self.request('/api/office-engine-auth',who='nguoi-a',
                         headers={'X-BDSG-Engine-Path':'/office-docs/command'})[0],403)
        # Cookie không thay chữ ký nguồn/callback; công cụ tạo/mở vẫn đóng.
        self.assertEqual(self.request('/api/office-source?key='+opened['key'],who='nguoi-a')[0],403)
        self.assertEqual(self.request('/api/office-callback',{'status':2},who='nguoi-a')[:2],(200,{'error':1}))
        self.assertEqual(self.tool('van_phong.mo_soan_thao',{'id':file['id']})[0],403)

    def test_business_requests_cookie_scope_origin_and_legacy_alias(self):
        first, second = self.units
        payload = {'title':'Nhu cau thu nghiem HTTP', 'sector':'bat-dong-san',
                   'description':'Noi dung tong hop khong phai du lieu khach'}
        created = self.value(self.tool('kinh_doanh.tao_yeu_cau', payload))
        rows = self.value(self.tool('kinh_doanh.danh_sach'))['requests']
        self.assertEqual([r['id'] for r in rows], [created['id']])
        self.assertEqual(self.value(self.tool('kinh_doanh.danh_sach', unit=second))['requests'], [])
        change = {'id':created['id'], 'stage':'kinh-doanh'}
        self.assertFalse(self.tool('kinh_doanh.doi_chang', change, unit=second)[1]['ok'])
        self.assertEqual(self.value(self.tool('kinh_doanh.doi_chang', change))['stage'], 'kinh-doanh')
        self.assertEqual(self.request('/api/requests', who='nguoi-a', unit=first)[0], 403)
        body = {'name':'kinh_doanh.tao_yeu_cau', 'arguments':payload}
        self.assertEqual(self.request('/api/tools', body, 'nguoi-a')[0], 403)
        self.assertEqual(self.request('/api/tools', body, 'nguoi-a', first,
                         {'Origin':'https://other.test'})[0], 403)
        self.assertNotEqual(self.request('/api/tools', body, unit=first)[0], 200)
        self.assertEqual(len(self.value(self.tool('kinh_doanh.danh_sach'))['requests']), 1)

    def test_same_cookie_switches_units_without_content_bypass(self):
        first, second = self.units
        project = self.value(self.tool("du_an.tao", {"name": "Du an rieng A"}))
        self.assertEqual(self.value(self.tool("du_an.danh_sach", unit=second))["projects"], [])
        self.assertEqual(self.request("/api/units", who="chu-quan")[1]["units"], [])
        self.assertEqual(self.tool("du_an.danh_sach", who="chu-quan")[0], 403)
        self.assertEqual(self.request("/api/tools", {"name": "du_an.danh_sach"}, "nguoi-a")[0], 403)
        me = self.request("/api/me", who="nguoi-a", unit=first)[1]
        self.assertEqual(set(me["user"]), {"id", "name", "role"})
        self.assertNotIn("unit_scope", json.dumps(me))
        self.assertEqual(self.value(self.tool("du_an.danh_sach"))["projects"][0]["id"], project["id"])

    def test_unit_mailbox_cookie_and_scope_headers(self):
        for unit in self.units:
            admin = self.app.units.bind({'id':'nguoi-a','role':'operator'}, unit)
            self.app.units.set_member(admin, {'unit_id':unit,'identity':'nguoi-b','role':'member'})
        sent = self.value(self.tool('agent.gui_tin', {'recipient':'nguoi-b','body':'Thu HTTP don vi A'}))
        inbox = self.value(self.tool('agent.doc_hop_thu', who='nguoi-b'))['messages']
        self.assertEqual([r['id'] for r in inbox], [sent['id']])
        self.assertEqual(self.value(self.tool('agent.doc_hop_thu', who='nguoi-b', unit=self.units[1])), {'messages':[]})
        self.assertEqual(self.request('/api/tools', {'name':'agent.doc_hop_thu','arguments':{}}, 'nguoi-b')[0], 403)
        self.assertEqual(self.tool('agent.doc_hop_thu', who='chu-quan')[0], 403)
        self.assertEqual({r['id'] for r in self.value(self.tool('agent.danh_sach'))['agents']}, {'nguoi-a','nguoi-b'})
        self.assertEqual(self.request('/api/tools', {'name':'agent.gui_tin','arguments':{
            'recipient':'nguoi-b','body':'Sai origin'}}, 'nguoi-a', self.units[0], {'Origin':'https://other.test'})[0], 403)

    def test_ghi_mcp_qua_http_can_de_xuat_va_admin_duyet_dung_digest(self):
        one = self.units[0]
        self.app.units.set_member(self.root, {'unit_id': one, 'identity': 'nguoi-b', 'role': 'member'})
        transport = TransportTongHop()
        self.app.connectors.transport = transport
        self.value(self.tool('cau_hinh.luu_dau_noi', {'platform_id': 'bdsg_crm',
            'url': 'https://crm.bdsg.vn/mcp', 'token': 'synthetic-http-write-key',
            'read_tools': ['crm.list'], 'write_tools': ['crm.delete'], 'allow_writes': True}))
        self.value(self.tool('cau_hinh.kiem_tra_dau_noi', {'platform_id': 'bdsg_crm'}))
        transport.calls.clear()
        task = self.value(self.tool('cong_viec.tao', {'prompt': 'Tong hop thu nghiem HTTP',
            'template': 'tong-quan', 'module_ids': ['bdsg_crm']}, who='nguoi-b'))
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            detail = self.value(self.request('/api/task?id='+task['id'], who='nguoi-b', unit=one))
            if detail['status'] == 'completed': break
            time.sleep(.01)
        self.assertEqual(detail['status'], 'completed')
        arguments = {'platform_id': 'bdsg_crm', 'tool': 'crm.delete', 'arguments': {'record': 'synthetic-only'}}
        self.assertFalse(self.tool('ket_noi.ghi', arguments)[1]['ok'])
        action = self.value(self.tool('hanh_dong.de_xuat', {
            'task_id': task['id'], 'tool': 'ket_noi.ghi', 'arguments': arguments}, who='nguoi-b'))
        self.assertEqual(transport.calls, [])
        decision = {'id': action['id'], 'digest': action['digest'], 'approve': True}
        self.assertFalse(self.tool('hanh_dong.duyet', decision, who='nguoi-b')[1]['ok'])
        result = self.value(self.tool('hanh_dong.duyet', decision))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(transport.calls), 1)
        self.assertNotIn('synthetic-http-write-key', json.dumps(result))
        self.assertFalse(self.tool('hanh_dong.duyet', decision)[1]['ok'])
        self.assertEqual(len(transport.calls), 1)

    def test_workspace_metadata_and_own_membership_versions(self):
        guest = self.request("/api/me")[1]
        self.assertEqual(guest["workspace"]["mode"], "units")
        self.assertFalse(guest["workspace"]["system_admin"])
        self.assertIsNone(guest["user"])
        root = self.request("/api/me", who="chu-quan")[1]
        self.assertTrue(root["workspace"]["system_admin"])
        me = self.request("/api/me", who="nguoi-a")[1]
        self.assertEqual(set(me["user"]), {"id", "name", "role"})
        self.assertFalse(me["workspace"]["system_admin"])
        self.assertEqual(me["workspace"]["apps"], ["account", "work", "tasks", "projects",
            "office", "ai-settings", "browser", "modules", "staff", "integrations", "studio", "agents", "requests"])
        rows = self.request("/api/units", who="nguoi-a")[1]["units"]
        self.assertEqual({row["id"] for row in rows}, set(self.units))
        for row in rows:
            self.assertEqual(set(row), {"id", "name", "role", "epoch", "revision"})
            self.assertEqual((row["epoch"], row["revision"]), (1, 1))
        self.assertEqual(self.request("/api/units", who="nguoi-b")[1], {"units": []})

    def test_unit_version_headers_reject_stale_and_malformed_requests(self):
        unit = self.units[0]
        path = "/api/tasks"
        valid = {"X-BDSG-Unit-Epoch": "1", "X-BDSG-Unit-Revision": "1"}
        self.assertEqual(self.request(path, who="nguoi-a", unit=unit, headers=valid)[0], 200)
        for headers in ({"X-BDSG-Unit-Epoch": "1"},
                        {"X-BDSG-Unit-Revision": "1"},
                        {**valid, "X-BDSG-Unit-Epoch": "0"},
                        {**valid, "X-BDSG-Unit-Revision": "1.0"},
                        {**valid, "X-BDSG-Unit-Revision": "2"}):
            status, body, _ = self.request(path, who="nguoi-a", unit=unit, headers=headers)
            self.assertEqual((status, body["code"]), (409, "unit_changed"))
        self.app.units.set_member(self.root, {"unit_id": unit, "identity": "nguoi-b", "role": "member"})
        self.app.units.set_member(self.root, {"unit_id": unit, "identity": "nguoi-b", "role": "revoke"})
        self.assertEqual(self.request(path, who="nguoi-b", unit=unit, headers=valid)[0], 403)
        self.app.units.set_member(self.root, {"unit_id": unit, "identity": "nguoi-b", "role": "member"})
        self.assertEqual(self.request(path, who="nguoi-b", unit=unit, headers=valid)[:2],
            (409, {"code": "unit_changed", "error": "Quyền đơn vị đã thay đổi. Hãy chọn lại đơn vị."}))
        row = self.request("/api/units", who="nguoi-b")[1]["units"][0]
        self.assertGreater(row["epoch"], 1)
        self.assertGreater(row["revision"], 1)
        self.assertEqual(self.request(path, who="nguoi-b", unit=unit)[0], 200)
        fresh = {"X-BDSG-Unit-Epoch": str(row["epoch"]), "X-BDSG-Unit-Revision": str(row["revision"])}
        self.assertEqual(self.request(path, who="nguoi-b", unit=unit, headers=fresh)[0], 200)
        self.assertEqual(self.request(path, who="chu-quan", unit=unit, headers=fresh)[0], 403)
        self.app.units.set_member(self.root, {"unit_id": unit, "identity": "nguoi-b", "role": "admin"})
        self.assertEqual(self.request(path, who="nguoi-b", unit=unit, headers=fresh)[0], 409)
        stale_write = self.request("/api/tools", {"name": "du_an.tao", "arguments": {
            "name": "Du an tu bieu mau cu"}}, "nguoi-b", unit, fresh)
        self.assertEqual((stale_write[0], stale_write[1]["code"]), (409, "unit_changed"))

    def test_catalogue_bootstrap_and_scoped_model_modules_are_safe(self):
        product = self.app.catalogue[0]
        self.app.core.connections.config = [{"platform_id": product["id"],
            "url": "https://private-synthetic.bdsg.vn/mcp", "token": "synthetic-private-token",
            "state": "synthetic-private-state", "checked_at": "synthetic-private-check",
            "read_tools": ["private-tool"], "write_tools": []}]
        (self.app.kho.root / "web-status.json").write_text(json.dumps({
            "checked_at": "synthetic-private-web-check", "checks": {
                product["id"]: {"state": "synthetic-private-web-state"}}}), encoding="utf-8")
        status, catalogue, _ = self.request("/api/catalogue")
        self.assertEqual(status, 200)
        self.assertEqual(catalogue["products"][0]["id"], product["id"])
        self.assertNotIn("mcp_endpoint", catalogue)
        self.assertFalse(any(key in catalogue["products"][0] for key in ("web", "mcp", "mcp_status")))
        self.assertNotIn("synthetic-private", json.dumps(catalogue))
        for path in ("/api/model", "/api/modules"):
            self.assertEqual(self.request(path)[0], 401)
            self.assertEqual(self.request(path, who="nguoi-a")[0], 403)
            self.assertEqual(self.request(path, who="chu-quan", unit=self.units[0])[0], 403)
            self.assertEqual(self.request(path, who="nguoi-a", unit=self.units[0],
                headers={"X-BDSG-Unit-Epoch": "1", "X-BDSG-Unit-Revision": "2"})[0], 409)
        model = self.request("/api/model", who="nguoi-a", unit=self.units[0])[1]
        self.assertFalse(model["configured"])
        self.assertEqual(model["provider"], "litellm")
        modules = self.request("/api/modules", who="nguoi-a", unit=self.units[0])[1]
        self.assertEqual(modules, self.value(self.tool("mo_dun.danh_sach")))
        for module in modules["modules"]:
            self.assertEqual(module["kind"], "web")
            self.assertEqual(module["mcp"]["read_tools"], [])
            self.assertEqual(module["mcp"]["write_tools"], [])
        self.assertNotIn("synthetic-private", json.dumps(modules))
        actor = self.app.units.bind({"id": "nguoi-a", "name": "A", "role": "operator"}, self.units[0])
        direct = self.app.core.goi(actor, "mo_dun.danh_sach", {})
        self.assertTrue(direct["ok"], direct)
        self.assertEqual(direct["ket_qua"], modules)
        staff = self.value(self.tool("nhan_su.danh_sach"))
        self.assertTrue(staff["agents"])
        self.assertFalse(staff["grants_permissions"])
        self.assertEqual(self.value(self.tool("nen_tang.ket_noi")), {"connections": []})
        project = self.value(self.tool("du_an.tao", {"name": "Du an kiem trang thai Office"}))
        state = self.value(self.tool("van_phong.trang_thai", {"project_id": project["id"]}))
        self.assertEqual(state["editor_state"], "chua-ho-tro-don-vi")

    def test_default_gateway_refuses_store_with_units(self):
        with self.assertRaises(PermissionError):
            UngDung(self.tmp.name, self.app.origin, True)

    def test_explicit_share_documents_and_office_follow_unit(self):
        first, second = self.units
        project = self.value(self.tool("du_an.tao", {"name": "Du an tai lieu"}))
        content = base64.b64encode(b"tai lieu thu").decode()
        document = self.value(self.request("/api/upload", {
            "project_id": project["id"], "name": "thu.txt", "content_base64": content}, "nguoi-a", first))
        file = self.value(self.tool("van_phong.tao", {
            "project_id": project["id"], "name": "thu.txt", "content_base64": content}))
        self.assertFalse(self.tool("van_phong.doc", {"id": file["id"]}, unit=second)[1]["ok"])
        self.assertEqual(self.request("/api/document?id=" + document["id"], who="nguoi-a", unit=second)[0], 404)
        self.value(self.tool("don_vi.chia_se_du_an", {
            "id": project["id"], "identity": "nguoi-a", "unit_id": second, "role": "viewer"}))
        self.assertEqual(self.request("/api/document?id=" + document["id"], who="nguoi-a", unit=second)[:2], (200, b"tai lieu thu"))
        self.assertEqual(self.value(self.tool("van_phong.doc", {"id": file["id"]}, unit=second))["content_base64"], content)
        self.assertFalse(self.tool("du_an.cap_nhat", {"id": project["id"], "name": "Khong duoc sua"}, unit=second)[1]["ok"])

    def test_csrf_stale_cookie_and_forged_scope_fail_closed(self):
        payload = {"name": "du_an.tao", "arguments": {"name": "Du an bi chan"}}
        for origin in ("", "https://evil.test"):
            self.assertEqual(self.request("/api/tools", payload, "nguoi-a", self.units[0], {"Origin": origin})[0], 403)
        self.assertEqual(self.request("/api/tools", payload, "nguoi-a", self.units[0], {"X-BDSG-Actor": "nguoi-b"})[0], 409)
        self.assertEqual(self.request("/api/tools", payload, "nguoi-b", self.units[0])[0], 403)
        for key in ("actor", "owner", "unit_scope"):
            forged = {**payload, "arguments": {**payload["arguments"], key: {"id": "chu-quan"}}}
            self.assertEqual(self.request("/api/tools", forged, "nguoi-a", self.units[0])[0], 400)
        self.assertEqual(self.tool("du_an.tao", {"name": "Gia mao don vi", "unit_id": self.units[1]})[0], 400)
        self.assertEqual(self.request("/api/tools", payload, unit=self.units[0],
                                     headers={"Authorization": "Bearer " + self.bearer})[0], 401)
        self.assertEqual(self.tool("du_an.tao", {"name": "Qua gioi han", "context": "x" * 70000})[0], 400)
        self.assertEqual(self.request("/api/units/members", {
            "identity": "nguoi-b", "role": "member", "unit_id": self.units[1]}, "nguoi-a", self.units[0])[0], 400)

    def test_office_file_lifecycle_requires_unit_and_explicit_editor_share(self):
        first, second = self.units
        project = self.value(self.tool("du_an.tao", {"name": "Du an vong doi tep"}))
        content = base64.b64encode(b"ban dau").decode()
        file = self.value(self.tool("van_phong.tao", {"project_id": project["id"],
            "name": "thu.txt", "content_base64": content}))
        for action, extra in (("rename", {"name": "moi.txt"}), ("trash", {}),
                              ("untrash", {}), ("restore-version", {"version": 1})):
            result = self.tool("van_phong.cap_nhat", {"id": file["id"],
                "expected_revision": file["revision"], "action": action, **extra}, unit=second)
            self.assertFalse(result[1]["ok"], action)
        self.value(self.tool("don_vi.chia_se_du_an", {"id": project["id"],
            "identity": "nguoi-a", "unit_id": second, "role": "viewer"}))
        self.assertFalse(self.tool("van_phong.cap_nhat", {"id": file["id"],
            "expected_revision": file["revision"], "action": "trash"}, unit=second)[1]["ok"])
        self.value(self.tool("don_vi.chia_se_du_an", {"id": project["id"],
            "identity": "nguoi-a", "unit_id": second, "role": "editor"}))
        for action, extra in (("rename", {"name": "moi.txt"}), ("save", {
                "content_base64": base64.b64encode(b"ban moi").decode()}),
                ("restore-version", {"version": 1}), ("trash", {}), ("untrash", {})):
            file = self.value(self.tool("van_phong.cap_nhat", {"id": file["id"],
                "expected_revision": file["revision"], "action": action, **extra}, unit=second))
            listed = self.value(self.tool("van_phong.danh_sach", {
                "project_id": project["id"], "trashed": action == "trash"}, unit=second))
            self.assertIn(file["id"], [entry["id"] for entry in listed["files"]])
        self.assertEqual(self.value(self.tool("van_phong.doc", {"id": file["id"]}))["content_base64"], content)

    def test_yeu_cau_va_phien_tai_office_tach_theo_don_vi_qua_http(self):
        first, second = self.units
        project = self.value(self.tool("du_an.tao", {"name": "Du an chia se de thu Office"}))
        self.value(self.tool("don_vi.chia_se_du_an", {
            "id": project["id"], "identity": "nguoi-a", "unit_id": second, "role": "editor"}))
        raw = b"noi dung tong hop"
        content = base64.b64encode(raw).decode()
        args = {"project_id": project["id"], "name": "thu.txt",
                "content_base64": content, "request_key": "a" * 32}
        files = [self.value(self.tool("van_phong.tao", args, unit=unit))
                 for unit in (first, second)]
        self.assertNotEqual(files[0]["id"], files[1]["id"])
        for unit, file in zip((first, second), files):
            self.assertEqual(self.value(self.tool("van_phong.tao", args, unit=unit))["id"], file["id"])
        begin = {"project_id": project["id"], "name": "thu.txt", "request_key": "b" * 32,
                 "total": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        upload = self.value(self.tool("van_phong.bat_dau_tai", begin, unit=first))
        self.assertEqual(self.value(self.tool("van_phong.phien_tai", {
            "project_id": project["id"]}, unit=second)), {"uploads": []})
        for tool in ("trang_thai_tai", "ket_thuc_tai", "huy_tai"):
            self.assertFalse(self.tool("van_phong." + tool, {"id": upload["id"]}, unit=second)[1]["ok"])
        part = {"destination": "office-part", "id": upload["id"], "offset": 0, "content_base64": content}
        self.assertFalse(self.request("/api/upload", part, "nguoi-a", second)[1]["ok"])
        self.value(self.request("/api/upload", part, "nguoi-a", first))
        own = self.value(self.tool("van_phong.bat_dau_tai", begin, unit=second))
        self.assertNotEqual(own["id"], upload["id"])
        result = self.value(self.tool("van_phong.ket_thuc_tai", {"id": upload["id"]}, unit=first))
        self.assertTrue(result["completed"])
        self.assertEqual(self.value(self.tool("van_phong.doc", {
            "id": result["file"]["id"]}, unit=second))["content_base64"], content)

    def test_unported_routes_tools_and_mcp_are_denied(self):
        for path in ("/api/requests", "/api/activity", "/api/agents",
                     "/api/connections", "/api/google/callback",
                     "/api/auth/google", "/api/office-source", "/api/office-engine-auth", "/mcp"):
            self.assertEqual(self.request(path, who="chu-quan", unit=self.units[0])[0], 401 if path == '/mcp' else 403, path)
        for path in ("/mcp", "/api/google/start", "/api/model-config", "/api/customer-support"):
            self.assertEqual(self.request(path, {}, "chu-quan", self.units[0])[0], 401 if path == '/mcp' else 403, path)
        self.assertEqual(self.request("/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                     unit=self.units[0], headers={"Authorization": "Bearer " + self.bearer})[0], 401)
        for tool in ("runtime.python", "mo_hinh.trang_thai",
                     "van_phong.google_nhap", "van_phong.tao_office", "van_phong.mo_soan_thao",
                     "van_phong.luu_soan_thao", "cau_hinh.tat_mo_hinh", "nguoi_dung.tao", "nhat_ky.danh_sach"):
            self.assertEqual(self.tool(tool)[0], 403, tool)

    def test_kernel_cung_chan_cong_cu_toan_cong_chua_phan_don_vi(self):
        self.app.units.set_member(self.root, {"unit_id": self.units[0],
            "identity": self.root["id"], "role": "member"})
        for actor in (self.root, {"id": "nguoi-a", "name": "nguoi-a", "role": "operator"}):
            scoped = self.app.units.bind(actor, self.units[0])
            for name in ("cau_hinh.mo_hinh", "cau_hinh.tat_mo_hinh",
                         "ket_noi.ghi", "nhat_ky.danh_sach"):
                result = self.app.core.goi(scoped, name, {})
                self.assertFalse(result["ok"], (actor["id"], name, result))
            catalogue = self.app.core.goi(scoped, "nen_tang.danh_sach", {})
            self.assertTrue(catalogue["ok"], catalogue)

    def test_membership_control_and_revocation_rechecked(self):
        unit = self.units[0]
        self.value(self.tool("du_an.tao", {"name": "Du an cho thanh vien"}))
        self.assertEqual(self.request("/api/units/members", {"identity": "nguoi-b", "role": "member"}, "nguoi-a", unit)[0], 200)
        self.assertEqual(self.value(self.tool("du_an.danh_sach", who="nguoi-b"))["projects"], [])
        denied = self.request("/api/units/members", who="nguoi-b", unit=unit)
        self.assertEqual(denied[0], 403)
        self.assertNotIn("code", denied[1], "Từ chối quản trị không làm mất membership")
        self.assertEqual(self.request("/api/units/members", {"identity": "nguoi-b", "role": "revoke"}, "chu-quan", unit)[0], 200)
        revoked = self.tool("du_an.danh_sach", who="nguoi-b")
        self.assertEqual(revoked[0], 403)
        self.assertEqual(revoked[1].get("code"), "unit_changed", "Cửa sổ đang mở phải nhận biết phạm vi bị thu hồi")

    def test_dau_noi_don_vi_qua_nhan_http_khong_dung_quyen_hoac_token_legacy(self):
        platform = self.app.catalogue[0]["id"]
        transport = TransportTongHop()
        self.app.connectors.transport = transport
        self.app.core.connections.config = [{"platform_id": platform,
            "url": "https://legacy.bdsg.vn/mcp", "token": "synthetic-legacy-secret",
            "read_tools": ["legacy.read"], "roles": ["quan-tri"]}]
        config = {"platform_id": platform, "url": "https://crm-a.bdsg.vn/mcp",
            "token": "synthetic-private-token-a", "read_tools": ["crm.list"], "read_roles": ["admin", "member"]}
        saved = self.value(self.tool("cau_hinh.luu_dau_noi", config))
        self.assertTrue(saved["has_token"])
        self.assertNotIn(config["token"], json.dumps(saved))
        self.assertEqual(self.value(self.tool("cau_hinh.dau_noi", unit=self.units[1])), {"connections": []})
        self.assertEqual(self.value(self.tool("cau_hinh.kiem_tra_dau_noi", {"platform_id": platform}))["state"], "da-xac-minh")
        self.app.units.set_member(self.root, {"unit_id": self.units[0], "identity": "nguoi-b", "role": "member"})
        result = self.value(self.tool("ket_noi.doc", {"platform_id": platform, "tool": "crm.list", "arguments": {}}, who="nguoi-b"))
        self.assertIn("crm-a.bdsg.vn", result["content"][0]["text"])
        self.assertFalse(self.tool("cau_hinh.dau_noi", who="nguoi-b")[1]["ok"])
        summary = self.value(self.tool("nen_tang.ket_noi", who="nguoi-b"))
        self.assertNotIn("url", summary["connections"][0])
        self.assertNotIn("synthetic-legacy-secret", json.dumps(summary))
        modules = self.value(self.tool("mo_dun.danh_sach", who="nguoi-b"))["modules"]
        selected = next(module for module in modules if module["id"] == platform)
        self.assertEqual(selected["mcp"]["read_tools"], ["crm.list"])
        self.assertEqual([entry[1] for entry in transport.calls], [config["token"], config["token"]])
        self.assertFalse(self.tool("ket_noi.doc", {"platform_id": platform, "tool": "legacy.read", "arguments": {}})[1]["ok"])

    def test_cau_hinh_ai_qua_http_chi_thuoc_don_vi_va_khong_tra_khoa(self):
        first, second = self.units
        config = {"enabled": True, "default_model": "thu-model", "models": [{
            "id": "thu-model", "label": "Mo hinh rieng don vi A",
            "upstream_model": "openai/synthetic-test-model", "api_key": "synthetic-key-only-test",
            "capabilities": ["general"], "skills": [],
            "prices": {"input_per_million": "1", "output_per_million": "1"}}],
            "policy": dict(DEFAULT_POLICY)}
        saved = self.value(self.tool("mo_hinh.luu", config, unit=first))
        self.assertEqual(saved["default_model"], "thu-model")
        self.assertTrue(self.request("/api/model", who="nguoi-a", unit=first)[1]["configured"])
        self.assertFalse(self.request("/api/model", who="nguoi-a", unit=second)[1]["configured"])
        self.assertNotIn("synthetic-key-only-test", json.dumps(saved))
        self.assertNotIn("api_key", saved["models"][0])
        self.assertEqual(self.value(self.tool("mo_hinh.danh_sach", unit=second))["models"], [])
        self.app.units.set_member(self.root, {"unit_id": first,
            "identity": self.root["id"], "role": "member"})
        self.assertFalse(self.tool("mo_hinh.luu", config, who="chu-quan", unit=first)[1]["ok"])
        self.assertFalse(self.tool("mo_hinh.cau_hinh", who="chu-quan", unit=first)[1]["ok"])
        self.assertEqual(self.request("/api/tools", {"name": "mo_hinh.danh_sach"}, "nguoi-a")[0], 403)

    def test_ai_hai_don_vi_qua_http_chay_adapter_va_tinh_han_muc_rieng(self):
        created = []
        for unit, model_id in zip(self.units, ("mo-hinh-a", "mo-hinh-b")):
            self.value(self.tool("mo_hinh.luu", {
                "enabled": True, "default_model": model_id, "models": [{
                    "id": model_id, "label": model_id, "upstream_model": "openai/synthetic-test-model",
                    "api_key": "synthetic-key-only-test", "capabilities": ["general"], "skills": [],
                    "prices": {"input_per_million": "1", "output_per_million": "1"}}],
                "policy": dict(DEFAULT_POLICY)}, unit=unit))
            created.append(self.value(self.tool("cong_viec.tao", {
                "prompt": "Phan tich yeu cau kinh doanh tong hop cho don vi",
                "template": "de-xuat-giai-phap", "model_selection": model_id}, unit=unit)))
        for index, (unit, task) in enumerate(zip(self.units, created)):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                result = self.value(self.request("/api/task?id=" + task["id"], who="nguoi-a", unit=unit))
                if result["status"] in ("completed", "failed"):
                    break
                time.sleep(.01)
            self.assertEqual(result["status"], "completed", result)
            self.assertEqual(result["unit_id"], unit)
            self.assertEqual(result["mode"], "mo-hinh-api")
            self.assertIn("mo-hinh-" + ("a" if index == 0 else "b"), result["artifacts"][0]["content"])
            self.assertNotIn("synthetic-key-only-test", json.dumps(result))
            quota = self.value(self.tool("mo_hinh.han_muc", unit=unit))
            self.assertEqual(quota["calls_used"], 1)
            self.assertEqual(quota["tasks_used"], 1)
        self.assertEqual(len(self.provider_requests), 2)
        for alias, transport in self.provider_requests:
            self.assertEqual(len(transport.requests), 1)
            self.assertEqual(json.loads(transport.requests[0][0].data)["model"], alias)

    def test_tac_vu_quy_trinh_qua_kernel_http_giu_don_vi(self):
        one,two=self.units
        created=self.value(self.tool('cong_viec.tao',{'prompt':'Đề xuất mô đun kinh doanh từ danh mục công khai',
                                                    'template':'de-xuat-giai-phap'}))
        identifier=created['id']
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            task=self.value(self.request('/api/task?id='+identifier,who='nguoi-a',unit=one))
            if task['status'] in ('completed','failed'): break
            time.sleep(.01)
        self.assertEqual(task['status'],'completed')
        self.assertEqual(task['unit_id'],one)
        self.assertNotIn('unit_scope',json.dumps(task))
        self.assertEqual(self.value(self.request('/api/tasks',who='nguoi-a',unit=two)),{'tasks':[]})
        self.assertFalse(self.request('/api/task?id='+identifier,who='nguoi-a',unit=two)[1]['ok'])
        self.assertEqual(self.request('/api/tasks',who='nguoi-a')[0],403)
        denied=self.tool('cong_viec.tao',{'prompt':'Không cho dùng runtime ở giai đoạn này',
                                         'template':'de-xuat-giai-phap','allow_python':True})
        self.assertEqual(denied[0],200)
        self.assertFalse(denied[1]['ok'])


if __name__ == "__main__":
    unittest.main()
