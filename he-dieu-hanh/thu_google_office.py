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

    def test_upload_requires_matching_confirmation_and_keeps_uncertain_ledger(self):
        self.google._store(OWNER["id"], self.token)
        file = self.app.office_editor.create(
            OWNER, {"project_id": self.project["id"], "name": "thu.docx"}
        )
        args = {"id": file["id"], "request_key": "c" * 32}
        for response in (b"{}", b"[]", b"not-json", b'{"id":"wrong-drive-id-123"}'):
            with self.subTest(response=response):
                with self.app.kho.ket_noi() as db:
                    db.execute("DELETE FROM google_office_exports")
                with patch.object(self.google, "_request", side_effect=[
                    b'{"ids":["fixed-drive-id-123"]}', response
                ]), self.assertRaises(LoiKetNoiGoogle):
                    self.google.export_file(OWNER, args)
                with self.app.kho.ket_noi() as db:
                    self.assertEqual(db.execute(
                        "SELECT state FROM google_office_exports"
                    ).fetchone()[0], "pending")
        with self.app.kho.ket_noi() as db:
            db.execute("DELETE FROM google_office_exports")
        with patch.object(self.google, "_request", side_effect=[
            b'{"ids":["fixed-drive-id-123"]}', b'{"id":"fixed-drive-id-123"}'
        ]):
            self.assertEqual(self.google.export_file(OWNER, args)["state"], "da-xuat-ban-sao")

    def test_invalid_oauth_payload_is_controlled_and_never_stored(self):
        base = {"access_token": "test", "token_type": "Bearer", "expires_in": 3600, "scope": SCOPE}
        values = [[], None, "invalid", {**base, "token_type": []},
                  {**base, "scope": []}, {**base, "access_token": ""},
                  {**base, "refresh_token": []}]
        for payload in values:
            with self.subTest(payload=payload), patch.object(
                self.google, "_request", return_value=json.dumps(payload).encode()
            ), self.assertRaises(LoiKetNoiGoogle):
                self.google._token_request({"grant_type": "authorization_code"})
        self.assertEqual(self.google.status(OWNER)["state"], "chua-ket-noi")

    def test_invalid_drive_metadata_does_not_download_or_publish(self):
        self.google._store(OWNER["id"], self.token)
        for metadata in ([], {}, {"name": "x.docx", "mimeType": "x", "size": []},
                         {"name": None, "mimeType": "x"}):
            with self.subTest(metadata=metadata), patch.object(
                self.google, "_request", return_value=json.dumps(metadata).encode()
            ) as request, self.assertRaises(LoiKetNoiGoogle):
                self.google.import_file(OWNER, {"project_id": self.project["id"],
                    "drive_id": "test-file-id-123", "request_key": "d" * 32})
            self.assertEqual(request.call_count, 1)
        with self.app.kho.ket_noi() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM google_office_imports").fetchone()[0], 0)

    def test_resumable_upload_requires_confirmed_identity_too(self):
        self.google._store(OWNER["id"], self.token)
        file = self.app.office.create_bytes(
            OWNER, self.project["id"], "lon.txt", b"a" * (6 * 1024 * 1024)
        )
        with patch.object(self.google, "_request", side_effect=[
            b'{"ids":["fixed-drive-id-123"]}',
            (b"", {"Location": "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=test-only"}),
            b'{"id":"wrong-drive-id-123"}'
        ]), self.assertRaises(LoiKetNoiGoogle):
            self.google.export_file(OWNER, {"id": file["id"], "request_key": "e" * 32})
        with self.app.kho.ket_noi() as db:
            self.assertEqual(db.execute("SELECT state FROM google_office_exports").fetchone()[0], "pending")

    def test_drive_list_validates_and_only_returns_declared_metadata(self):
        self.google._store(OWNER["id"], self.token)
        for payload in ([], {"files": {}}, {"files": [None]}, {"files": [{"id": "bad"}]}):
            with self.subTest(payload=payload), patch.object(
                self.google, "_request", return_value=json.dumps(payload).encode()
            ), self.assertRaises(LoiKetNoiGoogle):
                self.google.list(OWNER)
        item = {"id": "test-file-id-123", "name": "thu.docx", "mimeType": "test/type", "size": "3"}
        with patch.object(self.google, "_request", return_value=json.dumps(
            {"files": [{**item, "unexpected": "not-for-interface"}], "nextPageToken": "next"}
        ).encode()):
            result = self.google.list(OWNER)
            self.assertEqual(result["files"], [item])
            self.assertTrue(result["limited"])

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
