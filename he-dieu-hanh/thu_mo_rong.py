"""Integration checks for documents, approval, schedules, user sessions and isolation."""

import base64
import json
import os
import tempfile
import time
import unittest
import sqlite3
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from may_chu import UngDung
from trinh_duyet_worker import check_url, public_addresses
from thu_mo_hinh_bdsg import Transport, ENV, Core, answer
from mo_hinh_bdsg import MoHinhBDSG, LoiMoHinhBDSG

OWNER = {"id": "chu-quan", "name": "Chu", "role": "quan-tri"}
A = {"id": "operator-a", "name": "A", "role": "operator"}
B = {"id": "operator-b", "name": "B", "role": "operator"}


class ThuMoRong(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = UngDung(self.temp.name, "https://thanhhoa.bdsg.vn", True)
        self.app.kho.tao_chu("mat-khau-rieng-trong-test")
        for actor in (A, B):
            self.app.kho.tao_agent(actor["id"], actor["name"], "operator")
        self.addCleanup(self.close)
        self.project = self.app.projects.create(
            A, {"name": "Du an thu", "context": "Ngu canh thu"}
        )

    def close(self):
        self.app.schedules.close()
        self.app.tasks.close()
        self.app.core.audit.close()
        self.temp.cleanup()

    def task(self, actor=A, **extra):
        result = self.app.tasks.create(
            actor, {"prompt": "Tong hop nhu cau kinh doanh thu nghiem", **extra}
        )
        for _ in range(100):
            doc = self.app.tasks.detail(actor, result["id"])
            if doc["status"] == "completed":
                return doc
            time.sleep(0.01)
        self.fail("task did not finish")

    def upload(self, name="du-lieu.csv", text="a,b\n1,2"):
        return self.app.documents.upload(
            A,
            {
                "project_id": self.project["id"],
                "name": name,
                "content_base64": base64.b64encode(text.encode()).decode(),
            },
        )

    def test_immutable_file_versions_and_task_snapshot(self):
        first = self.upload()
        second = self.upload(text="a,b\n5,6")
        self.assertEqual([first["version"], second["version"]], [1, 2])
        task = self.task(project_id=self.project["id"], document_ids=[first["id"]])
        self.assertEqual(task["documents"][0]["text"], "a,b\n1,2")
        self.assertIn(first["sha256"], task["artifacts"][0]["content"])
        meta, raw = self.app.documents.download(A, first["id"])
        self.assertEqual(raw, b"a,b\n1,2")
        with self.assertRaises(ValueError):
            self.app.documents.download(B, first["id"])
        self.assertNotIn("a,b", str(self.app.kho.hoat_dong(A["id"])))

    def test_file_validation_and_project_scope(self):
        for name in ("../secret.txt", "x.html", "x.py", "a\\b.csv"):
            with self.assertRaises(ValueError):
                self.upload(name)
        first = self.upload()
        with self.assertRaises(ValueError):
            self.app.documents.snapshot(A, [first["id"]], "other-project")
        with self.assertRaises(ValueError):
            self.app.documents.snapshot(A, [{}], self.project["id"])
        with self.assertRaises(ValueError):
            self.upload(text="\x00binary")

    def test_collaboration_permission_revocation(self):
        doc = self.upload()
        self.app.projects.share(
            A, {"id": self.project["id"], "identity": B["id"], "role": "viewer"}
        )
        self.assertEqual(self.app.documents.download(B, doc["id"])[1], b"a,b\n1,2")
        with self.assertRaises(ValueError):
            self.app.projects.update(B, {**self.project, "name": "Khong duoc sua"})
        self.app.projects.share(
            A, {"id": self.project["id"], "identity": B["id"], "role": "editor"}
        )
        self.app.projects.update(B, {**self.project, "name": "Duoc sua"})
        self.app.projects.share(
            A, {"id": self.project["id"], "identity": B["id"], "role": "revoke"}
        )
        with self.assertRaises(ValueError):
            self.app.documents.download(B, doc["id"])
        self.assertEqual(self.app.projects.list(B)["projects"], [])

    def test_exact_approval_once_and_no_auto_execution(self):
        task = self.task()
        args = {
            "task_id": task["id"],
            "tool": "kinh_doanh.tao_yeu_cau",
            "arguments": {
                "title": "Nhu cau thu",
                "sector": "cong-nghe",
                "description": "Du lieu gia lap kiem duyet",
            },
        }
        action = self.app.actions.propose(A, args)
        self.assertEqual(self.app.kho.yeu_cau(A["id"]), [])
        with self.assertRaises(PermissionError):
            self.app.actions.decide(
                A, {"id": action["id"], "digest": action["digest"], "approve": True}
            )
        with self.assertRaises(ValueError):
            self.app.actions.decide(
                OWNER, {"id": action["id"], "digest": "wrong", "approve": True}
            )
        value = self.app.actions.decide(
            OWNER, {"id": action["id"], "digest": action["digest"], "approve": True}
        )
        self.assertEqual(value["status"], "completed")
        self.assertEqual(len(self.app.kho.yeu_cau(A["id"])), 1)
        with self.assertRaises(ValueError):
            self.app.actions.decide(
                OWNER, {"id": action["id"], "digest": action["digest"], "approve": True}
            )

    def test_expired_and_revoked_actions_never_write(self):
        task = self.task()
        action = self.app.actions.propose(
            A,
            {"task_id": task["id"], "tool": "kinh_doanh.tao_yeu_cau", "arguments": {}},
        )
        self.app.kho.thu_hoi_agent(A["id"])
        with self.assertRaises(PermissionError):
            self.app.actions.decide(
                OWNER, {"id": action["id"], "digest": action["digest"], "approve": True}
            )
        self.assertEqual(self.app.kho.yeu_cau(A["id"]), [])

    def test_scheduler_claim_pause_and_no_replay(self):
        schedule = self.app.schedules.create(
            A,
            {
                "name": "Bao cao thu",
                "interval_seconds": 900,
                "task": {"prompt": "Tong hop danh muc cho bao cao thu"},
            },
        )
        self.app.schedules.tick(schedule["next_run"] + 1)
        rows = self.app.schedules.list(A)["schedules"]
        self.assertEqual(rows[0]["last_status"], "queued")
        first = rows[0]["last_task"]
        self.app.schedules.tick(schedule["next_run"] + 1)
        self.assertEqual(self.app.schedules.list(A)["schedules"][0]["last_task"], first)
        self.app.schedules.toggle(A, {"id": schedule["id"], "enabled": False})
        self.app.schedules.tick(time.time() + 100000)
        self.assertEqual(self.app.schedules.list(A)["schedules"][0]["last_task"], first)
        with self.assertRaises(ValueError):
            self.app.schedules.toggle(B, {"id": schedule["id"], "enabled": True})

    def test_schedule_cannot_grant_external_or_python(self):
        for key in ("allow_module_reads", "allow_python"):
            with self.assertRaises(ValueError):
                self.app.schedules.create(
                    A,
                    {
                        "name": "Sai quyen",
                        "interval_seconds": 900,
                        "task": {"prompt": "Tong hop bao cao du lieu thu", key: True},
                    },
                )

    def test_delegation_checks_project_acl_and_reduces_privileges(self):
        project = self.app.projects.create(OWNER, {"name": "Du an dieu phoi"})
        parent = self.task(
            actor=OWNER,
            project_id=project["id"],
            allow_delegation=True,
            allow_python=True,
        )
        self.app.projects.update(
            OWNER,
            {
                "id": project["id"],
                "name": "Du an da doi",
                "context": "NEW_CONTEXT_NOT_GRANTED_TO_PARENT",
            },
        )
        args = {
            "task_id": parent["id"],
            "recipient": A["id"],
            "prompt": "Tong hop danh muc cong khai cho phan viec con",
        }
        with self.assertRaises(ValueError):
            self.app.delegation.delegate(OWNER, args)
        self.app.projects.share(
            OWNER, {"id": project["id"], "identity": A["id"], "role": "viewer"}
        )
        child = self.app.delegation.delegate(OWNER, args)
        detail = self.app.tasks.detail(A, child["id"])
        self.assertEqual(detail["project"], parent["project"])
        self.assertEqual(detail["parent_id"], parent["id"])
        self.assertFalse(detail["allow_delegation"])
        self.assertFalse(detail["allow_module_reads"])
        with self.assertRaises(PermissionError):
            self.app.delegation.delegate(
                A,
                {
                    "task_id": child["id"],
                    "recipient": B["id"],
                    "prompt": "Khong duoc dieu phoi tiep",
                },
            )

    def test_write_connector_requires_explicit_grant_and_owner(self):
        args = {
            "platform_id": "bdsg_crm",
            "url": "https://crm.bdsg.vn/mcp",
            "token": "test-token-only",
            "read_tools": [],
            "write_tools": ["crm.create"],
        }
        with self.assertRaises(ValueError):
            self.app.connectors.save(OWNER, args)
        with self.assertRaises(PermissionError):
            self.app.connectors.save(A, {**args, "allow_writes": True})
        result = self.app.connectors.save(OWNER, {**args, "allow_writes": True})
        self.assertEqual(result["write_tools"], ["crm.create"])
        self.assertNotIn("test-token-only", str(result))

    def test_daily_api_reservation_is_enforced_before_provider(self):
        actors = [A, B, OWNER]
        for i in range(6):
            identity = "quota-test-" + str(i)
            self.app.kho.tao_agent(identity, identity, "operator")
            actors.append({"id": identity, "name": identity, "role": "operator"})
        for actor in actors[:8]:
            for _ in range(16):
                self.app.tasks.reserve_model(actor)
            with self.assertRaises(LoiMoHinhBDSG):
                self.app.tasks.reserve_model(actor)
        with self.assertRaises(LoiMoHinhBDSG):
            self.app.tasks.reserve_model(actors[8])

    def test_project_output_budget_is_shared_and_missing_usage_is_conservative(self):
        for actor in (A, B):
            for _ in range(16):
                self.app.tasks.reserve_model(actor, self.project["id"])
        with self.assertRaises(LoiMoHinhBDSG):
            self.app.tasks.reserve_model(OWNER, self.project["id"])

    def test_restore_preserves_documents_and_completed_tasks(self):
        doc = self.upload()
        task = self.task(project_id=self.project["id"], document_ids=[doc["id"]])
        with tempfile.TemporaryDirectory() as restored:
            with (
                sqlite3.connect(self.app.kho.db) as source,
                sqlite3.connect(os.path.join(restored, "van-hanh.db")) as destination,
            ):
                source.backup(destination)
            shutil.copytree(self.app.documents.root, os.path.join(restored, "tai-lieu"))
            app = UngDung(restored, "https://thanhhoa.bdsg.vn", True)
            try:
                self.assertEqual(app.documents.download(A, doc["id"])[1], b"a,b\n1,2")
                self.assertEqual(
                    app.tasks.detail(A, task["id"])["artifacts"], task["artifacts"]
                )
            finally:
                app.tasks.close()
                app.core.audit.close()

    def test_expiry_and_restart_do_not_repeat_actions(self):
        task = self.task()
        action = self.app.actions.propose(
            A,
            {"task_id": task["id"], "tool": "kinh_doanh.tao_yeu_cau", "arguments": {}},
        )
        with self.app.kho.ket_noi() as db:
            db.execute("UPDATE actions SET expires=0 WHERE id=?", (action["id"],))
        with self.assertRaises(ValueError):
            self.app.actions.decide(
                OWNER, {"id": action["id"], "digest": action["digest"], "approve": True}
            )
        with self.app.kho.ket_noi() as db:
            db.execute(
                "UPDATE actions SET status='executing' WHERE id=?", (action["id"],)
            )
        from hanh_dong import HanhDong

        recovered = HanhDong(self.app.kho, self.app.core, self.app.tasks)
        self.assertEqual(recovered.get(A, action["id"])["status"], "unknown")
        self.assertEqual(self.app.kho.yeu_cau(A["id"]), [])

    def test_user_login_role_revocation_and_no_password_log(self):
        password = "mat-khau-nguoi-dung-chi-trong-test"
        self.app.kho.tao_nguoi_dung(
            OWNER, {"id": "nhan-vien-thu", "name": "Thu", "password": password}
        )
        token, status = self.app.kho.dang_nhap("nhan-vien-thu", password, "test")
        self.assertEqual(status, "ok")
        self.assertEqual(self.app.kho.tu_phien(token)["role"], "operator")
        self.app.kho.thu_hoi_agent("nhan-vien-thu")
        self.assertIsNone(self.app.kho.tu_phien(token))
        self.assertNotIn(
            password, (self.app.kho.root / "nhat-ky-nhan.jsonl").read_text()
        )

    def test_browser_destination_and_dns_rebinding_guard(self):
        self.assertEqual(
            check_url("https://example.com/a", ["example.com"]), "https://example.com/a"
        )
        for url in (
            "http://example.com",
            "file:///etc/passwd",
            "https://example.com@127.0.0.1",
            "https://other.com",
            "https://example.com:8443",
        ):
            with self.assertRaises(ValueError):
                check_url(url, ["example.com"])
        with patch(
            "trinh_duyet_worker.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("127.0.0.1", 443))],
        ):
            with self.assertRaises(ValueError):
                public_addresses("example.com")

    def test_revocation_stops_running_model_before_next_tool(self):
        entered = threading.Event()
        release = threading.Event()
        from thu_mo_hinh_bdsg import Response, call

        class SlowTransport:
            def open(self, request, timeout):
                entered.set()
                release.wait(3)
                return Response(answer(calls=[call("kinh_doanh__danh_sach")]))

        self.app.tasks.model = MoHinhBDSG(environ=ENV, opener=SlowTransport())
        created = self.app.tasks.create(
            A, {"prompt": "Tong hop thong tin yeu cau thu nghiem"}
        )
        self.assertTrue(entered.wait(2))
        result = self.app.core.goi(OWNER, "nguoi_dung.thu_hoi", {"id": A["id"]})
        self.assertTrue(result["ok"])
        release.set()
        for _ in range(100):
            task = self.app.tasks._load(created["id"])
            if task["status"] in ("cancelled", "failed"):
                break
            time.sleep(0.01)
        self.assertEqual(task["status"], "cancelled")
        self.assertEqual(task["artifacts"], [])
        self.assertFalse(self.app.core.goi(A, "kinh_doanh.danh_sach", {})["ok"])

    @unittest.skipUnless(
        os.environ.get("BDSG_TEST_RUNTIME") == "1", "Requires Linux runtime"
    )
    def test_python_quota_inode_creation_and_api_cancel(self):
        task = self.task(allow_python=True)
        code = "import os\nfor name in ['/work/unbounded-file','/tmp/unbounded-file','/dev/unbounded-file','/unbounded-file']:\n try:os.open(name,os.O_CREAT|os.O_WRONLY);raise AssertionError('create bypass')\n except (PermissionError,OSError):pass\nprint('FILES_BOUNDED')"
        import platform

        if platform.machine() == "x86_64":
            code += "\nimport ctypes\nlibc=ctypes.CDLL(None,use_errno=True)\nfor number,args in [(425,(0,0)),(29,(0,4096,384)),(319,(b'x',0))]:\n ctypes.set_errno(0)\n assert libc.syscall(number,*args)==-1 and ctypes.get_errno()==1, 'kernel bypass'\nprint('KERNEL_BYPASSES_DENIED')"
        value = self.app.runtime.run(A, {"task_id": task["id"], "code": code})
        self.assertTrue(value["ok"], value)
        self.assertIn("FILES_BOUNDED", value["stdout"])
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                self.app.core.goi,
                A,
                "runtime.python",
                {"task_id": task["id"], "code": "while True: pass"},
            )
            for _ in range(100):
                if self.app.tasks._load(task["id"]).get("runtime_running"):
                    break
                time.sleep(0.01)
            started = time.monotonic()
            cancel = self.app.core.goi(A, "cong_viec.dung", {"id": task["id"]})
            self.assertLess(time.monotonic() - started, 1)
            self.assertTrue(cancel["ok"])
            self.assertFalse(future.result(timeout=3)["ok"])

    @unittest.skipUnless(
        os.environ.get("BDSG_TEST_RUNTIME") == "1", "Requires isolated PDF parser"
    )
    def test_pdf_text_extraction_in_isolated_runtime(self):
        stream = b"BT /F1 12 Tf 30 100 Td (BDSG PDF TEST) Tj ET"
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        raw = b"%PDF-1.4\n"
        offsets = [0]
        for index, obj in enumerate(objects, 1):
            offsets.append(len(raw))
            raw += str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
        xref = len(raw)
        raw += b"xref\n0 6\n0000000000 65535 f \n"
        raw += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
        raw += (
            b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
            + str(xref).encode()
            + b"\n%%EOF\n"
        )
        doc = self.app.documents.upload(
            A,
            {
                "project_id": self.project["id"],
                "name": "kiem-tra.pdf",
                "content_base64": base64.b64encode(raw).decode(),
            },
        )
        self.assertIn("BDSG PDF TEST", self.app.documents.get(A, doc["id"])["text"])

    @unittest.skipUnless(
        os.environ.get("BDSG_TEST_RUNTIME") == "1",
        "Requires Linux bubblewrap/seccomp test worker",
    )
    def test_python_namespaces_seccomp_and_artifact(self):
        task = self.task(allow_python=True)
        code = "import os,socket,subprocess\nassert not os.path.exists('/var/lib/bdsg-thanhhoa')\ntry: socket.socket();raise AssertionError('network open')\nexcept PermissionError:pass\ntry: subprocess.run(['/usr/bin/true']);raise AssertionError('exec open')\nexcept PermissionError:pass\nopen('ket-qua.csv','w').write('tong\\n3')\nprint('ISOLATION_OK')"
        result = self.app.runtime.run(A, {"task_id": task["id"], "code": code})
        self.assertTrue(result["ok"], result)
        self.assertIn("ISOLATION_OK", result["stdout"])
        self.assertEqual(result["artifacts"][0]["name"], "ket-qua.csv")
        with self.assertRaises(ValueError):
            self.app.runtime.run(B, {"task_id": task["id"], "code": "print(1)"})


class ThuSuDung(unittest.TestCase):
    def test_usage_and_long_followup(self):
        value = {
            **answer("bao cao"),
            "usage": {"prompt_tokens": 25, "completion_tokens": 10},
        }
        events = []
        model = MoHinhBDSG(environ=ENV, opener=Transport([value]))
        model.run(
            "x" * 6000,
            {},
            Core(),
            {},
            lambda kind, message, **extra: events.append((kind, extra)),
        )
        usage = next(extra for kind, extra in events if kind == "model-usage")
        self.assertEqual(usage["input_tokens"], 25)
        self.assertEqual(usage["output_tokens"], 10)

    def test_total_deadline_before_provider_call(self):
        transport = Transport([])
        model = MoHinhBDSG(environ=ENV, opener=transport)
        with patch("mo_hinh_bdsg.time.monotonic", side_effect=[0, 181]):
            with self.assertRaises(LoiMoHinhBDSG):
                model.run("test", {}, Core(), {})
        self.assertEqual(transport.requests, [])


if __name__ == "__main__":
    unittest.main()
