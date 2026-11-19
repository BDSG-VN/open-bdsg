"""Kiểm tác vụ bền vững, quyền sở hữu và dừng hợp tác trên dữ liệu tạm."""
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from cong_viec import CongViec
from kho import Kho
from mo_hinh_bdsg import MoHinhBDSG


OWNER = {"id": "chu-quan", "name": "Chu", "role": "quan-tri"}
A = {"id": "operator-a", "name": "A", "role": "operator"}
B = {"id": "operator-b", "name": "B", "role": "operator"}


class MoHinhTat:
    configured = False
    configuration_error = ""
    module_read_tools = staticmethod(MoHinhBDSG.module_read_tools)

    def public_status(self):
        return {"configured": False, "mode": "quy-trinh", "model": None}


class NhanThu:
    catalogue = [
        {"id": "bdsg_crm", "name": "BDSG CRM", "url": "https://crm.bdsg.vn/", "group": "Vận hành", "purpose": "Quan hệ khách hàng"},
        {"id": "bdsg_land", "name": "BDSG LAND", "url": "https://bdsgland.bdsg.vn/", "group": "Bất động sản", "purpose": "Dịch vụ bất động sản"},
    ]

    def __init__(self):
        self.calls = []
        self.block = None
        self.entered = threading.Event()

    def goi(self, actor, name, arguments):
        self.calls.append((actor["id"], name, arguments))
        if self.block and name == "nen_tang.danh_sach":
            self.entered.set()
            if not self.block.wait(4):
                raise RuntimeError("test wait exceeded")
        if name == "nen_tang.danh_sach":
            return {"ok": True, "ket_qua": {"products": self.catalogue}}
        if name == "nen_tang.ket_noi":
            return {"ok": True, "ket_qua": {"connections": [{"platform_id": "bdsg_crm", "state": "da-khai-bao", "read_tools": ["crm.list"], "write_tools": []}]}}
        raise AssertionError("Không được gọi công cụ khác")


class ThuCongViec(unittest.TestCase):
    def test_module_reads_require_explicit_owner_model_and_verified_scope(self):
        for value in ["true", 1, None]:
            with self.assertRaises(ValueError):
                self.create(actor=OWNER, module_ids=["bdsg_crm"], allow_module_reads=value)
        with self.assertRaises(PermissionError):
            self.create(allow_module_reads=True, module_ids=["bdsg_crm"])
        with self.assertRaises(ValueError):
            self.create(actor=OWNER, allow_module_reads=True, module_ids=["bdsg_crm"])
        self.tasks.model.configured = True
        with self.assertRaises(ValueError):
            self.create(actor=OWNER, allow_module_reads=True)
        with self.assertRaises(ValueError):
            self.create(actor=OWNER, allow_module_reads=True, module_ids=["bdsg_crm"])

    def test_module_read_snapshot_persists_and_followup_does_not_expand(self):
        self.core.connections = SimpleNamespace(config=[{"platform_id": "bdsg_crm", "state": "da-xac-minh", "read_tools": ["crm.list"]}])
        self.tasks.model.configured = True
        self.tasks.model.run = lambda *a: "# Dữ liệu công cụ giả"
        task_id = self.create(actor=OWNER, allow_module_reads=True, module_ids=["bdsg_crm"])
        original = self.completed(OWNER, task_id)
        self.assertTrue(original["allow_module_reads"])
        self.assertEqual(original["allowed_module_tools"], {"bdsg_crm": ["crm.list"]})
        self.core.connections.config[0]["read_tools"].append("crm.new")
        self.tasks.followup(OWNER, task_id, "Bổ sung báo cáo từ mô-đun đã chọn")
        continued = self.completed(OWNER, task_id)
        self.assertEqual(continued["allowed_module_tools"], original["allowed_module_tools"])
        self.assertTrue(self.tasks.list(OWNER)["tasks"][0]["allow_module_reads"])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.kho = Kho(self.tmp.name)
        self.core = NhanThu()
        self.model_patch = patch("cong_viec.MoHinhBDSG", MoHinhTat)
        self.model_patch.start()
        self.addCleanup(self.model_patch.stop)
        self.tasks = CongViec(self.kho, self.core)
        self.addCleanup(self.close)

    def close(self):
        if self.core.block:
            self.core.block.set()
        self.tasks.close()
        self.tmp.cleanup()

    def create(self, actor=A, **args):
        return self.tasks.create(actor, {"prompt": "Đề xuất triển khai bất động sản Thanh Hoá", "template": "de-xuat-giai-phap", **args})["id"]

    def completed(self, actor, task_id):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            task = self.tasks.detail(actor, task_id)
            if task["status"] in ("completed", "cancelled", "failed"):
                return task
            time.sleep(0.01)
        self.fail("Tác vụ chưa kết thúc trong giới hạn")

    def test_owner_scope_and_read_only_execution(self):
        task_id = self.create(module_ids=["bdsg_land"])
        task = self.completed(A, task_id)
        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["mode"], "quy-trinh")
        self.assertEqual(len(task["steps"]), 3)
        self.assertTrue(all(s["finished"] >= s["started"] for s in task["steps"]))
        self.assertIn("BDSG LAND", task["artifacts"][0]["content"])
        self.assertIn("Chưa cấu hình", task["artifacts"][0]["content"])
        self.assertNotIn("BDSG CRM", task["artifacts"][0]["content"])
        self.assertEqual({c[1] for c in self.core.calls}, {"nen_tang.danh_sach", "nen_tang.ket_noi"})
        self.assertEqual(self.tasks.list(B)["tasks"], [])
        for operation in (lambda: self.tasks.detail(B, task_id), lambda: self.tasks.cancel(B, task_id), lambda: self.tasks.followup(B, task_id, "Bổ sung nội dung thử nghiệm")):
            with self.assertRaises(ValueError):
                operation()
        self.assertEqual(self.tasks.detail(OWNER, task_id)["owner"], A["id"])

    def test_module_validation_and_public_metadata(self):
        with self.assertRaises(ValueError):
            self.create(module_ids=["khong-ton-tai"])
        with self.assertRaises(ValueError):
            self.create(module_ids=["bdsg_crm", "bdsg_crm"])
        with self.assertRaises(PermissionError):
            self.create(actor={"id": "agent-a", "role": "agent"})
        public = self.tasks.modules(None)["modules"]
        self.assertTrue(all(p["mcp"]["state"] == "can-xac-thuc" for p in public))
        self.assertNotIn("crm.list", json.dumps(public))
        private = self.tasks.modules(A)["modules"]
        self.assertEqual(private[0]["kind"], "mcp-declared")
        self.assertEqual(private[0]["mcp"]["read_tools"], ["crm.list"])

    def test_cooperative_cancel_stops_next_tool(self):
        self.core.block = threading.Event()
        task_id = self.create()
        self.assertTrue(self.core.entered.wait(3))
        self.assertEqual(self.tasks.cancel(A, task_id)["status"], "cancelling")
        self.core.block.set()
        task = self.completed(A, task_id)
        self.assertEqual(task["status"], "cancelled")
        self.assertEqual([c[1] for c in self.core.calls], ["nen_tang.danh_sach"])
        self.assertEqual(task["artifacts"], [])

    def test_followup_keeps_original_result_and_adds_context(self):
        task_id = self.create(module_ids=["bdsg_land"])
        original = self.completed(A, task_id)
        artifact_id = original["artifacts"][0]["id"]
        self.tasks.followup(A, task_id, "Bổ sung phần tiếp cận khách hàng tại Thanh Hoá")
        task = self.completed(A, task_id)
        self.assertEqual(task["run"], 2)
        self.assertEqual(task["artifacts"][0]["id"], artifact_id)
        self.assertEqual(len(task["artifacts"]), 2)
        self.assertIn("Bổ sung phần tiếp cận", task["artifacts"][-1]["content"])
        self.assertEqual(len([m for m in task["messages"] if m["role"] == "user"]), 2)

    def test_cancel_during_report_does_not_publish_late_result(self):
        entered, release = threading.Event(), threading.Event()
        original = self.tasks._report

        def delayed(*args):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test wait exceeded")
            return original(*args)

        with patch.object(self.tasks, "_report", side_effect=delayed):
            task_id = self.create()
            try:
                self.assertTrue(entered.wait(3))
                self.tasks.cancel(A, task_id)
            finally:
                release.set()
            task = self.completed(A, task_id)
        self.assertEqual(task["status"], "cancelled")
        self.assertEqual(task["artifacts"], [])
        self.assertFalse(any(m["role"] == "assistant" for m in task["messages"]))

    def test_revocation_during_report_does_not_publish_late_result(self):
        entered, release = threading.Event(), threading.Event()
        active = {"value": True}
        self.core.verify_actor = lambda actor: active["value"]
        original = self.tasks._report

        def delayed(*args):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test wait exceeded")
            return original(*args)

        with patch.object(self.tasks, "_report", side_effect=delayed):
            task_id = self.create()
            try:
                self.assertTrue(entered.wait(3))
                active["value"] = False
            finally:
                release.set()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                with self.tasks.lock:
                    task = self.tasks._load(task_id)
                if task["status"] in ("completed", "failed", "cancelled"):
                    break
                time.sleep(0.01)
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["artifacts"], [])

    def test_restart_preserves_results_without_replaying(self):
        task_id = self.create()
        original = self.completed(A, task_id)
        self.tasks.close()
        before = len(self.core.calls)
        with self.kho.ket_noi() as db:
            task = {**original, "status": "running"}
            db.execute("UPDATE cong_viec_tasks SET status='running',document=? WHERE id=?", (json.dumps(task), task_id))
        self.tasks = CongViec(self.kho, self.core)
        reopened = self.tasks.detail(A, task_id)
        self.assertEqual(reopened["status"], "interrupted")
        self.assertEqual(reopened["artifacts"], original["artifacts"])
        self.assertEqual(len(self.core.calls), before)

    def test_model_result_or_failure_never_fake_fallback(self):
        class MoHinhThu:
            configured = True
            configuration_error = ""
            fail = False

            def public_status(self):
                return {"configured": True, "mode": "mo-hinh-bdsg", "model": "model-thu"}

            def run(self, prompt, context, core, actor, on_event, cancelled):
                self.context = context
                if self.fail:
                    raise RuntimeError("loi-bi-mat-khong-duoc-lo")
                on_event("model_test", "Đã chạy mô hình thử")
                return "# Kết quả từ API mô hình thử"

        self.tasks.model = MoHinhThu()
        task_id = self.create(module_ids=["bdsg_land"])
        task = self.completed(A, task_id)
        self.assertEqual(task["mode"], "mo-hinh-bdsg")
        self.assertEqual(task["artifacts"][0]["content"], "# Kết quả từ API mô hình thử")
        self.assertEqual(self.tasks.model.context["products"][0]["id"], "bdsg_land")
        self.tasks.model.fail = True
        failed = self.completed(A, self.create())
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["artifacts"], [])
        self.assertNotIn("loi-bi-mat", json.dumps(failed))


if __name__ == "__main__":
    unittest.main()
