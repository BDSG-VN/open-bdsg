"""Kiểm quyền phiên web qua HTTP thật, không dùng tài khoản hoặc dữ liệu thật."""
import http.client
import json
import tempfile
import threading
import time
import unittest
from contextlib import closing

from kho import bam
from may_chu import UngDung, tao_may_chu


class ThuPhienHTTP(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = UngDung(self.temp.name, "https://example.invalid", True)
        self.app.kho.tao_chu("synthetic-owner-password-only")
        owner = {"id": "chu-quan", "role": "quan-tri"}
        for name in ("operator-a", "operator-b"):
            self.app.kho.tao_nguoi_dung(owner, {"id": name, "name": name,
                "password": "synthetic-user-password-only"})
        self.tokens = {}
        for key, identity in (("owner", "chu-quan"), ("owner2", "chu-quan"),
                              ("a", "operator-a"), ("a2", "operator-a"), ("b", "operator-b")):
            password = "synthetic-owner-password-only" if identity == "chu-quan" else "synthetic-user-password-only"
            self.tokens[key] = self.app.kho.dang_nhap(identity, password, "synthetic-" + key)[0]
        self.bearer = self.app.kho.tao_agent("agent-test", "Synthetic")
        self.server = tao_may_chu(self.app, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown(); self.server.server_close()
        self.app.schedules.close(); self.app.tasks.close(); self.app.core.audit.close()
        self.temp.cleanup()

    def request(self, path, who=None, body=None, headers=None, origin=True):
        hdr = {"Content-Type": "application/json"}
        if origin: hdr["Origin"] = self.app.origin
        if who: hdr["Cookie"] = "bdsg_session=" + self.tokens[who]
        hdr.update(headers or {})
        with closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)) as client:
            client.request("GET" if body is None else "POST", path,
                           None if body is None else json.dumps(body), hdr)
            response = client.getresponse()
            return response.status, json.loads(response.read())

    def sessions(self, who):
        status, value = self.request("/api/sessions", who)
        self.assertEqual(status, 200, value)
        return value["sessions"]

    def current(self, who):
        return next(item for item in self.sessions(who) if item["current"])

    def test_cookie_required_and_bearer_does_not_replace_web_session(self):
        self.assertEqual(self.request("/api/sessions")[0], 401)
        self.assertEqual(self.request("/api/sessions", headers={"Authorization": "Bearer " + self.bearer})[0], 401)
        self.assertEqual(self.request("/api/sessions/revoke-others", "a", {}, origin=False)[0], 403)
        self.assertEqual(len(self.sessions("a")), 2)

    def test_each_user_only_sees_own_sessions_and_no_credentials(self):
        own, other = self.sessions("a"), self.sessions("b")
        self.assertEqual(len(own), 2)
        self.assertEqual(len(other), 1)
        self.assertTrue(own[0]["current"])
        self.assertTrue({item["id"] for item in own}.isdisjoint(item["id"] for item in other))
        text = json.dumps(own)
        for token in [*self.tokens.values(), self.bearer]:
            self.assertNotIn(token, text); self.assertNotIn(bam(token), text)
        self.assertNotIn("session_hash", text)

    def test_revoke_others_keeps_current_and_unrelated_account(self):
        self.assertEqual(self.request("/api/sessions/revoke-others", "a", {})[:2], (200, {"revoked_count": 1}))
        self.assertFalse(self.request("/api/me", "a2")[1]["authenticated"])
        self.assertEqual(self.request("/api/sessions", "a2")[0], 401)
        self.assertTrue(self.request("/api/me", "a")[1]["authenticated"])
        self.assertTrue(self.request("/api/me", "b")[1]["authenticated"])

    def test_owner_cannot_use_self_session_api_to_revoke_another_user(self):
        foreign = self.current("b")["id"]
        denied = self.request("/api/sessions/revoke", "owner", {"id": foreign})
        missing = self.request("/api/sessions/revoke", "owner", {"id": "x" * 24})
        self.assertEqual(denied, missing)
        self.assertEqual(denied[0], 404)
        self.assertTrue(self.request("/api/me", "b")[1]["authenticated"])

    def test_rename_then_revoke_other_cookie_and_refuse_current(self):
        second = self.current("a2")["id"]
        self.assertEqual(self.request("/api/sessions/rename", "a", {"id": second, "label": "MacBook thử"})[0], 200)
        self.assertEqual(self.current("a2")["label"], "MacBook thử")
        current = self.current("a")["id"]
        self.assertEqual(self.request("/api/sessions/revoke", "a", {"id": current})[0], 400)
        self.assertEqual(self.request("/api/sessions/revoke", "a", {"id": second}), (200, {"revoked": True}))
        self.assertEqual(self.request("/api/sessions", "a2")[0], 401)

    def test_stale_actor_and_extra_token_fields_cannot_choose_kept_session(self):
        self.assertEqual(self.request("/api/sessions", "a",
            headers={"X-BDSG-Actor": "operator-b"})[0], 409)
        self.assertEqual(self.request("/api/sessions/revoke-others", "a", {},
            headers={"X-BDSG-Actor": "operator-b"})[0], 409)
        self.assertEqual(self.request("/api/sessions/revoke-others", "a", {"current_token": self.tokens["a2"]})[0], 400)
        self.assertEqual(len(self.sessions("a")), 2)

    def test_only_coarse_hint_is_recorded_and_legacy_created_remains_unknown(self):
        self.assertEqual(self.request("/api/me", "a", headers={"User-Agent": "PRIVATE-RAW-AGENT Windows"})[0], 200)
        self.request("/api/me", "a", headers={"User-Agent": "Linux"})
        current = self.current("a")
        self.assertEqual(current["client_hint"], "Windows")
        self.assertNotIn("PRIVATE-RAW-AGENT", json.dumps(current))
        legacy = "synthetic-legacy-token"
        with self.app.kho.ket_noi() as db:
            db.execute("INSERT INTO phien VALUES(?,?,?)", (bam(legacy), "operator-a", time.time() + 3600))
        self.tokens["legacy"] = legacy
        self.request("/api/me", "legacy", headers={"User-Agent": "Macintosh"})
        old = self.current("legacy")
        self.assertIsNone(old["created_at"])
        self.assertIsNotNone(old["last_seen_at"])
        self.assertEqual(old["client_hint"], "macOS")

    def test_invalid_label_is_rejected_without_disclosing_other_labels(self):
        identifier = self.current("a")["id"]
        for label in ("", "x" * 81, "private\nvalue", True):
            self.assertEqual(self.request("/api/sessions/rename", "a", {"id": identifier, "label": label})[0], 400)
        self.assertTrue(self.request("/api/me", "a")[1]["authenticated"])


if __name__ == "__main__": unittest.main()
