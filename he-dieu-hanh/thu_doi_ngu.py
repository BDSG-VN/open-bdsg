"""Kiểm điều phối bằng mô hình tổng hợp; không tuyên bố đã gọi nhà cung cấp AI."""

import copy
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from cong_viec import CongViec
from doi_ngu import DoiNgu
from kho import Kho
from mo_hinh_bdsg import LoiMoHinhBDSG
from nhan_su import NhanSu
from thu_cong_viec import A, B, MoHinhTat, NhanThu


def assignment(skill_id, dependencies=None):
    return {
        "skill_id": skill_id,
        "mission": "Phân tích dữ liệu tổng hợp được cấp",
        "deliverable": "Báo cáo có bằng chứng kiểm được",
        "depends_on": dependencies or [],
    }


class ThuDoiNgu(unittest.TestCase):
    def setUp(self):
        self.registry = NhanSu()
        self.engine = DoiNgu(self.registry)
        self.events = []
        self.event_lock = threading.Lock()

    def emit(self, kind, message, **extra):
        with self.event_lock:
            self.events.append((kind, message, extra))

    def plan(self, nodes):
        return json.dumps(
            {"summary": "Phân công từ dữ liệu tổng hợp", "assignments": nodes}
        )

    def test_catalogue_has_independent_hashes_and_no_permission_grant(self):
        catalogue = self.registry.catalogue()
        self.assertGreaterEqual(len(catalogue["agents"]), 24)
        self.assertFalse(catalogue["grants_permissions"])
        self.assertEqual(
            len({s["sha256"] for s in catalogue["agents"]}), len(catalogue["agents"])
        )
        changed = self.registry.detail("bdsg-ban-hang")
        changed["sources"].clear()
        self.assertTrue(self.registry.detail("bdsg-ban-hang")["sources"])

    def test_altered_skill_is_rejected_at_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {
                "schema": 1,
                "version": "test",
                "locale": "vi-VN",
                "skills": [
                    {
                        "id": "bdsg-thu",
                        "sha256": "0" * 64,
                        "sources": [{"repository": "test/source"}],
                    }
                ],
            }
            (root / "catalog.json").write_text(json.dumps(manifest), encoding="utf-8")
            target = root / "skills/bdsg-thu"
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text(
                "---\nname: bdsg-thu\n---\nTampered", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                NhanSu(root)

    def test_unknown_duplicate_cycle_and_extra_permissions_are_rejected(self):
        cases = [
            [assignment("unapproved")],
            [assignment("bdsg-ban-hang"), assignment("bdsg-ban-hang")],
            [
                assignment("bdsg-ban-hang", ["bdsg-marketing"]),
                assignment("bdsg-marketing"),
            ],
            [{**assignment("bdsg-ban-hang"), "sudo": True}],
            [assignment("bdsg-ban-hang", ["bdsg-ban-hang"])],
            [],
        ]
        for nodes in cases:
            with self.subTest(nodes=nodes), self.assertRaises(LoiMoHinhBDSG):
                self.engine.validate_plan(self.plan(nodes))

    def test_parallel_specialists_then_handoff_and_final_synthesis(self):
        rendezvous = threading.Barrier(2)
        calls = []
        lock = threading.Lock()
        nodes = [
            assignment("bdsg-nghien-cuu"),
            assignment("bdsg-tai-chinh"),
            assignment("bdsg-chien-luoc", ["bdsg-nghien-cuu", "bdsg-tai-chinh"]),
        ]

        def call(prompt, context, on_event, cancelled):
            with lock:
                calls.append(copy.deepcopy(context))
            if "workforce_catalogue" in context:
                return self.plan(nodes)
            if "workforce_results" in context:
                self.assertEqual(len(context["workforce_results"]), 3)
                return "# Sản phẩm tổng hợp từ ba kết quả thật trong bài kiểm"
            worker = context["assignment"]
            self.assertFalse(context["execution_scope"]["delegation"])
            if worker["skill_id"] == "bdsg-chien-luoc":
                self.assertEqual(len(worker["handoffs"]), 2)
            else:
                self.assertEqual(worker["handoffs"], {})
                rendezvous.wait(timeout=3)
            on_event(
                "model-usage",
                "Dữ liệu kiểm tổng hợp",
                input_tokens=10,
                output_tokens=20,
            )
            return "# Kết quả tổng hợp " + worker["skill_id"]

        answer = self.engine.run(
            "Lập phương án kinh doanh có nghiên cứu và tài chính",
            {"execution_scope": {"delegation": True, "python": False}},
            call,
            self.emit,
            lambda: False,
        )
        self.assertIn("Sản phẩm tổng hợp", answer)
        self.assertEqual(len(calls), 5)
        team = [e[2]["team"] for e in self.events if e[0] == "team-state"][-1]
        self.assertEqual(team["state"], "completed")
        self.assertTrue(
            all(
                node["state"] == "completed" and node["output"]
                for node in team["agents"]
            )
        )

    def test_single_specialist_does_not_spawn_unneeded_roles(self):
        count = []

        def call(prompt, context, on_event, cancelled):
            count.append(context)
            if "workforce_catalogue" in context:
                return self.plan([assignment("bdsg-bien-ban")])
            return "# Biên bản từ dữ liệu tổng hợp"

        self.engine.run("Tóm tắt cuộc họp", {}, call, self.emit, lambda: False)
        self.assertEqual(len(count), 3)

    def test_cancel_after_planning_never_starts_specialist(self):
        stop = threading.Event()
        calls = []

        def call(*args):
            calls.append(args)
            stop.set()
            return self.plan([assignment("bdsg-ban-hang")])

        with self.assertRaises(LoiMoHinhBDSG):
            self.engine.run("Chuẩn bị bán hàng", {}, call, self.emit, stop.is_set)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.events[-1][2]["team"]["state"], "cancelled")

    def test_failed_dependency_blocks_downstream_and_no_synthesis(self):
        calls = []

        def call(prompt, context, on_event, cancelled):
            calls.append(context)
            if "workforce_catalogue" in context:
                return self.plan(
                    [
                        assignment("bdsg-nghien-cuu"),
                        assignment("bdsg-ban-hang", ["bdsg-nghien-cuu"]),
                    ]
                )
            raise LoiMoHinhBDSG("Lỗi mô hình tổng hợp trong bài kiểm")

        with self.assertRaises(LoiMoHinhBDSG):
            self.engine.run(
                "Nghiên cứu rồi soạn kịch bản bán hàng",
                {},
                call,
                self.emit,
                lambda: False,
            )
        team = self.events[-1][2]["team"]
        self.assertEqual([n["state"] for n in team["agents"]], ["failed", "blocked"])
        self.assertEqual(len(calls), 2)

    def test_oversized_specialist_output_is_not_silently_truncated(self):
        def call(prompt, context, on_event, cancelled):
            if "workforce_catalogue" in context:
                return self.plan([assignment("bdsg-bien-ban")])
            return "x" * (self.engine.MAX_OUTPUT_BYTES + 1)

        with self.assertRaises(LoiMoHinhBDSG):
            self.engine.run("Tóm tắt tài liệu", {}, call, self.emit, lambda: False)
        self.assertEqual(self.events[-1][2]["team"]["state"], "failed")


class ThuDoiNguTrongTacVu(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kho = Kho(self.temp.name)
        self.core = NhanThu()
        self.tasks = CongViec(self.kho, self.core)
        self.tasks.model = MoHinhTat()
        self.addCleanup(self.tasks.close)

    def finish(self, identifier):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            task = self.tasks.detail(A, identifier)
            if task["status"] in ("completed", "failed", "cancelled"):
                return task
            time.sleep(0.01)
        self.fail("Đội ngũ chưa kết thúc trong bài kiểm tổng hợp")

    def create(self):
        return self.tasks.create(
            A,
            {
                "prompt": "Soạn biên bản từ nội dung cuộc họp tổng hợp",
                "template": "nhan-su-chuyen-mon",
            },
        )["id"]

    def test_without_model_never_marks_specialist_work_completed(self):
        task = self.finish(self.create())
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["team"]["state"], "awaiting_model")
        self.assertEqual(task["artifacts"], [])

    def test_persists_specialist_output_usage_acl_and_previous_run(self):
        class SyntheticModel(MoHinhTat):
            configured = True

            def run(model_self, prompt, context, core, actor, event, cancelled):
                event("model-reserve", "Lượt tổng hợp trong kiểm thử")
                event(
                    "model-usage",
                    "Mức sử dụng tổng hợp",
                    input_tokens=10,
                    output_tokens=20,
                )
                if "workforce_catalogue" in context:
                    return json.dumps(
                        {
                            "summary": "Một chuyên môn soạn biên bản",
                            "assignments": [assignment("bdsg-bien-ban")],
                        }
                    )
                return "# Biên bản từ dữ liệu tổng hợp"

        self.tasks.model = SyntheticModel()
        identifier = self.create()
        task = self.finish(identifier)
        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["team"]["state"], "completed")
        self.assertEqual(task["usage"]["requests"], 3)
        self.assertEqual(len(task["artifacts"]), 2)
        self.assertIn("skill_sha256", task["team"]["agents"][0])
        self.assertTrue(all("team" not in e for e in task["events"]))
        with self.assertRaises(ValueError):
            self.tasks.detail(B, identifier)
        self.tasks.followup(A, identifier, "Bổ sung bảng theo dõi quyết định cuộc họp")
        task = self.finish(identifier)
        self.assertEqual(task["team"]["run"], 2)
        self.assertEqual(task["team_history"][0]["run"], 1)
        self.assertEqual(len(task["artifacts"]), 4)
        self.tasks.close()
        task["status"] = "running"
        task["team"]["state"] = "working"
        task["team"]["agents"][0]["state"] = "running"
        self.tasks._save(task)
        restarted = CongViec(self.kho, self.core)
        try:
            recovered = restarted.detail(A, identifier)
            self.assertEqual(recovered["status"], "interrupted")
            self.assertEqual(recovered["team"]["state"], "interrupted")
            self.assertEqual(recovered["team"]["agents"][0]["state"], "interrupted")
        finally:
            restarted.close()


if __name__ == "__main__":
    unittest.main()
