"""Kiểm cấu hình riêng, ranh giới quyền và phiên MCP với transport giả lập."""
import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cau_hinh_ket_noi import CauHinhKetNoi
from dieu_phoi import CongMCP
from kho import Kho

OWNER = {"id": "chu-quan", "role": "quan-tri"}
OTHER = {"id": "operator-a", "role": "operator"}
CATALOGUE = [{"id": "crm", "name": "CRM"}]
CONFIG = {"platform_id": "crm", "url": "https://crm.bdsg.vn/mcp", "token": "test-token-private", "read_tools": ["crm.list"]}


class Response:
    def __init__(self, payload, status=200, headers=None):
        self.payload = json.dumps(payload).encode() if payload is not None else b""
        self.status, self.headers = status, headers or {"Content-Type": "application/json"}
    def read(self, size):
        return self.payload[:size]
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass


class Transport:
    def __init__(self):
        self.calls = []
    def open(self, req, timeout):
        self.calls.append(req)
        if req.get_method() == "DELETE":
            return Response(None, 204)
        data = json.loads(req.data)
        if data["method"] == "notifications/initialized":
            return Response(None, 202)
        result = {"protocolVersion": "2025-06-18"} if data["method"] == "initialize" else {"tools": [{"name": "crm.list"}]}
        return Response({"jsonrpc": "2.0", "id": data["id"], "result": result}, headers={"Content-Type": "application/json", "Mcp-Session-Id": "test-session"})


class ThuKetNoi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.kho = Kho(self.tmp.name)
        self.client = CongMCP(None, CATALOGUE)
        self.settings = CauHinhKetNoi(self.kho, self.client, CATALOGUE)

    def test_save_private_without_connecting_and_reload(self):
        with patch("dieu_phoi.socket.getaddrinfo", side_effect=AssertionError("save must not connect")):
            public = self.settings.save(OWNER, CONFIG)
        self.assertNotIn(CONFIG["token"], json.dumps(public))
        self.assertNotIn(CONFIG["token"], json.dumps(self.settings.list(OWNER)))
        self.assertNotIn(CONFIG["token"], json.dumps(self.client.tom_tat()))
        self.assertEqual(self.settings.path.stat().st_mode & 0o777, 0o600)
        fresh = CongMCP(None, CATALOGUE)
        reloaded = CauHinhKetNoi(self.kho, fresh, CATALOGUE)
        self.assertEqual(reloaded.list(OWNER)["connections"][0]["state"], "da-khai-bao")
        self.assertEqual(fresh.config[0]["token"], CONFIG["token"])

    def test_permissions_and_validation(self):
        for operation in [lambda:self.settings.list(OTHER),lambda:self.settings.save(OTHER, CONFIG),lambda:self.settings.probe(OTHER,"crm"),lambda:self.settings.disconnect(OTHER,"crm")]:
            with self.assertRaises(PermissionError): operation()
        for url in ["http://crm.bdsg.vn/mcp", "https://127.0.0.1/mcp", "https://bdsg.vn.evil.test/mcp", "https://user:secret@crm.bdsg.vn/mcp", "https://crm.bdsg.vn/mcp?token=x", "https://crm.bdsg.vn:8443/mcp"]:
            with self.subTest(url=url), self.assertRaises(ValueError): self.settings.save(OWNER, {**CONFIG,"url":url})
        for tools in [["*"], ["crm.list","crm.list"], "crm.list"]:
            with self.assertRaises(ValueError): self.settings.save(OWNER,{**CONFIG,"read_tools":tools})

    def test_reuse_credential_only_at_same_enabled_endpoint(self):
        self.settings.save(OWNER, CONFIG)
        self.settings.save(OWNER, {**CONFIG,"token":""})
        with self.assertRaises(ValueError):
            self.settings.save(OWNER, {**CONFIG,"url":"https://other.bdsg.vn/mcp","token":""})
        self.settings.disconnect(OWNER,"crm")
        with self.assertRaises(ValueError): self.settings.save(OWNER,{**CONFIG,"token":""})
        self.assertEqual(self.client.config, [])
        self.assertNotIn(CONFIG["token"], self.settings.path.read_text())

    def test_probe_does_not_grant_discovered_tools(self):
        self.settings.save(OWNER, {**CONFIG,"read_tools":[]})
        with patch.object(self.client,"kiem_tra", return_value={"tools":[{"name":"crm.write","annotations":{"readOnlyHint":True}}]}):
            result=self.settings.probe(OWNER,"crm")
        self.assertEqual(result["state"],"da-xac-minh")
        self.assertEqual(result["read_tools"],[])
        with self.assertRaises(PermissionError): self.client.goi(OWNER,"crm","crm.write",{})

    def test_probe_failure_is_redacted_and_partial_list_labelled(self):
        self.settings.save(OWNER,CONFIG)
        with patch.object(self.client,"kiem_tra",side_effect=ValueError(CONFIG["token"])):
            result=self.settings.probe(OWNER,"crm")
        self.assertEqual(result["state"],"loi-ket-noi")
        self.assertNotIn(CONFIG["token"],json.dumps(result))
        with patch.object(self.client,"kiem_tra",return_value={"tools":[{"name":"crm.list"}],"nextCursor":"next"}):
            self.assertFalse(self.settings.probe(OWNER,"crm")["tools_complete"])

    def test_http_handshake_and_session_cleanup_no_business_call(self):
        self.settings.save(OWNER,CONFIG)
        transport=Transport()
        with patch("dieu_phoi.socket.getaddrinfo",return_value=[(2,1,6,"",("1.1.1.1",443))]),patch("dieu_phoi.build_opener",return_value=transport):
            result=self.settings.probe(OWNER,"crm")
        self.assertEqual(result["state"],"da-xac-minh")
        methods=[json.loads(r.data)["method"] for r in transport.calls if r.data]
        self.assertEqual(methods,["initialize","notifications/initialized","tools/list"])
        self.assertEqual(transport.calls[-1].get_method(),"DELETE")
        self.assertEqual(transport.calls[-1].get_header("Mcp-session-id"),"test-session")

    def test_private_dns_denied_before_transport(self):
        self.settings.save(OWNER,CONFIG)
        with patch("dieu_phoi.socket.getaddrinfo",return_value=[(2,1,6,"",("127.0.0.1",443))]),patch("dieu_phoi.build_opener") as opener:
            result=self.settings.probe(OWNER,"crm")
        self.assertEqual(result["state"],"loi-ket-noi")
        opener.assert_not_called()

    def test_sse_multiline_stops_at_matching_result(self):
        self.settings.save(OWNER,CONFIG)
        transport=Transport()
        original=transport.open
        def open_(req,timeout):
            if req.data and json.loads(req.data)["method"]=="tools/list":
                response=Response(None,headers={"Content-Type":"text/event-stream"})
                lines=iter([b': keepalive\n',b'\n',b'data: {"jsonrpc":"2.0","id":2,\n',b'data: "result":{"tools":[{"name":"crm.list"}]}}\n',b'\n'])
                response.readline=lambda size: next(lines)  # Đọc sau kết quả sẽ làm bài kiểm hỏng.
                return response
            return original(req,timeout)
        with patch("dieu_phoi.socket.getaddrinfo",return_value=[(2,1,6,"",("1.1.1.1",443))]),patch("dieu_phoi.build_opener",return_value=transport),patch.object(transport,"open",side_effect=open_):
            result=self.settings.probe(OWNER,"crm")
        self.assertEqual(result["state"],"da-xac-minh")
        self.assertEqual(result["discovered_tools"],["crm.list"])


if __name__ == "__main__":
    unittest.main()
