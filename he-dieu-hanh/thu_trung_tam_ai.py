"""Kiểm danh mục và tài trợ AI bằng dữ liệu tổng hợp, không gọi API trả phí."""

import copy
import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from kho import Kho
from may_chu import UngDung
from mo_hinh_bdsg import LoiMoHinhBDSG
from ngan_sach_ai import DEFAULT_POLICY, NganSachAI, validate_policy
from sao_luu_he_thong import backup, restore
from trung_tam_ai import TrungTamAI, MoHinhLiteLLM
from thu_mo_hinh_bdsg import Transport, answer

OWNER = {"id": "test-owner", "name": "Chủ quản kiểm", "role": "quan-tri"}
USER = {"id": "test-user", "name": "Người dùng kiểm", "role": "operator"}


def model(identifier="fast-model", capability="general"):
    return {
        "id": identifier,
        "label": "Mô hình tổng hợp " + identifier,
        "upstream_model": "openai/synthetic-test-model",
        "api_key": "synthetic-key-not-live",
        "capabilities": [capability],
        "skills": [],
        "prices": {"input_per_million": "1", "output_per_million": "3"},
    }


def config():
    return {
        "enabled": True,
        "default_model": "fast-model",
        "models": [model(), model("code-model", "coding")],
        "policy": dict(DEFAULT_POLICY),
    }


class ThuTrungTamAI(unittest.TestCase):
    def test_gateway_omits_sampling_and_matches_reserved_output(self):
        # Claude hiện hành từ chối temperature; alias không bộc lộ nhà cung cấp.
        transport = Transport([answer('Kết quả thật qua transport giả')])
        adapter = MoHinhLiteLLM('claude-test-revision', 'synthetic-key-not-live', opener=transport)
        adapter._request([{'role':'user','content':'Tạo website demo'}], [])
        payload = json.loads(transport.requests[0][0].data)
        self.assertNotIn('temperature', payload)
        self.assertEqual(payload['max_tokens'], MoHinhLiteLLM.MAX_OUTPUT_TOKENS)
        self.assertEqual(payload['max_tokens'], 8192)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.kho = Kho(self.directory.name)
        self.hub = TrungTamAI(self.kho, probe=lambda key, aliases: True)

    def test_disabled_without_credentials_and_does_not_fake_result(self):
        self.assertFalse(self.hub.configured)
        with self.assertRaises(LoiMoHinhBDSG):
            self.hub.choose({})

    def test_only_owner_can_configure_no_keys_in_catalogue_or_admin_result(self):
        with self.assertRaises(PermissionError):
            self.hub.save(USER, config())
        result = self.hub.save(OWNER, config())
        public = json.dumps([result, self.hub.catalogue(), self.hub.public_status()])
        self.assertNotIn("synthetic-key", public)
        self.assertNotIn(self.hub.data["gateway_key"], public)
        self.assertTrue(result["models"][0]["has_api_key"])
        with self.assertRaises(PermissionError):
            self.hub.admin(USER)
        loaded = TrungTamAI(self.kho)
        self.assertTrue(loaded.configured)
        self.assertTrue(loaded.data == self.hub.data)

    def test_config_rejects_unknown_fields_providers_duplicates_and_nan(self):
        for mutate in (
            lambda c: c.update(base_url="https://attacker.invalid"),
            lambda c: c["models"][0].update(upstream_model="custom/unsupported"),
            lambda c: c["models"].append(copy.deepcopy(c["models"][0])),
            lambda c: c["models"][0]["prices"].update(input_per_million="NaN"),
            lambda c: c["policy"].update(tasks_per_user=True),
        ):
            candidate = config()
            mutate(candidate)
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                self.hub.save(OWNER, candidate)
        self.assertFalse(self.hub.path.exists())

    def test_keep_key_only_for_same_upstream_and_proxy_has_revision_alias(self):
        self.hub.save(OWNER, config())
        candidate = self.hub.admin(OWNER)
        payload = {
            key: candidate[key]
            for key in ("enabled", "default_model", "models", "policy")
        }
        for item in payload["models"]:
            item.pop("has_api_key")
        self.hub.save(OWNER, payload)
        payload["models"][0]["upstream_model"] = "anthropic/synthetic-test-model"
        with self.assertRaises(ValueError):
            self.hub.save(OWNER, payload)
        proxy = json.loads(self.hub.proxy_path.read_text(encoding="utf-8"))
        self.assertEqual(
            proxy["model_list"][0]["model_name"],
            "fast-model-" + self.hub.data["revision"],
        )
        self.assertEqual(proxy["router_settings"], {"num_retries": 0, "fallbacks": []})
        self.assertNotIn("callbacks", proxy)

    def test_manual_selection_and_specialist_routing_stay_within_allowlist(self):
        self.hub.save(OWNER, config())
        self.assertEqual(self.hub.choose({})[0]["id"], "fast-model")
        self.assertEqual(
            self.hub.choose({"assignment": {"skill_id": "bdsg-debug"}})[0]["id"],
            "code-model",
        )
        self.assertEqual(
            self.hub.choose(
                {
                    "model_selection": "fast-model",
                    "assignment": {"skill_id": "bdsg-debug"},
                }
            )[0]["id"],
            "fast-model",
        )
        with self.assertRaises(LoiMoHinhBDSG):
            self.hub.choose({"model_selection": "unapproved"})

    def test_failed_private_save_restores_previous_proxy_configuration(self):
        self.hub.save(OWNER, config())
        before = copy.deepcopy(self.hub.data)
        previous = json.loads(self.hub.proxy_path.read_text(encoding="utf-8"))
        original = self.hub._write

        def fail_private(path, data):
            if path == self.hub.path:
                raise OSError("Lỗi đĩa tổng hợp")
            return original(path, data)

        with patch.object(self.hub, "_write", fail_private), self.assertRaises(OSError):
            self.hub.save(OWNER, config())
        self.assertEqual(self.hub.data, before)
        self.assertEqual(
            json.loads(self.hub.proxy_path.read_text(encoding="utf-8")), previous
        )

    def test_backup_restore_keeps_private_models_proxy_and_credits(self):
        self.hub.save(OWNER, config())
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "snapshot"
            restored = Path(directory) / "restored"
            manifest = backup(self.kho.root, bundle)
            self.assertIn("data/ai-models-private.json", manifest["files"])
            self.assertIn("data/litellm-config.json", manifest["files"])
            restore(bundle, restored)
            loaded = TrungTamAI(Kho(restored / "data"))
            self.assertTrue(loaded.data == self.hub.data)

    def test_model_error_does_not_fallback_or_refund_uncertain_spend(self):
        calls, events = [], []

        class Fake:
            def run(inner, prompt, context, core, actor, emit, cancelled):
                emit("model-reserve", "Tổng hợp", input_bytes=1000)
                calls.append(1)
                raise LoiMoHinhBDSG("Lỗi provider tổng hợp")

        self.hub.factory = lambda alias, key: Fake()
        self.hub.save(OWNER, config())
        with self.assertRaises(LoiMoHinhBDSG):
            self.hub.run(
                "Thử tổng hợp", {}, None, USER, lambda *a, **k: events.append((a, k))
            )
        self.assertEqual(len(calls), 1)
        self.assertEqual(events[0][0][0], "model-selected")
        self.assertEqual(self.hub.budget.status(USER, DEFAULT_POLICY)["calls_used"], 1)

    def test_no_request_sent_when_budget_or_input_measurement_missing(self):
        calls = []

        class Fake:
            def run(inner, prompt, context, core, actor, emit, cancelled):
                emit("model-reserve", "Tổng hợp", input_bytes=1000)
                calls.append(1)
                return "Không được tới đây"

        self.hub.factory = lambda alias, key: Fake()
        candidate = config()
        candidate["policy"]["usd_global"] = "0"
        self.hub.save(OWNER, candidate)
        with self.assertRaises(LoiMoHinhBDSG):
            self.hub.run("Thử tổng hợp", {}, None, USER)
        self.assertEqual(calls, [])

    def test_five_daily_tasks_are_atomic_idempotent_and_owner_specific(self):
        budget = NganSachAI(self.kho, clock=lambda: 1000000)
        successes, lock = [], threading.Lock()

        def claim(index):
            try:
                with self.kho.ket_noi() as db:
                    db.execute("BEGIN IMMEDIATE")
                    budget.claim_task(db, USER, "test-" + str(index), 1, DEFAULT_POLICY)
                with lock:
                    successes.append(index)
            except LoiMoHinhBDSG:
                pass

        with ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(claim, range(20)))
        self.assertEqual(len(successes), 5)
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            budget.claim_task(db, USER, "test-" + str(successes[0]), 1, DEFAULT_POLICY)
        self.assertEqual(budget.status(USER, DEFAULT_POLICY)["tasks_used"], 5)
        self.assertEqual(budget.status(OWNER, DEFAULT_POLICY)["tasks_used"], 0)
        budget.clock = lambda: 1000000 + 86400
        self.assertEqual(budget.status(USER, DEFAULT_POLICY)["tasks_remaining"], 5)

    def test_cost_cap_cannot_be_overspent_by_parallel_calls(self):
        budget = NganSachAI(self.kho)
        policy = validate_policy({**DEFAULT_POLICY, "usd_global": "0.005"})
        successful = []

        def reserve(index):
            try:
                budget.reserve(
                    USER,
                    "test",
                    str(index),
                    1000,
                    1000,
                    {"input_per_million": "1", "output_per_million": "3"},
                    policy,
                )
                successful.append(index)
            except LoiMoHinhBDSG:
                pass

        with ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(reserve, range(20)))
        self.assertEqual(len(successful), 1)
        self.assertEqual(budget.status(USER, policy)["usd_reserved"], "0.004")

    def test_midnight_is_vietnam_time_and_missing_usage_remains_reserved(self):
        budget = NganSachAI(self.kho, clock=lambda: 86400 - 25200 - 1)
        self.assertEqual(budget.day(), 0)
        budget.clock = lambda: 86400 - 25200
        self.assertEqual(budget.day(), 1)
        self.assertEqual(
            budget.status(USER, DEFAULT_POLICY)["resets_at_unix"], 2 * 86400 - 25200
        )

    def test_project_and_global_output_caps_apply_across_different_users(self):
        prices = {"input_per_million": "1", "output_per_million": "3"}
        policy = {**DEFAULT_POLICY, "output_tokens_per_project": 4096}
        self.hub.budget.reserve(
            USER, "one", "test", 100, 4096, prices, policy, project_id="same-project"
        )
        with self.assertRaises(LoiMoHinhBDSG):
            self.hub.budget.reserve(
                OWNER,
                "two",
                "test",
                100,
                4096,
                prices,
                policy,
                project_id="same-project",
            )
        self.hub.budget.reserve(
            OWNER, "two", "test", 100, 4096, prices, policy, project_id="other-project"
        )
        with self.assertRaises(LoiMoHinhBDSG):
            self.hub.budget.reserve(
                OWNER,
                "three",
                "test",
                100,
                4096,
                prices,
                {**policy, "output_tokens_global": 8192},
                project_id="third-project",
            )

    def test_switching_from_legacy_does_not_reset_project_output_budget(self):
        with self.kho.ket_noi() as db:
            db.execute(
                "CREATE TABLE model_calls(owner TEXT,created REAL,project_id TEXT,output_reserved INTEGER)"
            )
            db.execute(
                "INSERT INTO model_calls VALUES (?,?,?,?)",
                (OWNER["id"], time.time(), "existing-project", 131072),
            )
        with self.assertRaises(LoiMoHinhBDSG):
            self.hub.budget.reserve(
                USER,
                "test",
                "test",
                100,
                4096,
                {"input_per_million": "1", "output_per_million": "3"},
                DEFAULT_POLICY,
                project_id="existing-project",
            )
        self.assertEqual(
            self.hub.budget.status(OWNER, DEFAULT_POLICY)["output_tokens_reserved"],
            131072,
        )

    def test_backup_blocks_ai_writes_until_database_and_config_are_copied(self):
        import sao_luu_he_thong

        self.hub.save(OWNER, config())
        original_revision = self.hub.data["revision"]
        copying, writer_finished = threading.Event(), threading.Event()
        original_copy = sao_luu_he_thong.private_copy

        def copy_with_barrier(source, target):
            if source.name == "ai-models-private.json":
                copying.set()
                self.assertFalse(
                    writer_finished.wait(0.2),
                    "Writer chen giữa snapshot DB và cấu hình",
                )
            original_copy(source, target)

        def write():
            self.assertTrue(copying.wait(3))
            self.hub.budget.reserve(
                USER,
                "during-backup",
                "test",
                100,
                100,
                {"input_per_million": "1", "output_per_million": "3"},
                DEFAULT_POLICY,
            )
            candidate = config()
            candidate["models"][0]["label"] = "Cấu hình mới sau snapshot"
            self.hub.save(OWNER, candidate)
            writer_finished.set()

        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "snapshot"
            with (
                patch.object(sao_luu_he_thong, "private_copy", copy_with_barrier),
                ThreadPoolExecutor(max_workers=2) as pool,
            ):
                snapshot = pool.submit(backup, self.kho.root, bundle)
                writing = pool.submit(write)
                snapshot.result(timeout=5)
                writing.result(timeout=5)
            restored = Path(directory) / "restore"
            restore(bundle, restored)
            loaded = TrungTamAI(Kho(restored / "data"))
            self.assertEqual(loaded.data["revision"], original_revision)
            self.assertEqual(
                loaded.budget.status(USER, DEFAULT_POLICY)["calls_used"], 0
            )
            self.assertEqual(
                self.hub.budget.status(USER, DEFAULT_POLICY)["calls_used"], 1
            )


class ThuAITrongTacVu(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = UngDung(self.directory.name, "https://thanhhoa.bdsg.vn", True)
        self.app.kho.tao_chu("synthetic-password-not-live")
        self.app.kho.tao_agent(USER["id"], "Người kiểm", USER["role"])
        self.owner = {"id": "chu-quan", "name": "Chủ quản kiểm", "role": "quan-tri"}
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.app.core.audit.close)
        self.addCleanup(self.app.tasks.close)
        self.calls = []
        self.aliases = []
        outer = self

        class Fake:
            def run(inner, prompt, context, core, actor, event, cancelled):
                event("model-reserve", "API tổng hợp", input_bytes=100)
                outer.calls.append(context)
                event(
                    "model-usage", "Usage tổng hợp", input_tokens=10, output_tokens=20
                )
                if "workforce_catalogue" in context:
                    return json.dumps(
                        {
                            "summary": "Phân công kiểm mô hình",
                            "assignments": [
                                {
                                    "skill_id": "bdsg-debug",
                                    "mission": "Kiểm lỗi từ dữ liệu tổng hợp",
                                    "deliverable": "Báo cáo có bằng chứng",
                                    "depends_on": [],
                                    "model_id": "code-model",
                                }
                            ],
                        }
                    )
                return "# Kết quả từ mô hình tổng hợp, chưa phải provider thật"

        def factory(alias, key):
            self.aliases.append(alias)
            return Fake()

        self.app.ai.factory = factory
        self.app.ai.probe = lambda key, aliases: True
        result = self.app.core.goi(self.owner, "mo_hinh.luu", config())
        self.assertTrue(result["ok"], result)

    def finish(self, identifier):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            task = self.app.tasks.detail(USER, identifier)
            if task["status"] in ("completed", "failed", "cancelled"):
                return task
            time.sleep(0.01)
        self.fail("Tác vụ tổng hợp chưa kết thúc")

    def test_five_task_claims_persist_with_tasks_and_sixth_does_not_create_row(self):
        # Tách trần số tác vụ khỏi trần token/chi phí, đã có các bài kiểm riêng.
        settings = config()
        settings['policy'].update(output_tokens_per_user=200000, usd_per_user='1.00')
        self.app.configure_ai(self.owner, settings)
        identifiers = []
        for _ in range(5):
            identifier = self.app.tasks.create(
                USER, {"prompt": "Phân tích lỗi từ dữ liệu tổng hợp để nghiệm thu"}
            )["id"]
            identifiers.append(identifier)
            task = self.finish(identifier)
            self.assertEqual(task["status"], "completed", task["events"][-1])
            self.assertEqual(task["team"]["models"]["bdsg-debug"]["id"], "code-model")
        with self.assertRaises(LoiMoHinhBDSG):
            self.app.tasks.create(
                USER, {"prompt": "Lượt thứ sáu không được gửi tới API"}
            )
        with self.assertRaises(LoiMoHinhBDSG):
            self.app.tasks.followup(
                USER, identifiers[0], "Tiếp tục tác vụ khi đã hết hạn mức ngày"
            )
        self.assertEqual(self.app.tasks.detail(USER, identifiers[0])["run"], 1)
        with self.app.kho.ket_noi() as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM cong_viec_tasks").fetchone()[0], 5
            )
            self.assertEqual(
                db.execute("SELECT count(*) FROM ai_task_credits").fetchone()[0], 5
            )
        self.assertEqual(len(self.calls), 15)
        self.assertEqual(
            self.app.ai.budget.status(USER, DEFAULT_POLICY)["calls_used"], 15
        )

    def test_kernel_denies_operator_config_and_legacy_cannot_bypass_hub(self):
        for name, args in (("mo_hinh.cau_hinh", {}), ("mo_hinh.luu", config())):
            self.assertFalse(self.app.core.goi(USER, name, args)["ok"])
        self.assertTrue(self.app.core.goi(USER, "mo_hinh.danh_sach", {})["ok"])
        self.assertNotIn("usd_global",self.app.ai.quota(USER)["policy"])
        with self.assertRaises(ValueError):
            self.app.model_settings.save(
                self.owner,
                {
                    "provider": "openai",
                    "model": "synthetic",
                    "api_key": "synthetic-api-key",
                },
            )
        self.assertIs(self.app.tasks.model, self.app.ai)

    def test_gateway_not_ready_does_not_consume_task_credit(self):
        self.app.ai.probe = lambda key, aliases: False
        with self.assertRaises(LoiMoHinhBDSG):
            self.app.tasks.create(
                USER, {"prompt": "Tác vụ phải chờ gateway nạp đúng danh mục"}
            )
        self.assertEqual(
            self.app.ai.budget.status(USER, DEFAULT_POLICY)["tasks_used"], 0
        )
        self.assertEqual(self.app.tasks.list(USER)["tasks"], [])

    def test_manual_model_is_used_by_planner_specialist_and_synthesis(self):
        identifier = self.app.tasks.create(
            USER,
            {
                "prompt": "Kiểm mô hình chọn tay khác mặc định cho mọi bước",
                "model_selection": "code-model",
            },
        )["id"]
        self.assertEqual(self.finish(identifier)["status"], "completed")
        self.assertEqual(len(self.aliases), 3)
        self.assertTrue(all(alias.startswith("code-model-") for alias in self.aliases))
        with self.app.kho.ket_noi() as db:
            reserved = db.execute('SELECT output_tokens FROM ai_reservations WHERE task_id=?', (identifier,)).fetchall()
        self.assertEqual([row[0] for row in reserved], [MoHinhLiteLLM.MAX_OUTPUT_TOKENS] * 3)

    def test_admin_cannot_change_profile_while_task_is_in_flight(self):
        entered, release = threading.Event(), threading.Event()

        class Blocked:
            def run(inner, *args):
                entered.set()
                if not release.wait(3):
                    raise AssertionError("Bài kiểm chặn không được giải phóng")
                raise LoiMoHinhBDSG("Lỗi có chủ đích trong bài kiểm tổng hợp")

        self.app.ai.factory = lambda alias, key: Blocked()
        revision = self.app.ai.data["revision"]
        identifier = self.app.tasks.create(
            USER, {"prompt": "Kiểm không đổi nhà cung cấp giữa lúc đang chạy"}
        )["id"]
        try:
            self.assertTrue(entered.wait(3))
            result = self.app.core.goi(self.owner, "mo_hinh.luu", config())
            self.assertFalse(result["ok"])
            self.assertEqual(self.app.ai.data["revision"], revision)
        finally:
            release.set()
        self.finish(identifier)


if __name__ == "__main__":
    unittest.main()
