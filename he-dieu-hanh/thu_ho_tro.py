"""Khách dùng hướng dẫn công khai; không mượn quyền hoặc tín dụng chủ quản."""

import http.client
import json
import tempfile
import threading
import unittest
from may_chu import UngDung, tao_may_chu


class ThuHoTro(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = UngDung(self.temp.name, "https://thanhhoa.bdsg.vn", True)
        self.server = tao_may_chu(self.app, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.app.tasks.close()
        self.app.core.audit.close()
        self.temp.cleanup()

    def request(self, path, body=None, headers=None):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=5
        )
        conn.request(
            "GET" if body is None else "POST",
            path,
            None if body is None else json.dumps(body),
            {
                "Content-Type": "application/json",
                "Origin": self.app.origin,
                **(headers or {}),
            },
        )
        response = conn.getresponse()
        value = json.loads(response.read())
        status = response.status
        self.cookie = (response.getheader("Set-Cookie") or "").split(";", 1)[0]
        conn.close()
        return status, value

    def test_anonymous_guidance_has_catalogue_provenance_and_no_write_power(self):
        status, result = self.request(
            "/api/customer-support",
            {"agent": "tu-van", "message": "Tôi cần tìm nền tảng CRM"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(result["mode"], "huong-dan")
        self.assertFalse(result["can_execute"])
        self.assertTrue(any("crm" in p["id"] for p in result["platforms"]))
        self.assertEqual(result["source"], "nen-tang/danh-muc.json")

    def test_chatgpt_connection_requires_owner_and_cannot_fake_a_login(self):
        self.assertEqual(self.request("/api/chatgpt-connection")[0], 401)
        self.app.kho.tao_chu("synthetic-owner-password-only")
        self.request(
            "/api/login",
            {"username": "chu-quan", "password": "synthetic-owner-password-only"},
        )
        headers = {"Cookie": self.cookie}
        status, result = self.request("/api/chatgpt-connection", headers=headers)
        self.assertEqual(status, 200)
        self.assertFalse(result["enabled"])
        self.assertFalse(result["has_client_id"])
        self.assertEqual(result["state"], "awaiting_partner_approval")
        self.assertEqual(
            self.request("/api/chatgpt-connection/start", {}, headers)[0], 409
        )
        self.assertFalse(self.request("/api/model")[1]["configured"])

    def test_guides_registration_and_purchase_without_claiming_execution(self):
        for agent in ("tai-khoan", "mua-hang"):
            status, result = self.request(
                "/api/customer-support",
                {
                    "agent": agent,
                    "message": "Hướng dẫn giúp tôi",
                    "platform_id": "bdsg_crm",
                },
            )
            self.assertEqual(status, 200)
            self.assertEqual(len(result["platforms"]), 1)
            self.assertEqual(result["platforms"][0]["url"], "https://crm.bdsg.vn/")
            self.assertEqual(len(result["steps"]), 4)
            self.assertFalse(result["can_execute"])

    def test_public_support_cannot_select_tools_credentials_or_foreign_urls(self):
        base = {"agent": "tu-van", "message": "test"}
        for extra in (
            {"tool": "nguoi_dung.tao"},
            {"api_key": "synthetic-token-never-valid"},
            {"platform_id": "https://evil.test"},
            {"agent": "admin"},
            {"agent": []},
            {"message": "x" * 1001},
        ):
            self.assertEqual(
                self.request("/api/customer-support", {**base, **extra})[0], 400
            )
        self.assertEqual(
            self.request(
                "/api/customer-support", base, {"Origin": "https://evil.test"}
            )[0],
            403,
        )
        self.assertEqual(
            self.request("/api/tools", {"name": "nguoi_dung.tao", "arguments": {}})[0],
            401,
        )
        result = self.request(
            "/api/customer-support",
            {**base, "message": "<script>synthetic-untrusted</script>"},
        )[1]
        self.assertNotIn("synthetic-untrusted", json.dumps(result))

    def test_public_support_has_bounded_rate_and_retry_hint(self):
        for _ in range(20):
            self.assertEqual(
                self.request(
                    "/api/customer-support", {"agent": "tu-van", "message": "CRM"}
                )[0],
                200,
            )
        self.assertEqual(
            self.request(
                "/api/customer-support", {"agent": "tu-van", "message": "CRM"}
            )[0],
            429,
        )

    def test_operator_cannot_read_or_start_owner_chatgpt_connection(self):
        self.app.kho.tao_chu("synthetic-owner-password-only")
        self.request(
            "/api/login",
            {"username": "chu-quan", "password": "synthetic-owner-password-only"},
        )
        self.assertEqual(
            self.request(
                "/api/tools",
                {
                    "name": "nguoi_dung.tao",
                    "arguments": {
                        "id": "test-operator",
                        "name": "Test operator",
                        "password": "synthetic-operator-password-only",
                    },
                },
                {"Cookie": self.cookie},
            )[0],
            200,
        )
        self.request(
            "/api/login",
            {
                "username": "test-operator",
                "password": "synthetic-operator-password-only",
            },
        )
        headers = {"Cookie": self.cookie}
        self.assertEqual(
            self.request("/api/chatgpt-connection", headers=headers)[0], 403
        )
        self.assertEqual(
            self.request("/api/chatgpt-connection/start", {}, headers)[0], 403
        )


if __name__ == "__main__":
    unittest.main()
