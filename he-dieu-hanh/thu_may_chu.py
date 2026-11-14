"""Kiểm ranh giới danh tính bằng HTTP thật với dữ liệu thử tạm thời."""
import http.client
import json
import tempfile
import threading
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


if __name__ == "__main__":
    unittest.main()
