"""Kiểm điều phối bằng mô hình tổng hợp; không tuyên bố đã gọi nhà cung cấp AI."""

import base64
import copy
import hashlib
import io
import json
import tempfile
import threading
import time
import unittest
import zipfile
from concurrent.futures import ALL_COMPLETED
from concurrent.futures import wait as real_wait
from pathlib import Path
from unittest.mock import patch

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
            len(
                {
                    source["repository"]
                    for agent in catalogue["agents"]
                    for source in agent["sources"]
                }
            ),
            36,
        )
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

    def test_portable_bundles_keep_skill_hashes_licenses_and_no_private_files(self):
        for format_id, prefix in (
            ("portable", "skills/"),
            ("codex", ".agents/skills/"),
            ("claude", "skills/"),
        ):
            with self.subTest(format=format_id):
                result = self.registry.export_bundle({"format": format_id})
                raw = base64.b64decode(result["content_base64"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), result["sha256"])
                self.assertEqual(
                    result["sha256"],
                    self.registry.export_bundle({"format": format_id})["sha256"],
                )
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    names = archive.namelist()
                    self.assertFalse(
                        any(
                            ".." in Path(name).parts
                            or name.endswith((".env", ".key", ".db", ".py", ".sh"))
                            for name in names
                        )
                    )
                    self.assertTrue(
                        any(
                            name.startswith("third_party/") and "LICENSE" in name
                            for name in names
                        )
                    )
                    for item in self.registry.skills.values():
                        self.assertEqual(
                            hashlib.sha256(
                                archive.read(prefix + item["id"] + "/SKILL.md")
                            ).hexdigest(),
                            item["sha256"],
                        )
                    if format_id == "portable":
                        self.assertIn(
                            "$schema", json.loads(archive.read("plugin.json"))
                        )
                    if format_id == "claude":
                        self.assertIn(prefix + "bdsg-agent-tong/SKILL.md", names)
                        self.assertEqual(
                            len(
                                json.loads(
                                    archive.read(
                                        prefix
                                        + "bdsg-agent-tong/references/catalog.json"
                                    )
                                )
                            ),
                            len(self.registry.skills),
                        )
                        identifier = "bdsg-ban-hang"
                        with zipfile.ZipFile(
                            io.BytesIO(
                                archive.read("individual/" + identifier + ".zip")
                            )
                        ) as individual:
                            self.assertIn(
                                identifier + "/SKILL.md", individual.namelist()
                            )
                            self.assertTrue(
                                any(
                                    "third_party/" in name
                                    for name in individual.namelist()
                                )
                            )
        with self.assertRaises(ValueError):
            self.registry.export_bundle({"format": "../../private"})
        with self.assertRaises(ValueError):
            self.registry._zip({"../outside": b"test"})

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

    def test_finished_success_is_preserved_when_same_batch_also_fails(self):
        rendezvous = threading.Barrier(2)

        def call(prompt, context, on_event, cancelled):
            if "workforce_catalogue" in context:
                return self.plan(
                    [assignment("bdsg-ban-hang"), assignment("bdsg-marketing")]
                )
            rendezvous.wait(timeout=3)
            if context["assignment"]["skill_id"] == "bdsg-marketing":
                raise LoiMoHinhBDSG("Lỗi mô hình tổng hợp có chủ đích")
            return "Kết quả bán hàng đã hoàn tất"

        def failure_first(futures, **kwargs):
            done, pending = real_wait(futures, timeout=3, return_when=ALL_COMPLETED)
            self.assertFalse(pending)
            return sorted(done, key=lambda future: future.exception() is None), pending

        with patch("doi_ngu.wait", failure_first), self.assertRaises(LoiMoHinhBDSG):
            self.engine.run("Hai phần việc độc lập", {}, call, self.emit, lambda: False)
        team = [e[2]["team"] for e in self.events if e[0] == "team-state"][-1]
        nodes = {node["skill_id"]: node for node in team["agents"]}
        self.assertEqual(nodes["bdsg-ban-hang"]["state"], "completed")
        self.assertEqual(
            nodes["bdsg-ban-hang"]["output"], "Kết quả bán hàng đã hoàn tất"
        )
        self.assertEqual(nodes["bdsg-marketing"]["state"], "failed")

    def test_planner_receives_bounded_authorized_document_and_previous_result(self):
        context = {
            "documents": [
                {
                    "id": "doc-test",
                    "name": "hop-dong.txt",
                    "version": 1,
                    "sha256": "a" * 64,
                    "text": "Hợp đồng xây dựng. " * 2000,
                    "truncated": False,
                }
            ],
            "previous_artifacts": ["Báo cáo trước: " + "đ" * 10000],
            "execution_scope": {"python": True},
        }
        original = copy.deepcopy(context)

        def call(prompt, supplied, on_event, cancelled):
            if "workforce_catalogue" in supplied:
                doc = supplied["documents"][0]
                self.assertEqual(doc["id"], "doc-test")
                self.assertTrue(doc["text"].startswith("Hợp đồng"))
                self.assertTrue(doc["truncated"])
                self.assertLessEqual(len(doc["text"].encode()), 2000)
                self.assertTrue(
                    supplied["previous_artifacts"][0]["text"].startswith(
                        "Báo cáo trước"
                    )
                )
                self.assertTrue(supplied["previous_artifacts"][0]["truncated"])
                self.assertLess(
                    len(json.dumps(supplied, ensure_ascii=False).encode()), 48000
                )
                self.assertEqual(supplied["execution_scope"], {})
                return self.plan([assignment("bdsg-nghien-cuu")])
            return "Kết quả kiểm từ dữ liệu tổng hợp"

        self.engine.run(
            "Tiếp tục phân tích tài liệu đã chọn",
            context,
            call,
            self.emit,
            lambda: False,
        )
        self.assertEqual(context, original)

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

    def test_finished_handoff_is_retained_when_downstream_fails(self):
        class SyntheticFailure(MoHinhTat):
            configured = True

            def run(model_self, prompt, context, core, actor, event, cancelled):
                if "workforce_catalogue" in context:
                    return json.dumps(
                        {
                            "summary": "Nghiên cứu trước bán hàng",
                            "assignments": [
                                assignment("bdsg-nghien-cuu"),
                                assignment("bdsg-ban-hang", ["bdsg-nghien-cuu"]),
                            ],
                        }
                    )
                if context["assignment"]["skill_id"] == "bdsg-nghien-cuu":
                    return "# Bàn giao nghiên cứu đã tạo trong bài kiểm tổng hợp"
                raise LoiMoHinhBDSG("Lỗi có chủ đích sau bàn giao")

        self.tasks.model = SyntheticFailure()
        task = self.finish(self.create())
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["team"]["state"], "failed")
        self.assertEqual(len(task["artifacts"]), 1)
        self.assertTrue(task["artifacts"][0]["name"].startswith("bdsg-nghien-cuu-"))
        self.assertIn("Bàn giao nghiên cứu", task["artifacts"][0]["content"])


if __name__ == "__main__":
    unittest.main()
