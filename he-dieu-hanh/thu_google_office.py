"""OAuth và Drive dùng phản hồi tổng hợp; không thay bài kiểm Google thật."""

import concurrent.futures
import hashlib
import importlib.util
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from google_office import SCOPE, GoogleOffice, LoiKetNoiGoogle
from may_chu import UngDung
from thu_office_tich_hop import Scanner

OWNER = {"id": "chu-quan", "role": "quan-tri", "name": "Chu thu nghiem"}


@unittest.skipUnless(
    importlib.util.find_spec("cryptography"), "Cần cryptography cho kho OAuth"
)
class ThuGoogleOffice(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        client, key = root / "client.json", root / "vault.key"
        client.write_text(
            json.dumps(
                {
                    "web": {
                        "client_id": "test-only.apps.googleusercontent.com",
                        "client_secret": "fake-client-secret",
                        "redirect_uris": [
                            "https://office.example.test/api/google/callback"
                        ],
                        "picker_api_key": "fake-picker-key",
                        "project_number": "123456789",
                    }
                }
            )
        )
        key.write_bytes(os.urandom(32))
        env = patch.dict(
            os.environ,
            {
                "BDSG_GOOGLE_CLIENT_FILE": str(client),
                "BDSG_GOOGLE_VAULT_KEY_FILE": str(key),
                "BDSG_CLAMAV_SOCKET": "",
                "BDSG_OFFICE_JWT_SECRET": "",
            },
        )
        env.start()
        self.addCleanup(env.stop)
        self.app = UngDung(str(root / "data"), "https://office.example.test", True)
        self.addCleanup(self.app.tasks.close)
        self.addCleanup(self.app.core.audit.close)
        self.app.kho.tao_chu("only-test-password")
        self.app.office.scanner = Scanner()
        self.google = self.app.google_office
        self.session, _ = self.app.kho.dang_nhap("chu-quan", "only-test-password", "qa")
        self.project = self.app.projects.create(OWNER, {"name": "Du an thu Google"})
        self.token = {
            "access_token": "test-only-access",
            "refresh_token": "test-only-refresh",
            "token_type": "Bearer",
            "scope": SCOPE,
            "expires_at": time.time() + 3600,
        }

    def test_state_pkce_one_use_binding_session_and_encrypted_vault(self):
        url, binding = self.google.start(OWNER, self.session)
        params = parse_qs(urlsplit(url).query)
        self.assertEqual(params["code_challenge_method"], ["S256"])
        query = {"state": params["state"], "code": ["fake-code"]}
        with patch.object(
            self.google, "_token_request", return_value=self.token
        ) as request:
            with self.assertRaises(LoiKetNoiGoogle):
                self.google.callback(query, "wrong-browser")
            request.assert_not_called()
            self.google.callback(query, binding)
            with self.assertRaises(LoiKetNoiGoogle):
                self.google.callback(query, binding)
        self.assertEqual(
            self.google._load(OWNER["id"])["refresh_token"], "test-only-refresh"
        )
        with self.app.kho.ket_noi() as db:
            blob = db.execute("SELECT cipher FROM google_office_tokens").fetchone()[0]
            self.assertNotIn(b"test-only-refresh", blob)
            db.execute("UPDATE google_office_tokens SET cipher=?", (bytes(len(blob)),))
        self.assertEqual(self.google.status(OWNER)["state"], "chua-ket-noi")

    def test_logout_denies_pending_consent_before_token_exchange(self):
        url, binding = self.google.start(OWNER, self.session)
        query = {"state": parse_qs(urlsplit(url).query)["state"], "code": ["code"]}
        self.app.kho.dang_xuat(self.session)
        with patch.object(self.google, "_token_request") as request:
            with self.assertRaises(LoiKetNoiGoogle):
                self.google.callback(query, binding)
            request.assert_not_called()

    def test_refresh_preserves_refresh_token_and_disconnect_really_revokes(self):
        self.google._store(OWNER["id"], {**self.token, "expires_at": 1})
        updated = {"access_token": "test-access-2", "expires_at": time.time() + 3600}
        with patch.object(self.google, "_token_request", return_value=updated):
            self.assertEqual(
                self.google._access(OWNER)["Authorization"], "Bearer test-access-2"
            )
        self.assertEqual(
            self.google._load(OWNER["id"])["refresh_token"], "test-only-refresh"
        )
        with patch.object(self.google, "_request", return_value=b"") as request:
            self.google.disconnect(OWNER)
            self.assertEqual(request.call_args.args[2], "/revoke")
        self.assertEqual(self.google.status(OWNER)["state"], "chua-ket-noi")

    def test_native_export_import_is_a_separate_scanned_version(self):
        from mau_office import create

        self.google._store(OWNER["id"], self.token)
        for extension, native in (
            ("docx", "document"),
            ("xlsx", "spreadsheet"),
            ("pptx", "presentation"),
        ):
            raw = create(extension)
            responses = [
                json.dumps(
                    {
                        "name": "Tai lieu thu",
                        "mimeType": "application/vnd.google-apps." + native,
                    }
                ).encode(),
                raw,
            ]
            with patch.object(
                self.google, "_request", side_effect=responses
            ) as request:
                args = {
                    "project_id": self.project["id"],
                    "drive_id": "test-file-id-123",
                    "request_key": hashlib.sha256(extension.encode()).hexdigest(),
                }
                result = self.google.import_file(OWNER, args)
                retry = self.google.import_file(OWNER, args)
                self.assertEqual(retry["file"]["id"], result["file"]["id"])
                self.assertEqual(request.call_count, 2)
                self.assertTrue(result["file"]["name"].endswith("." + extension))
                self.assertIn("/export?", request.call_args_list[1].args[2])
                self.assertIn("mimeType=", request.call_args_list[1].args[2])
                read = self.app.office.read(OWNER, {"id": result["file"]["id"]})
                self.assertEqual(read["checks"]["virus_state"], "khong-phat-hien")

    def test_uncertain_upload_reconciles_even_with_new_frontend_request(self):
        self.google._store(OWNER["id"], self.token)
        file = self.app.office_editor.create(
            OWNER, {"project_id": self.project["id"], "name": "thu.docx"}
        )
        with self.app.kho.ket_noi() as db:
            raw = db.execute(
                "SELECT content FROM office_versions WHERE file_id=?", (file["id"],)
            ).fetchone()[0]
        args = {"id": file["id"], "request_key": "a" * 32}
        with (
            patch.object(
                self.google,
                "_request",
                side_effect=[
                    b'{"ids":["fixed-drive-id-123"]}',
                    LoiKetNoiGoogle("timeout"),
                ],
            ),
            self.assertRaises(LoiKetNoiGoogle),
        ):
            self.google.export_file(OWNER, args)
        remote = json.dumps(
            {
                "id": "fixed-drive-id-123",
                "size": str(len(raw)),
                "md5Checksum": hashlib.md5(raw, usedforsecurity=False).hexdigest(),
            }
        ).encode()
        with patch.object(self.google, "_request", return_value=remote) as request:
            result = self.google.export_file(OWNER, {**args, "request_key": "b" * 32})
            self.assertEqual(result["state"], "da-xuat-ban-sao")
            self.assertEqual(request.call_args.args[1], "GET")

    def test_missing_client_is_not_a_fake_connection(self):
        with patch.dict(
            os.environ,
            {"BDSG_GOOGLE_CLIENT_FILE": "", "BDSG_GOOGLE_VAULT_KEY_FILE": ""},
        ):
            google = GoogleOffice(self.app.office, self.app.origin)
        self.assertEqual(google.status(OWNER)["state"], "chua-cau-hinh")
        with self.assertRaises(LoiKetNoiGoogle):
            google.start(OWNER, self.session)

    def test_disconnect_cannot_be_undone_by_inflight_reconnect_callback(self):
        self.google._store(OWNER["id"], self.token)
        url, binding = self.google.start(OWNER, self.session)
        query = {"state": parse_qs(urlsplit(url).query)["state"], "code": ["test-code"]}
        entered, release = threading.Event(), threading.Event()

        def exchange(_fields):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test synchronization")
            return {**self.token, "access_token": "reconnected-test-token"}

        with (
            patch.object(self.google, "_token_request", side_effect=exchange),
            patch.object(self.google, "_request", return_value=b""),
            concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor,
        ):
            callback = executor.submit(self.google.callback, query, binding)
            try:
                self.assertTrue(entered.wait(5))
                disconnect = executor.submit(self.google.disconnect, OWNER)
            finally:
                release.set()
            callback.result(timeout=5)
            disconnect.result(timeout=5)
        self.assertEqual(self.google.status(OWNER)["state"], "chua-ket-noi")


if __name__ == "__main__":
    unittest.main()
