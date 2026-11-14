"""Kiểm Chromium với biểu mẫu tổng hợp; mọi yêu cầu HTTPS được trả tại chỗ."""

import os
import time
import unittest

from trinh_duyet_worker import BrowserWorker


@unittest.skipUnless(
    os.environ.get("BDSG_TEST_BROWSER") == "1",
    "Requires isolated Chromium test environment",
)
class ThuBieuMau(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(chromium_sandbox=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context()
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.page.route(
            "**/*",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body='<form action="/submit"><label>Business need<input name="need"></label><button>Save</button></form>',
            ),
        )
        self.page.goto("https://example.com/form")
        self.worker = BrowserWorker.__new__(BrowserWorker)
        self.worker.revoked_owners = set()
        self.worker.revoked_tasks = set()
        self.sessions = {
            "task:1": {
                "owner": "test-actor",
                "hosts": ["example.com"],
                "context": self.context,
                "page": self.page,
                "expires": time.monotonic() + 60,
                "nodes": [],
                "nonce": "",
                "count": 0,
            }
        }
        self.observation = self.command(action="observe")
        self.args = {
            "node": 0,
            "nonce": self.observation["nonce"],
            "intent": "fill",
            "text": "Synthetic business need",
        }

    def command(self, **args):
        return self.worker.command(
            self.browser,
            self.sessions,
            {"task_id": "task:1", "owner": "test-actor", **args},
        )

    def test_inspection_then_approval_and_nonce_replay(self):
        target = self.command(action="inspect", **self.args)["target"]
        self.assertEqual(self.page.locator("input").input_value(), "")
        self.assertNotIn("values", target)
        self.command(
            action="approved", expected_target=target["signature"], **self.args
        )
        self.assertEqual(self.page.locator("input").input_value(), self.args["text"])
        with self.assertRaises(ValueError):
            self.command(
                action="approved", expected_target=target["signature"], **self.args
            )

    def test_changed_form_blocks_effect(self):
        target = self.command(action="inspect", **self.args)["target"]
        self.page.locator("input").fill("Changed by another actor")
        with self.assertRaises(ValueError):
            self.command(
                action="approved", expected_target=target["signature"], **self.args
            )
        self.assertEqual(
            self.page.locator("input").input_value(), "Changed by another actor"
        )

    def test_sensitive_forms_require_manual_takeover(self):
        for attributes in (
            'type="password"',
            'autocomplete="one-time-code"',
            'name="card_number"',
            'type="file"',
        ):
            with self.subTest(attributes=attributes):
                self.page.set_content(
                    "<form><input " + attributes + "><button>Save</button></form>"
                )
                observed = self.command(action="observe")
                with self.assertRaises(PermissionError):
                    self.command(
                        action="inspect",
                        node=1,
                        nonce=observed["nonce"],
                        intent="click",
                    )

    def test_changed_destination_blocks_effect(self):
        target = self.command(action="inspect", **self.args)["target"]
        self.page.locator("form").evaluate("e=>e.action='https://other.example/submit'")
        with self.assertRaises(ValueError):
            self.command(
                action="approved", expected_target=target["signature"], **self.args
            )

    def test_preview_does_not_invalidate_proposal(self):
        first = self.command(action="inspect", **self.args)["target"]
        preview = self.command(action="inspect", image=True, **self.args)
        self.assertEqual(preview["target"], first)
        self.assertTrue(preview["screenshot"])
        self.command(action="approved", expected_target=first["signature"], **self.args)
        self.assertEqual(self.page.locator("input").input_value(), self.args["text"])

    def test_select_click_and_key_require_matching_snapshot(self):
        self.page.set_content(
            '<form><select name="kind"><option value="a">A</option><option value="b">B</option></select><button type="button" onclick="this.dataset.clicked=1">Save</button><input name="note" onkeydown="event.preventDefault();this.dataset.key=event.key"></form>'
        )
        for node, intent, text in (
            (0, "select", "b"),
            (1, "click", ""),
            (2, "key", "Enter"),
        ):
            observed = self.command(action="observe")
            args = {
                "node": node,
                "intent": intent,
                "text": text,
                "nonce": observed["nonce"],
            }
            target = self.command(action="inspect", **args)["target"]
            self.command(action="approved", expected_target=target["signature"], **args)
        self.assertEqual(self.page.locator("select").input_value(), "b")
        self.assertEqual(self.page.locator("button").get_attribute("data-clicked"), "1")
        self.assertEqual(self.page.locator("input").get_attribute("data-key"), "Enter")


if __name__ == "__main__":
    unittest.main()
