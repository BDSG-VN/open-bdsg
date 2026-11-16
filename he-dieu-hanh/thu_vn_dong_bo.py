"""Checkpoint với dữ liệu tổng hợp: không gọi mạng hoặc thay đổi sổ nghiệp vụ."""

import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from may_chu import UngDung
from thu_tich_hop_vn import KEY, OWNER, FakeTransport
from vn_dong_bo import DongBoVietNam
from vn_transport import LoiTichHop


class ThuDongBo(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        key = root / "vault.key"
        key.write_bytes(os.urandom(32))
        env = patch.dict(os.environ, {"BDSG_INTEGRATION_VAULT_KEY_FILE": str(key)})
        env.start()
        self.addCleanup(env.stop)
        self.app = UngDung(root / "data", "https://test.example", True)
        self.app.kho.tao_chu("mat-khau-chi-dung-trong-test")
        self.addCleanup(self.app.core.audit.close)
        self.addCleanup(self.app.tasks.close)
        self.transport = FakeTransport(
            {"products": [{"id": "1", "title": "Hang tong hop"}]}
        )
        self.app.vn_integrations.transport = self.transport
        self.sync = self.app.vn_sync
        self.connection = self.app.vn_integrations.save(
            OWNER,
            {
                "provider": "sapo_web",
                "label": "Cua hang tong hop",
                "settings": {"store": "shop-thu"},
                "credentials": {"access_token": KEY},
                "operations": ["products"],
            },
        )

    def create(self, **fields):
        return self.sync.create(
            OWNER,
            {
                "connection_id": self.connection["id"],
                "operation": "products",
                "label": "Danh muc thu",
                "arguments": {"limit": 1},
                "request_key": "create-request-001",
                **fields,
            },
        )

    def step(self, job):
        return self.sync.step(OWNER, {"id": job["id"]})

    def test_create_is_idempotent_and_does_not_call_provider(self):
        job = self.create()
        self.assertEqual(self.create()["id"], job["id"])
        self.assertEqual(self.transport.calls, [])
        with self.assertRaises(LoiTichHop):
            self.create(label="Khac")
        with self.assertRaises(LoiTichHop):
            self.create(arguments={"url": "https://test.example", "access_token": KEY})
        self.assertNotIn(KEY, str(self.sync.list(OWNER)))
        self.assertNotIn("arguments", job)

    def test_two_pages_checkpoint_restart_and_completed_never_calls_again(self):
        job = self.create()
        progress = self.step(job)
        self.assertEqual(
            (progress["state"], progress["pages"], progress["records"]), ("ready", 1, 1)
        )
        self.assertIn("page=1", self.transport.calls[0][2])
        self.sync = DongBoVietNam(self.app.vn_integrations)
        self.transport.data = {"products": []}
        done = self.step(job)
        self.assertEqual((done["state"], done["pages"]), ("completed", 2))
        self.assertIn("page=2", self.transport.calls[1][2])
        self.step(job)
        self.assertEqual(len(self.transport.calls), 2)
        snapshot = self.sync.page(OWNER, {"id": job["id"], "page": 1})
        self.assertEqual(snapshot["items"][0]["id"], "1")
        self.assertFalse(snapshot["external_write_performed"])

    def test_failed_page_keeps_checkpoint_and_requires_explicit_resume(self):
        job = self.create()
        self.step(job)
        self.transport.error = LoiTichHop("provider_unavailable")
        with self.assertRaises(LoiTichHop):
            self.step(job)
        current = self.sync.list(OWNER)["jobs"][0]
        self.assertEqual((current["state"], current["pages"]), ("paused", 1))
        with self.assertRaises(LoiTichHop):
            self.step(job)
        self.transport.error = None
        self.transport.data = {"products": []}
        self.sync.control(OWNER, {"id": job["id"], "action": "resume"})
        self.assertEqual(self.step(job)["state"], "completed")
        self.assertEqual(self.transport.calls[-1][2], self.transport.calls[-2][2])

    def test_retry_after_is_observed_before_resume(self):
        job = self.create()
        self.transport.error = LoiTichHop("rate_limited", 3600)
        with self.assertRaises(LoiTichHop):
            self.step(job)
        with self.assertRaises(LoiTichHop) as failure:
            self.sync.control(OWNER, {"id": job["id"], "action": "resume"})
        self.assertEqual(failure.exception.code, "rate_limited")
        self.assertGreaterEqual(failure.exception.retry_after, 3599)

    def test_revision_change_denies_old_snapshot_and_further_reads(self):
        job = self.create()
        self.step(job)
        self.app.vn_integrations.disconnect(
            OWNER, {"id": self.connection["id"], "expected_revision": 1}
        )
        for action in (
            lambda: self.step(job),
            lambda: self.sync.page(OWNER, {"id": job["id"], "page": 1}),
        ):
            with self.assertRaises(LoiTichHop):
                action()
        self.assertEqual(len(self.transport.calls), 1)

    def test_cancel_while_network_is_running_discards_checkpoint(self):
        job = self.create()
        self.transport.started, self.transport.release = (
            threading.Event(),
            threading.Event(),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.step, job)
            self.assertTrue(self.transport.started.wait(3))
            with self.assertRaises(LoiTichHop):
                self.step(job)
            cancelled = self.sync.control(OWNER, {"id": job["id"], "action": "cancel"})
            self.assertEqual(cancelled["state"], "cancelled")
            self.transport.release.set()
            with self.assertRaises(LoiTichHop):
                future.result(timeout=5)
        current = self.sync.list(OWNER)["jobs"][0]
        self.assertEqual((current["state"], current["pages"]), ("cancelled", 0))

    def test_interrupted_claim_is_paused_after_restart_without_network(self):
        job = self.create()
        with self.app.kho.ket_noi() as db:
            db.execute(
                "UPDATE vn_sync_jobs SET state='running' WHERE id=?", (job["id"],)
            )
        restarted = DongBoVietNam(self.app.vn_integrations)
        current = restarted.list(OWNER)["jobs"][0]
        self.assertEqual(
            (current["state"], current["error_code"]), ("paused", "interrupted")
        )
        self.assertEqual(self.transport.calls, [])

    def test_page_limit_cannot_be_bypassed_by_resume(self):
        job = self.create(max_pages=1)
        current = self.step(job)
        self.assertEqual(
            (current["state"], current["error_code"]), ("paused", "page_limit")
        )
        with self.assertRaises(LoiTichHop):
            self.sync.control(OWNER, {"id": job["id"], "action": "resume"})
        self.assertEqual(len(self.transport.calls), 1)

    def test_other_owner_and_operator_cannot_access_jobs(self):
        job = self.create()
        for actor in (
            {"id": "other", "role": "quan-tri"},
            {"id": OWNER["id"], "role": "van-hanh"},
        ):
            with self.assertRaises(PermissionError):
                self.sync.step(actor, {"id": job["id"]})
            with self.assertRaises(PermissionError):
                self.sync.page(actor, {"id": job["id"], "page": 1})
        self.assertEqual(self.transport.calls, [])

    def test_request_revision_is_checked_before_transport(self):
        with self.assertRaises(LoiTichHop):
            self.app.vn_integrations.read(
                OWNER,
                {
                    "id": self.connection["id"],
                    "operation": "products",
                    "arguments": {},
                    "request_key": "wrong-revision-001",
                    "expected_revision": 2,
                },
            )
        self.assertEqual(self.transport.calls, [])

    def test_expired_connection_denies_snapshot(self):
        self.app.vn_integrations.clock = lambda: 1000
        self.connection = self.app.vn_integrations.save(OWNER, {
            "id": self.connection["id"], "expected_revision": 1,
            "provider": "sapo_web", "label": "Co han", "settings": {"store": "shop-thu"},
            "operations": ["products"], "expires_at": 2000,
        })
        self.sync.clock = lambda: 1000
        job = self.create()
        self.step(job)
        self.sync.clock = lambda: 3000
        with self.assertRaises(LoiTichHop) as failure:
            self.sync.page(OWNER, {"id": job["id"], "page": 1})
        self.assertEqual(failure.exception.code, "authorization_required")

    def test_cycle_and_size_limit_never_commit_partial_page(self):
        job = self.create()
        original = self.app.vn_integrations.read
        def loop(*args):
            return {**original(*args), "next_arguments": {"limit": 1}}
        with patch.object(self.app.vn_integrations, "read", side_effect=loop):
            with self.assertRaises(LoiTichHop):
                self.step(job)
        self.assertEqual(self.sync.list(OWNER)["jobs"][0]["pages"], 0)
        second = self.create(request_key="create-request-002")
        with patch.object(self.sync, "MAX_BYTES", 1):
            with self.assertRaises(LoiTichHop):
                self.step(second)
        with self.app.kho.ket_noi() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM vn_sync_pages").fetchone()[0], 0)

    def test_kernel_checks_write_gate_and_operator_permission(self):
        token = self.app.kho.tao_agent("operator-sync", "Operator", "operator")
        actor = self.app.kho.tu_token(token)
        for tool in ("dong_bo_danh_sach", "dong_bo_tao", "dong_bo_buoc", "dong_bo_trang", "dong_bo_dieu_khien"):
            self.assertFalse(self.app.core.goi(actor, "tich_hop_vn." + tool, {})["ok"])
        closed = UngDung(self.app.kho.root.parent / "closed", "https://test.example", False)
        closed.kho.tao_chu("mat-khau-chi-dung-trong-test")
        try:
            self.assertFalse(closed.core.goi(OWNER, "tich_hop_vn.dong_bo_tao", {})["ok"])
            self.assertFalse(closed.core.goi(OWNER, "tich_hop_vn.dong_bo_buoc", {})["ok"])
        finally:
            closed.tasks.close()
            closed.core.audit.close()


if __name__ == "__main__":
    unittest.main()
