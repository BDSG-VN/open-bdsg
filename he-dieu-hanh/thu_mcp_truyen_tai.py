"""Giao thức MCP trên HTTP adapter tổng hợp; không gửi yêu cầu Internet."""
import json
import unittest

from mcp_truyen_tai import TruyenTaiMCP

CONFIG = {"url": "https://crm.bdsg.vn/mcp", "token": "synthetic-mcp-private-token"}


class Response:
    def __init__(self, status, payload=None, headers=None):
        self.status = status
        self.headers = {key.lower(): value for key, value in (headers or {}).items()}
        self.headers.setdefault("content-type", "application/json")
        self.raw = json.dumps(payload).encode() if payload is not None else b""

    def getheader(self, key):
        return self.headers.get(key.lower())

    def read1(self, size, timeout):
        raw, self.raw = self.raw[:size], self.raw[size:]
        return raw

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class Exchange:
    def __init__(self):
        self.requests = []

    def __call__(self, host, address, path, method, headers, body, deadline, guard):
        guard()
        self.requests.append((host, address, path, method, dict(headers), body))
        if method == "DELETE":
            return Response(204)
        request = json.loads(body)
        if request["method"] == "notifications/initialized":
            return Response(202)
        result = {"protocolVersion": "2025-06-18", "capabilities": {}} if request["method"] == "initialize" else {
            "tools": [{"name": "crm.list"}]}
        return Response(200, {"jsonrpc": "2.0", "id": request["id"], "result": result}, {"Mcp-Session-Id": "test-session"})


class ThuMCPTruyenTai(unittest.TestCase):
    @staticmethod
    def resolve(*_args, **_options):
        return [(2, 1, 6, "", ("1.1.1.1", 443))]

    def test_handshake_giu_dia_chi_va_session_khong_goi_nghiep_vu_khi_probe(self):
        exchange = Exchange()
        resolutions = []
        def resolve(host, port, **options):
            resolutions.append(host)
            return [(2, 1, 6, "", ("1.1.1.1", 443))]
        transport = TruyenTaiMCP(resolver=resolve, exchange=exchange)
        result = transport.goi(CONFIG, "tools/list", {}, lambda: None)
        self.assertEqual(result, {"tools": [{"name": "crm.list"}]})
        self.assertEqual(resolutions, ["crm.bdsg.vn"])
        self.assertEqual([json.loads(row[5])["method"] for row in exchange.requests if row[5]], [
            "initialize", "notifications/initialized", "tools/list"])
        self.assertEqual(exchange.requests[-1][3], "DELETE")
        self.assertTrue(all(row[:3] == ("crm.bdsg.vn", "1.1.1.1", "/mcp") for row in exchange.requests))
        self.assertEqual(exchange.requests[-1][4]["MCP-Session-Id"], "test-session")

    def test_dns_co_ip_rieng_bat_ky_chan_truoc_gui_chung_thu(self):
        for private in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:192.168.1.1"):
            exchange = Exchange()
            resolver = lambda *_args, **_options: self.resolve()+[(2, 1, 6, "", (private, 443))]
            with self.subTest(address=private), self.assertRaises(PermissionError):
                TruyenTaiMCP(resolver=resolver, exchange=exchange).goi(CONFIG, "tools/list", {}, lambda: None)
            self.assertEqual(exchange.requests, [])

    def test_redirect_khong_duoc_theo(self):
        sent = []
        def redirect(*args):
            sent.append(args)
            return Response(302, headers={"Location": "https://other.bdsg.vn/mcp"})
        with self.assertRaises(ValueError):
            TruyenTaiMCP(resolver=self.resolve, exchange=redirect).goi(CONFIG, "tools/list", {}, lambda: None)
        self.assertEqual(len(sent), 1)

    def test_sse_nhieu_chunk_chi_doc_result_dung_id_khong_thuc_thi_yeu_cau_tu_server(self):
        exchange = Exchange()
        def streaming(*args):
            response = exchange(*args)
            if args[5] and json.loads(args[5])["method"] == "tools/list":
                response.headers["content-type"] = "text/event-stream"
                response.raw = (b'data: {"jsonrpc":"2.0","id":999,"method":"sampling/createMessage"}\r\n\r\n'
                    b'data: {"jsonrpc":"2.0","id":2,\r\ndata: "result":{"tools":[{"name":"crm.list"}]}}\r\n\r\n')
                original = response.read1
                response.read1 = lambda size, timeout: original(min(size, 7), timeout)
            return response
        result = TruyenTaiMCP(resolver=self.resolve, exchange=streaming).goi(CONFIG, "tools/list", {}, lambda: None)
        self.assertEqual(result, {"tools": [{"name": "crm.list"}]})
        self.assertEqual(len(exchange.requests), 4)

    def test_session_header_co_ky_tu_dieu_khien_bi_chan(self):
        exchange = Exchange()
        def invalid_session(*args):
            response = exchange(*args)
            response.headers["mcp-session-id"] = "bad\r\nInjected: value"
            return response
        with self.assertRaises(ValueError):
            TruyenTaiMCP(resolver=self.resolve, exchange=invalid_session).goi(CONFIG, "tools/list", {}, lambda: None)
        self.assertEqual(len(exchange.requests), 1)

    def test_loi_json_rpc_va_body_vuot_tran_khong_tra_ket_qua(self):
        for kind in ("oversize", "wrong-version", "boolean-id", "rpc-error"):
            exchange = Exchange()
            def invalid(*args):
                response = exchange(*args)
                if args[5] and json.loads(args[5])["method"] == "tools/list":
                    if kind == "oversize":
                        response.raw = b"x"*(2*1024*1024+1)
                    else:
                        body = {"jsonrpc": "2.0", "id": 2, "result": {"tools": []}}
                        if kind == "wrong-version": body["jsonrpc"] = "1.0"
                        if kind == "boolean-id": body["id"] = True
                        if kind == "rpc-error": body["error"] = {"message": "synthetic-error"}
                        response.raw = json.dumps(body).encode()
                return response
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                TruyenTaiMCP(resolver=self.resolve, exchange=invalid).goi(CONFIG, "tools/list", {}, lambda: None)


if __name__ == "__main__":
    unittest.main()
