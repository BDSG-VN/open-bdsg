"""Kiểm ranh giới phê duyệt: tạo dự thảo không được gây tác động."""

import tempfile
import time
import unittest
from may_chu import UngDung

A = {"id": "operator-browser", "name": "Browser operator", "role": "operator"}
OWNER = {"id": "chu-quan", "name": "Owner", "role": "quan-tri"}


class BrowserWire:
    def __init__(self):
        self.value = ""
        self.signature = "a" * 64
        self.nonce = "observation-one"
        self.effects = 0

    def __call__(self, data):
        if data["action"] == "inspect":
            return {
                "ok": True,
                "result": {
                    "target": {
                        "signature": self.signature,
                        "url": "https://example.com/form",
                        "tag": "input",
                        "type": "text",
                        "label": "Business need",
                        "form_action": "https://example.com/submit",
                    },
                    "screenshot": "",
                },
            }
        if data["action"] == "approved":
            if data["expected_target"] != self.signature or data["nonce"] != self.nonce:
                return {"ok": False, "error": "stale"}
            self.effects += 1
            self.value = data["text"]
            self.nonce = "consumed"
            return {"ok": True, "result": {"executed": True}}
        raise AssertionError("unexpected browser command")


class ThuPheDuyetBrowser(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = UngDung(self.temp.name, "https://thanhhoa.bdsg.vn", True)
        self.app.kho.tao_chu("owner-password-test-only")
        self.app.kho.tao_agent(A["id"], A["name"], "operator")
        self.wire = BrowserWire()
        self.app.browser.transport = self.wire
        self.app.actions.browser = self.app.browser
        self.addCleanup(self.close)
        self.task = self.app.tasks.create(
            A,
            {
                "prompt": "Prepare synthetic business form",
                "template": "de-xuat-giai-phap",
                "browser_hosts": ["example.com"],
                "allow_action_drafts": True,
            },
        )
        for _ in range(100):
            if self.app.tasks.detail(A, self.task["id"])["status"] == "completed":
                break
            time.sleep(0.01)

    def close(self):
        self.app.tasks.close()
        self.app.core.audit.close()
        self.temp.cleanup()

    def tool(self, actor, name, args):
        result = self.app.core.goi(actor, name, args)
        self.assertTrue(result["ok"], result)
        return result["ket_qua"]

    def proposal(self):
        return self.tool(
            A,
            "hanh_dong.de_xuat",
            {
                "task_id": self.task["id"],
                "tool": "trinh_duyet.hanh_dong",
                "arguments": {
                    "task_id": self.task["id"],
                    "action": "fill",
                    "node": 0,
                    "nonce": self.wire.nonce,
                    "text": "A synthetic business request",
                },
            },
        )

    def test_draft_has_no_effect_then_owner_approval_executes_once(self):
        action = self.proposal()
        self.assertEqual(self.wire.value, "")
        self.assertEqual(self.wire.effects, 0)
        decided = self.tool(
            OWNER,
            "hanh_dong.duyet",
            {"id": action["id"], "digest": action["digest"], "approve": True},
        )
        self.assertEqual(decided["status"], "completed")
        self.assertEqual(self.wire.value, "A synthetic business request")
        self.assertFalse(
            self.app.core.goi(
                OWNER,
                "hanh_dong.duyet",
                {"id": action["id"], "digest": action["digest"], "approve": True},
            )["ok"]
        )
        self.assertEqual(self.wire.effects, 1)

    def test_direct_execution_is_denied(self):
        action = self.proposal()
        self.assertFalse(
            self.app.core.goi(
                A, "trinh_duyet.hanh_dong", action["payload"]["arguments"]
            )["ok"]
        )
        self.assertEqual(self.wire.effects, 0)

    def test_changed_form_blocks_approval_but_can_be_rejected(self):
        action = self.proposal()
        self.wire.signature = "b" * 64
        self.assertFalse(
            self.app.core.goi(
                OWNER,
                "hanh_dong.duyet",
                {"id": action["id"], "digest": action["digest"], "approve": True},
            )["ok"]
        )
        preview = self.tool(OWNER, "hanh_dong.xem_trinh_duyet", {"id": action["id"]})
        self.assertFalse(preview["matches"])
        self.assertEqual(self.wire.effects, 0)
        rejected = self.tool(
            OWNER,
            "hanh_dong.duyet",
            {"id": action["id"], "digest": action["digest"], "approve": False},
        )
        self.assertEqual(rejected["status"], "rejected")

    def test_preview_does_not_consume_observation(self):
        action = self.proposal()
        self.assertTrue(
            self.tool(OWNER, "hanh_dong.xem_trinh_duyet", {"id": action["id"]})[
                "matches"
            ]
        )
        self.assertEqual(self.wire.effects, 0)
        self.assertEqual(
            self.tool(
                OWNER,
                "hanh_dong.duyet",
                {"id": action["id"], "digest": action["digest"], "approve": True},
            )["status"],
            "completed",
        )
        self.assertFalse(
            self.app.core.goi(
                A, "trinh_duyet.hanh_dong", action["payload"]["arguments"]
            )["ok"]
        )

    def test_expired_proposal_cannot_execute(self):
        action = self.proposal()
        with self.app.kho.ket_noi() as db:
            db.execute("UPDATE actions SET expires=0 WHERE id=?", (action["id"],))
        self.assertFalse(
            self.app.core.goi(
                OWNER,
                "hanh_dong.duyet",
                {"id": action["id"], "digest": action["digest"], "approve": True},
            )["ok"]
        )
        self.assertEqual(self.wire.effects, 0)
        self.assertEqual(
            self.tool(
                OWNER,
                "hanh_dong.duyet",
                {"id": action["id"], "digest": action["digest"], "approve": False},
            )["status"],
            "rejected",
        )

    def test_revoked_actor_cannot_execute_but_owner_can_reject(self):
        action = self.proposal()
        with self.app.kho.ket_noi() as db:
            db.execute("UPDATE agents SET active=0 WHERE ma=?", (A["id"],))
        self.assertFalse(
            self.app.core.goi(
                OWNER,
                "hanh_dong.duyet",
                {"id": action["id"], "digest": action["digest"], "approve": True},
            )["ok"]
        )
        self.assertEqual(self.wire.effects, 0)
        self.assertEqual(
            self.tool(
                OWNER,
                "hanh_dong.duyet",
                {"id": action["id"], "digest": action["digest"], "approve": False},
            )["status"],
            "rejected",
        )

    def test_followup_invalidates_old_proposal(self):
        action = self.proposal()
        self.tool(
            A,
            "cong_viec.tiep_tuc",
            {"id": self.task["id"], "text": "A new synthetic round of business work"},
        )
        self.assertFalse(
            self.app.core.goi(
                OWNER,
                "hanh_dong.duyet",
                {"id": action["id"], "digest": action["digest"], "approve": True},
            )["ok"]
        )
        self.assertEqual(self.wire.effects, 0)


if __name__ == "__main__":
    unittest.main()
