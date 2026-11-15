"""Hợp đồng lưu Office và từ chối callback/token bằng kho tổng hợp riêng."""

import base64
import concurrent.futures
import hashlib
import io
import os
import tempfile
import threading
import time
import unittest
import zipfile
from unittest.mock import patch

from chu_ky_office import sign, verify
from kiem_tep_office import kiem_tep
from mau_office import create
from may_chu import UngDung
from quet_virus import LoiChuaQuetVirus, LoiPhatHienVirus, QuetVirus
from van_phong import LoiXungDotVanPhong

SECRET = "test-only-not-a-production-secret-" * 2
A = {"id": "operator-a", "role": "operator", "name": "Nguoi thu"}
B = {"id": "operator-b", "role": "operator", "name": "Nguoi khac"}


class Scanner:
    def status(self):
        return {"state": "san-sang"}

    def scan(self, raw):
        if b"blocked-test-file" in raw:
            raise LoiPhatHienVirus("Tep thu bi chan")
        return {
            "virus_state": "khong-phat-hien",
            "sha256": hashlib.sha256(raw).hexdigest(),
        }


def changed_document(text):
    result = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(create("docx"))) as source,
        zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for path in source.namelist():
            raw = source.read(path)
            if path == "word/document.xml":
                raw = raw.replace(
                    b"<w:p/>",
                    ("<w:p><w:r><w:t>" + text + "</w:t></w:r></w:p>").encode(),
                )
            target.writestr(path, raw)
    return result.getvalue()


class ThuOfficeTichHop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(
            os.environ, {"BDSG_OFFICE_JWT_SECRET": SECRET, "BDSG_CLAMAV_SOCKET": ""}
        )
        env.start()
        self.addCleanup(env.stop)
        self.app = UngDung(self.tmp.name, "https://office.example.test", True)
        for target in ("du_an.ngat_phien", "kho.ngat_phien"):
            mocked = patch(target)
            mocked.start()
            self.addCleanup(mocked.stop)
        self.addCleanup(self.app.core.audit.close)
        self.addCleanup(self.app.tasks.close)
        self.app.kho.tao_chu("test-only-password")
        for actor in (A, B):
            self.app.kho.tao_agent(actor["id"], actor["name"], actor["role"])
        self.office = self.app.office
        self.office.scanner = Scanner()
        self.editor = self.app.office_editor
        self.project = self.app.projects.create(A, {"name": "Du an thu Office"})

    def file(self, extension="docx"):
        return self.editor.create(
            A, {"project_id": self.project["id"], "name": "tep." + extension}
        )

    def callback(self, payload):
        return self.editor.callback(
            {"token": sign({**payload, "exp": int(time.time()) + 60}, SECRET)}, ""
        )

    def test_three_formats_create_open_and_signed_source(self):
        for extension in ("docx", "xlsx", "pptx"):
            file = self.file(extension)
            session = self.editor.open(A, {"id": file["id"]})
            config = session["config"]
            self.assertEqual(config["document"]["fileType"], extension)
            verify(config["token"], SECRET, "editor")
            from urllib.parse import parse_qs, urlsplit

            token = sign(
                {
                    "payload": {"url": config["document"]["url"]},
                    "operation": "download",
                    "exp": time.time() + 60,
                },
                SECRET,
            )
            raw = self.editor.source(
                parse_qs(urlsplit(config["document"]["url"]).query), "Bearer " + token
            )
            self.assertEqual(
                kiem_tep("tep." + extension, raw)["format_state"], "cau-truc-co-ban"
            )
            with self.assertRaises(PermissionError):
                self.editor.source(
                    parse_qs(urlsplit(config["document"]["url"]).query), ""
                )

    def test_callback_snapshot_atomic_and_old_generation_cannot_overwrite(self):
        file = self.file()
        session = self.editor.open(A, {"id": file["id"]})
        key = session["key"]
        with self.app.kho.ket_noi() as db:
            db.execute(
                "UPDATE office_editors SET pending='request-1' WHERE key=?", (key,)
            )
            db.execute(
                "INSERT INTO office_editor_requests VALUES ('request-1',?,?,?)",
                (key, A["id"], A["role"]),
            )
        raw = changed_document("new-version")
        payload = {
            "key": key,
            "status": 6,
            "userdata": "request-1",
            "url": "https://untrusted.invalid/file",
        }
        with patch.object(self.editor, "_fetch", return_value=raw):
            self.assertEqual(self.callback(payload), {"error": 0})
            self.assertEqual(
                self.office.read(A, {"id": file["id"]})["file"]["version"], 2
            )
            self.assertEqual(self.callback(payload), {"error": 0})
            final = {"key": key, "status": 2, "url": "result", "users": [A["id"]]}
            self.callback(final)
            self.assertEqual(self.callback(final), {"error": 0})
        reopened = self.editor.open(A, {"id": file["id"]})
        self.assertNotEqual(reopened["key"], key)

    def test_acl_revocation_malware_and_compare_revision_reject_save(self):
        file = self.file()
        with self.assertRaises((ValueError, PermissionError)):
            self.editor.open(B, {"id": file["id"]})
        session = self.editor.open(A, {"id": file["id"]})
        key = session["key"]
        self.assertFalse(self.editor.engine_access(B, "/doc/" + key + "/c/"))
        with (
            patch.object(
                self.editor,
                "_fetch",
                return_value=changed_document("blocked-test-file"),
            ),
            patch.object(
                self.office.scanner, "scan", side_effect=LoiPhatHienVirus("test")
            ),
            self.assertRaises(LoiPhatHienVirus),
        ):
            self.callback(
                {"key": key, "status": 2, "url": "result", "users": [A["id"]]}
            )
        self.assertEqual(self.office.read(A, {"id": file["id"]})["file"]["version"], 1)
        self.office.update(
            A,
            {
                "id": file["id"],
                "expected_revision": 1,
                "action": "rename",
                "name": "doi.docx",
            },
        )
        with self.assertRaises(LoiXungDotVanPhong):
            self.callback(
                {"key": key, "status": 2, "url": "result", "users": [A["id"]]}
            )

    def test_every_write_scans_and_failure_is_not_published(self):
        with self.assertRaises(LoiPhatHienVirus):
            self.office.create(
                A,
                {
                    "project_id": self.project["id"],
                    "name": "blocked.txt",
                    "content_base64": base64.b64encode(b"blocked-test-file").decode(),
                },
            )
        self.assertEqual(
            self.office.list(A, {"project_id": self.project["id"]})["files"], []
        )
        self.office.scanner = QuetVirus("/does-not-exist/clamd.socket", timeout=0.1)
        with self.assertRaises(LoiChuaQuetVirus):
            self.file()
        self.assertEqual(
            self.office.list(A, {"project_id": self.project["id"]})["files"], []
        )

    def test_signed_callback_never_follows_arbitrary_url(self):
        for url in (
            "http://169.254.169.254/latest/meta-data/",
            "https://example.org/file",
            "http://127.0.0.1:8088/cache/files/wrong/file.docx",
            "https://office.example.test/office-docs/cache/files/abc/../secret",
        ):
            with self.assertRaises(ValueError):
                self.editor._fetch(url, "abc")

    def test_shared_editor_key_and_cache_query_cannot_substitute_another_file(self):
        file = self.file()
        self.app.projects.share(
            A, {"id": self.project["id"], "identity": B["id"], "role": "editor"}
        )
        first = self.editor.open(A, {"id": file["id"]})
        second = self.editor.open(B, {"id": file["id"]})
        self.assertEqual(first["key"], second["key"])
        other_project = self.app.projects.create(B, {"name": "Du an rieng"})
        other = self.editor.create(
            B, {"project_id": other_project["id"], "name": "rieng.docx"}
        )
        other_session = self.editor.open(B, {"id": other["id"]})
        path = (
            "/office-docs/cache/files/data/"
            + other_session["key"].replace("-", "%2d")
            + "_123/output.docx/output.docx?probe="
            + first["key"]
        )
        self.assertFalse(self.editor.engine_access(A, path))
        self.assertTrue(self.editor.engine_access(B, path))

    def test_error_session_cannot_commit_after_reopen(self):
        file = self.file()
        first = self.editor.open(A, {"id": file["id"]})
        self.callback({"key": first["key"], "status": 3})
        second = self.editor.open(A, {"id": file["id"]})
        self.assertNotEqual(first["key"], second["key"])
        with self.assertRaises(PermissionError):
            self.callback(
                {"key": first["key"], "status": 2, "users": [A["id"]], "url": "late"}
            )

    def _revocation_during_shared_snapshot(self, global_revoke):
        file = self.file()
        self.app.projects.share(
            A, {"id": self.project["id"], "identity": B["id"], "role": "editor"}
        )
        session = self.editor.open(A, {"id": file["id"]})
        self.editor.open(B, {"id": file["id"]})
        raw = changed_document("shared-content")
        entered, release = threading.Event(), threading.Event()

        def scan(value):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test synchronization")
            return Scanner().scan(value)

        with (
            patch.object(self.editor, "_fetch", return_value=raw),
            patch.object(self.office.scanner, "scan", side_effect=scan),
            concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor,
        ):
            future = executor.submit(
                self.callback,
                {
                    "key": session["key"],
                    "status": 2,
                    "users": [A["id"]],
                    "url": "snapshot",
                },
            )
            try:
                self.assertTrue(entered.wait(5))
                if global_revoke:
                    self.app.kho.thu_hoi_agent(B["id"])
                else:
                    self.app.projects.share(
                        A,
                        {
                            "id": self.project["id"],
                            "identity": B["id"],
                            "role": "revoke",
                        },
                    )
            finally:
                release.set()
            with self.assertRaises(PermissionError):
                future.result(timeout=5)
        self.assertEqual(self.office.read(A, {"id": file["id"]})["file"]["version"], 1)

    def test_project_revoke_is_atomic_with_shared_snapshot_lock(self):
        self._revocation_during_shared_snapshot(False)

    def test_direct_kho_revoke_used_by_cli_locks_shared_snapshot(self):
        self._revocation_during_shared_snapshot(True)

    def test_failed_force_save_can_retry_without_reopening(self):
        file = self.file()
        session = self.editor.open(A, {"id": file["id"]})
        key = session["key"]
        with self.app.kho.ket_noi() as db:
            db.execute("UPDATE office_editors SET pending='failed' WHERE key=?", (key,))
        self.callback({"key": key, "status": 7, "userdata": "failed"})
        self.assertTrue(self.editor.progress(A, {"key": key})["save_error"])
        with patch("soan_thao_office.http.client.HTTPConnection") as client:
            response = client.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = b'{"error":0}'
            request = self.editor.save(A, {"key": key})
        with patch.object(
            self.editor, "_fetch", return_value=changed_document("retried")
        ):
            self.callback(
                {
                    "key": key,
                    "status": 6,
                    "userdata": request["request_id"],
                    "url": "snapshot",
                }
            )
        self.assertEqual(self.office.read(A, {"id": file["id"]})["file"]["version"], 2)

    def test_create_retry_returns_same_file_and_rejects_changed_payload(self):
        args = {
            "project_id": self.project["id"],
            "name": "lap.docx",
            "request_key": "a" * 32,
        }
        first = self.editor.create(A, args)
        with patch(
            "zipfile.time.localtime", return_value=(2031, 7, 1, 0, 0, 0, 1, 182, 0)
        ):
            retry = self.editor.create(A, args)
        self.assertEqual(first["id"], retry["id"])
        with self.assertRaises(LoiXungDotVanPhong):
            self.editor.create(A, {**args, "name": "khac.docx"})
        text = {
            "project_id": self.project["id"],
            "name": "ghi-chu.txt",
            "content_base64": base64.b64encode(b"hello").decode(),
            "request_key": "b" * 32,
        }
        one = self.office.create(A, text)
        two = self.office.create(A, text)
        self.assertEqual(one["id"], two["id"])
        with self.assertRaises(LoiXungDotVanPhong):
            self.office.create(
                A, {**text, "content_base64": base64.b64encode(b"changed").decode()}
            )

    def test_upload_finish_and_retry_return_same_version_scan_receipt(self):
        raw = b"scan receipt fixture"
        upload = self.office.begin_upload(
            A,
            {
                "project_id": self.project["id"],
                "name": "quet.txt",
                "total": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "request_key": "c" * 32,
            },
        )
        self.office.upload_part(
            A,
            {
                "id": upload["id"],
                "offset": 0,
                "content_base64": base64.b64encode(raw).decode(),
            },
        )
        first = self.office.finish_upload(A, {"id": upload["id"]})
        retry = self.office.finish_upload(A, {"id": upload["id"]})
        self.assertEqual(first["checks"], retry["checks"])
        self.assertEqual(first["checks"]["virus_state"], "khong-phat-hien")
        self.assertEqual(first["checks"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(
            (first["file"]["id"], first["version"]),
            (retry["file"]["id"], retry["version"]),
        )


class ThuChuKyOffice(unittest.TestCase):
    def test_tamper_expiry_algorithm_and_operation(self):
        token = sign(
            {
                "payload": {"status": 6},
                "exp": time.time() + 60,
                "operation": "callback",
            },
            SECRET,
        )
        self.assertEqual(verify(token, SECRET, "callback"), {"status": 6})
        for value, op in (
            (token + "x", "callback"),
            (token, "download"),
            (sign({"exp": 1}, SECRET), "callback"),
        ):
            with self.assertRaises(PermissionError):
                verify(value, SECRET, op)


if __name__ == "__main__":
    unittest.main()
