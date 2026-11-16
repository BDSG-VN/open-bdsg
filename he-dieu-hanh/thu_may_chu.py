"""Kiểm ranh giới danh tính bằng HTTP thật với dữ liệu thử tạm thời."""
import http.client
import json
import tempfile
import threading
import time
import unittest
from may_chu import UngDung, tao_may_chu


class ThuCong(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = UngDung(self.tmp.name, "https://thanhhoa.bdsg.vn", True)
        self.app.kho.tao_chu("mat-khau-chi-trong-test")
        self.tokens = {x: self.app.kho.tao_agent(x, x, "operator" if x == "operator-a" else "agent")
                       for x in ("agent-a", "agent-b", "agent-c", "operator-a")}
        self.server = tao_may_chu(self.app, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.app.tasks.close()
        self.app.core.audit.close()
        self.tmp.cleanup()

    def request(self, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        hdr = {"Content-Type": "application/json", **(headers or {})}
        conn.request("GET" if body is None else "POST", path, json.dumps(body) if body is not None else None, hdr)
        response = conn.getresponse()
        raw = response.read()
        result = (response.status, json.loads(raw) if raw else None, dict(response.getheaders()))
        conn.close()
        return result

    def rpc(self, who, name, args=None):
        status, body, _ = self.request("/mcp", {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
            "params": {"name": name, "arguments": args or {}}}, self.mcp_headers(who))
        self.assertEqual(status, 200)
        return body["result"]

    def mcp_headers(self, who):
        return {"Authorization": "Bearer " + self.tokens[who], "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-06-18"}

    def result(self, value):
        self.assertFalse(value.get("isError"), value)
        parsed = json.loads(value["content"][0]["text"])
        return parsed.get("ket_qua", parsed)

    def test_auth_origin_and_public_catalogue(self):
        self.assertEqual(self.request("/api/requests")[0], 401)
        self.assertEqual(self.request("/mcp")[0], 401)
        self.assertEqual(self.request("/api/catalogue", headers={"Origin": "https://evil.test"})[0], 403)
        catalog = self.request("/api/catalogue")[1]
        self.assertEqual(len(catalog["products"]), 38)
        self.assertTrue(all(p["mcp"]["state"] == "chua-cau-hinh" for p in catalog["products"]))

    def test_project_task_snapshot_and_archive_permissions(self):
        args = {"name": "Du an thu Thanh Hoa", "instructions": "Chi doc", "context": "Ngu canh ban dau"}
        project = self.result(self.rpc("operator-a", "du_an.tao", args))
        self.assertTrue(self.rpc("agent-a", "du_an.danh_sach")["isError"])
        task = self.result(self.rpc("operator-a", "cong_viec.tao", {"prompt": "Tong hop ke hoach du an thu", "project_id": project["id"], "template": "de-xuat-giai-phap"}))
        self.result(self.rpc("operator-a", "du_an.cap_nhat", {**args, "id": project["id"], "context": "Ngu canh thay doi"}))
        self.result(self.rpc("operator-a", "du_an.luu_tru", {"id": project["id"]}))
        self.assertTrue(self.rpc("operator-a", "cong_viec.tao", {"prompt": "Khong duoc tao trong luu tru", "project_id": project["id"]})["isError"])
        for _ in range(100):
            result = self.app.tasks.detail({"id":"operator-a","role":"operator"},task["id"])
            if result["status"] == "completed": break
            time.sleep(.02)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["project"]["context"], "Ngu canh ban dau")
        self.assertIn("Ngu canh ban dau", result["artifacts"][0]["content"])
        self.assertNotIn("Ngu canh thay doi", result["artifacts"][0]["content"])
        self.result(self.rpc("operator-a", "du_an.khoi_phuc", {"id":project["id"]}))
        self.assertFalse(self.app.projects.list({"id":"operator-a","role":"operator"})["projects"][0]["archived"])

    def test_large_unicode_project_web_body_and_mcp_limit(self):
        _, _, headers = self.request("/api/login", {"username":"chu-quan","password":"mat-khau-chi-trong-test"}, {"Origin":self.app.origin})
        payload = {"name":"du_an.tao", "arguments":{"name":"Du an Unicode", "instructions":"x"*4000,"context":"x"*12000}}
        # JSON escaping a Vietnamese character remains below the dedicated 64 KiB web limit.
        payload["arguments"]["context"] = "\u1ec7"*8000
        code, body, _ = self.request("/api/tools", payload, {"Origin":self.app.origin,"Cookie":headers["Set-Cookie"].split(";")[0]})
        self.assertEqual(code,200)
        self.assertTrue(body["ok"],body)
        self.assertEqual(self.request("/mcp", {"x":"x"*17000}, self.mcp_headers("agent-a"))[0],400)

    def test_office_web_upload_uses_authenticated_actor_and_existing_body_limit(self):
        import base64
        project = self.result(self.rpc("operator-a", "du_an.tao", {"name": "Office HTTP thu"}))
        _, _, headers = self.request("/api/login", {
            "username": "chu-quan", "password": "mat-khau-chi-trong-test",
        }, {"Origin": self.app.origin})
        hdr = {"Origin": self.app.origin, "Cookie": headers["Set-Cookie"].split(";")[0]}
        raw = b"x" * 32768
        payload = {"name": "van_phong.tao", "arguments": {
            "project_id": project["id"], "name": "limit.txt",
            "content_base64": base64.b64encode(raw).decode(),
        }}
        self.assertEqual(self.request("/api/tools", payload)[0], 403)
        status, body, _ = self.request("/api/tools", payload, hdr)
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"], body)
        file = body["ket_qua"]
        self.assertEqual(file["owner"], "chu-quan")
        read = self.result(self.rpc("operator-a", "van_phong.doc", {"id": file["id"]}))
        self.assertEqual(base64.b64decode(read["content_base64"]), raw)
        self.assertTrue(self.rpc("agent-a", "van_phong.doc", {"id": file["id"]})["isError"])
        payload["arguments"]["actor"] = {"id": "operator-a", "role": "quan-tri"}
        forged = self.request("/api/tools", payload, hdr)[1]
        self.assertTrue(forged["ok"], forged)
        self.assertEqual(forged["ket_qua"]["owner"], "chu-quan")

    def test_office_parts_use_existing_upload_route_without_expanding_tools_body(self):
        import base64
        import hashlib
        project = self.result(self.rpc("operator-a", "du_an.tao", {"name":"Office phan thu"}))
        _, _, headers = self.request("/api/login", {"username":"chu-quan","password":"mat-khau-chi-trong-test"}, {"Origin":self.app.origin})
        hdr = {"Origin":self.app.origin,"Cookie":headers["Set-Cookie"].split(";")[0]}
        raw = b"x" * 600000
        status, result, _ = self.request("/api/tools", {"name":"van_phong.bat_dau_tai","arguments":{
            "project_id":project["id"],"name":"large.txt","total":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"request_key":"a"*32,
        }}, hdr)
        self.assertEqual(status,200)
        self.assertTrue(result["ok"],result)
        upload = result["ket_qua"]
        for offset in (0,524288):
            body={"destination":"office-part","id":upload["id"],"offset":offset,"content_base64":base64.b64encode(raw[offset:offset+524288]).decode()}
            status,result,_=self.request("/api/upload",body,hdr)
            self.assertEqual(status,200)
            self.assertTrue(result["ok"],result)
        status,result,_=self.request("/api/tools",{"name":"van_phong.ket_thuc_tai","arguments":{"id":upload["id"]}},hdr)
        self.assertTrue(result["ok"],result)
        self.assertEqual(self.request("/api/upload",{"destination":"unknown"},hdr)[0],400)
        self.assertEqual(self.request("/api/tools",{"x":"x"*66000},hdr)[0],400)

    def test_web_session_csrf_logout(self):
        payload = {"username": "chu-quan", "password": "mat-khau-chi-trong-test"}
        self.assertEqual(self.request("/api/login", payload)[0], 403)
        status, _, headers = self.request("/api/login", payload, {"Origin": self.app.origin})
        self.assertEqual(status, 200)
        cookie = headers["Set-Cookie"]
        for flag in ("Secure", "HttpOnly", "SameSite=Strict"):
            self.assertIn(flag, cookie)
        hdr = {"Cookie": cookie.split(";")[0], "Origin": self.app.origin}
        self.assertTrue(self.request("/api/me", headers=hdr)[1]["authenticated"])
        self.assertEqual(self.request("/api/logout", {}, hdr)[0], 200)
        self.assertFalse(self.request("/api/me", headers=hdr)[1]["authenticated"])

    def test_agent_message_identity_isolation_persistence(self):
        message = "noi-dung-thu-rieng-tu"
        self.result(self.rpc("agent-a", "agent.gui_tin", {"recipient": "agent-b", "body": message}))
        inbox = self.result(self.rpc("agent-b", "agent.doc_hop_thu"))["messages"]
        self.assertEqual(inbox[0]["sender"], "agent-a")
        self.assertEqual(inbox[0]["body"], message)
        self.assertEqual(self.result(self.rpc("agent-c", "agent.doc_hop_thu", {"peer": "agent-b"}))["messages"], [])
        self.result(self.rpc("agent-b", "agent.gui_tin", {"recipient": "agent-a", "body": "da-nhan"}))
        self.assertEqual(len(self.app.kho.hop_thu("agent-a")), 2)
        from kho import Kho
        self.assertEqual(len(Kho(self.tmp.name).hop_thu("agent-a")), 2)
        self.assertNotIn(message, (self.app.kho.root / "nhat-ky-nhan.jsonl").read_text())
        with self.app.kho.ket_noi() as db:
            hashes = [r[0] for r in db.execute("SELECT token_hash FROM agents")]
        self.assertFalse(any(t in hashes for t in self.tokens.values()))

    def test_role_and_request_ownership(self):
        args = {"title": "Yeu cau thu", "sector": "cong-nghe", "description": "Du lieu thu nghiem tach biet"}
        self.assertTrue(self.rpc("agent-a", "kinh_doanh.tao_yeu_cau", args)["isError"])
        created = self.result(self.rpc("operator-a", "kinh_doanh.tao_yeu_cau", args))
        self.assertEqual(len(self.app.kho.yeu_cau("operator-a")), 1)
        self.assertEqual(self.app.kho.yeu_cau("agent-a"), [])
        with self.assertRaises(ValueError):
            self.app.kho.doi_chang("agent-a", created["id"], "trien-khai")
        self.assertTrue(self.rpc("operator-a", "ket_noi.ghi", {"platform_id": "bdsg_crm", "tool": "x", "arguments": {}})["isError"])

    def test_write_gate_and_token_revocation(self):
        self.app.core.nhan.chinh_sach.cong_ghi.dong()
        self.assertTrue(self.rpc("agent-a", "agent.gui_tin", {"recipient": "agent-b", "body": "thu"})["isError"])
        self.app.kho.thu_hoi_agent("agent-a")
        self.assertEqual(self.request("/mcp", {"jsonrpc": "2.0", "id": 1, "method": "ping"}, self.mcp_headers("agent-a"))[0], 401)

    def test_mcp_initialize_limits(self):
        body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}
        status, response, _ = self.request("/mcp", body, self.mcp_headers("agent-a"))
        self.assertEqual(status, 200)
        self.assertEqual(response["result"]["protocolVersion"], "2025-06-18")
        headers = self.mcp_headers("agent-a")
        headers["Accept"] = "application/json"
        self.assertEqual(self.request("/mcp", body, headers)[0], 406)
        headers["MCP-Protocol-Version"] = "1900-01-01"
        self.assertEqual(self.request("/mcp", body, headers)[0], 400)
        self.assertEqual(self.request("/mcp", {"x": "x" * 17000}, self.mcp_headers("agent-a"))[0], 400)

    def test_failed_password_rate_limit(self):
        for _ in range(8):
            self.assertEqual(self.request("/api/login", {"username": "chu-quan", "password": "sai"}, {"Origin": self.app.origin})[0], 401)
        self.assertEqual(self.request("/api/login", {"username": "chu-quan", "password": "sai"}, {"Origin": self.app.origin})[0], 429)

    def test_task_via_mcp_and_scoped_http(self):
        job = self.result(self.rpc("operator-a", "cong_viec.tao", {"prompt": "Lap de xuat dung CRM tai Thanh Hoa", "module_ids": ["bdsg_crm"], "template": "de-xuat-giai-phap"}))
        task = None
        for _ in range(100):
            task = self.result(self.rpc("operator-a", "cong_viec.chi_tiet", {"id": job["id"]}))
            if task["status"] in ("completed", "failed"):
                break
            time.sleep(.01)
        self.assertEqual(task["status"], "completed")
        self.assertEqual(len(task["artifacts"]), 1)
        self.assertEqual(task["mode"], "quy-trinh")
        self.assertTrue(self.rpc("agent-a", "cong_viec.chi_tiet", {"id": job["id"]})["isError"])
        self.assertEqual(self.request("/api/tasks")[0], 401)

    def test_model_configuration_owner_only_private_and_no_echo(self):
        self.assertEqual(self.request("/api/model-config", {"provider": "openai"}, {"Origin": self.app.origin})[0], 401)
        args = {"provider": "openai", "model": "test-config-only-never-called", "api_key": "test-key-private-never-real-12345"}
        self.assertTrue(self.rpc("operator-a", "cau_hinh.mo_hinh", args)["isError"])
        status, _, headers = self.request("/api/login", {"username": "chu-quan", "password": "mat-khau-chi-trong-test"}, {"Origin": self.app.origin})
        self.assertEqual(status, 200)
        auth = {"Cookie": headers["Set-Cookie"].split(";")[0], "Origin": self.app.origin}
        status, value, _ = self.request("/api/model-config", args, auth)
        self.assertEqual(status, 200)
        self.assertFalse(value["verified"])
        self.assertEqual(value["provider"], "openai")
        self.assertNotIn(args["api_key"], json.dumps(value))
        self.assertNotIn(args["api_key"], json.dumps(self.request("/api/model")[1]))
        self.assertNotIn(args["api_key"], (self.app.kho.root / "nhat-ky-nhan.jsonl").read_text())
        private = self.app.kho.root / "model-private.json"
        self.assertEqual(private.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(private.read_text())["api_key"], args["api_key"])
        from cau_hinh_mo_hinh import CauHinhMoHinh
        self.app.tasks.model = None
        CauHinhMoHinh(self.app.kho, self.app.tasks)
        self.assertEqual(self.app.tasks.model.public_status()["provider"], "openai")
        result=self.app.core.goi({"id":"chu-quan","role":"quan-tri","name":"Chu"},"cau_hinh.tat_mo_hinh",{})
        self.assertTrue(result["ok"])
        self.assertFalse(self.app.tasks.model.configured)
        self.assertNotIn(args["api_key"],private.read_text())
        CauHinhMoHinh(self.app.kho,self.app.tasks)
        self.assertFalse(self.app.tasks.model.configured)

    def test_connector_management_requires_owner_and_redacts_credentials(self):
        args={"platform_id":"bdsg_crm","url":"https://crm.bdsg.vn/mcp","token":"fake-private-token","read_tools":["crm.list"]}
        self.assertTrue(self.rpc("operator-a","cau_hinh.luu_dau_noi",args)["isError"])
        actor={"id":"chu-quan","role":"quan-tri","name":"Chu"}
        result=self.app.core.goi(actor,"cau_hinh.luu_dau_noi",args)
        self.assertTrue(result["ok"])
        self.assertNotIn(args["token"],json.dumps(result))
        self.assertNotIn(args["token"],(self.app.kho.root/"nhat-ky-nhan.jsonl").read_text())
        public = self.request("/api/catalogue")[1]
        self.assertNotIn("crm.list", json.dumps(public))
        self.assertNotIn(args["url"], json.dumps(public))
        self.app.core.nhan.chinh_sach.cong_ghi.dong()
        self.assertFalse(self.app.core.goi(actor,"cau_hinh.ngat_dau_noi",{"platform_id":"bdsg_crm"})["ok"])
        self.assertEqual(len(self.app.core.connections.config),1)


if __name__ == "__main__":
    unittest.main()
