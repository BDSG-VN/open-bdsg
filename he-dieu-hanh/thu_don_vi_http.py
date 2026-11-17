"""Cổng thử đơn vị: HTTP thật, đăng nhập cookie thật, chỉ dữ liệu tổng hợp."""
import base64
import http.client
import json
import tempfile
import threading
import time
import unittest

from may_chu import UngDung, tao_may_chu


class ThuDonViHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = UngDung(self.tmp.name, "https://preview.test", True, unit_preview=True)
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

    def test_unported_routes_tools_and_mcp_are_denied(self):
        for path in ("/api/requests", "/api/activity", "/api/agents",
                     "/api/connections", "/api/model", "/api/modules", "/api/google/callback",
                     "/api/auth/google", "/api/office-source", "/api/office-engine-auth", "/mcp"):
            self.assertEqual(self.request(path, who="chu-quan", unit=self.units[0])[0], 403, path)
        for path in ("/mcp", "/api/office-callback", "/api/google/start", "/api/model-config", "/api/customer-support"):
            self.assertEqual(self.request(path, {}, "chu-quan", self.units[0])[0], 403, path)
        self.assertEqual(self.request("/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                     unit=self.units[0], headers={"Authorization": "Bearer " + self.bearer})[0], 403)
        for tool in ("runtime.python", "mo_hinh.trang_thai",
                     "van_phong.google_nhap", "van_phong.tao_office", "van_phong.mo_soan_thao",
                     "van_phong.luu_soan_thao", "cau_hinh.dau_noi", "nguoi_dung.tao", "nhat_ky.danh_sach"):
            self.assertEqual(self.tool(tool)[0], 403, tool)

    def test_membership_control_and_revocation_rechecked(self):
        unit = self.units[0]
        self.value(self.tool("du_an.tao", {"name": "Du an cho thanh vien"}))
        self.assertEqual(self.request("/api/units/members", {"identity": "nguoi-b", "role": "member"}, "nguoi-a", unit)[0], 200)
        self.assertEqual(self.value(self.tool("du_an.danh_sach", who="nguoi-b"))["projects"], [])
        self.assertEqual(self.request("/api/units/members", who="nguoi-b", unit=unit)[0], 403)
        self.assertEqual(self.request("/api/units/members", {"identity": "nguoi-b", "role": "revoke"}, "chu-quan", unit)[0], 200)
        self.assertEqual(self.tool("du_an.danh_sach", who="nguoi-b")[0], 403)

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
