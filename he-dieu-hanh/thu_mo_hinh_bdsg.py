"""Kiểm agent đọc BDSG bằng transport giả; không chạm API thật hoặc dùng khóa thật."""
import json
import unittest
import tempfile
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dieu_phoi import DieuPhoi
from kho import Kho
from mo_hinh_bdsg import MoHinhBDSG, LoiMoHinhBDSG


ENV = {"BDSG_MODEL_BASE_URL": "https://llm.bdsg.vn/v1", "BDSG_MODEL_NAME": "bdsg-test", "BDSG_MODEL_API_KEY": "khoa-gia-chi-trong-test"}


def answer(content=None, calls=None):
    message = {"role": "assistant", "content": content}
    if calls is not None:
        message["tool_calls"] = calls
    return {"choices": [{"message": message}]}


def call(name, arguments="{}"):
    return {"id": "call-test", "type": "function", "function": {"name": name, "arguments": arguments}}


class Response:
    status = 200

    def __init__(self, value):
        self.raw = json.dumps(value).encode() if not isinstance(value, bytes) else value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, count):
        return self.raw[:count]


class Transport:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return Response(reply)


class Core:
    def __init__(self):
        self.calls = []
        self.connections = SimpleNamespace(config=[{"platform_id": "bdsg_crm", "state": "da-xac-minh", "roles": ["quan-tri"], "read_tools": ["crm.list"]}])
        self.nhan = SimpleNamespace(danh_sach_cong_cu=lambda actor: [{"ten": name, "ghi": write, "mo_ta": "test", "luoc_do": {"type": "object", "properties": {}}} for name, write in [("nen_tang.danh_sach", False), ("mo_dun.danh_sach", False), ("kinh_doanh.tao_yeu_cau", True), ("ket_noi.doc", False)]])

    def danh_tinh(self, actor):
        return actor

    def goi(self, actor, name, arguments):
        self.calls.append((actor, name, arguments))
        return {"ok": True, "ma_theo_doi": "test-trace", "ket_qua": {"products": [{"id": "bdsg_crm"}]}}


class ThuMoHinh(unittest.TestCase):
    def test_module_read_crosses_real_core_policy_and_audit(self):
        actor = {"id": "chu-quan", "name": "Chu", "role": "quan-tri"}
        args = {"platform_id": "bdsg_crm", "tool": "crm.list", "arguments": {"limit": 1}}
        scope = {"allow_reads": True, "selected_ids": ["bdsg_crm"], "read_tools": {"bdsg_crm": ["crm.list"]}}
        transport = Transport([answer(calls=[call("ket_noi__doc", json.dumps(args))]), answer("# Báo cáo đã đọc dữ liệu thử")])
        with tempfile.TemporaryDirectory() as directory:
            core = DieuPhoi(Kho(directory), [{"id": "bdsg_crm"}])
            try:
                core.connections.config = [{"platform_id": "bdsg_crm", "state": "da-xac-minh", "read_tools": ["crm.list"]}]
                with patch.object(core.connections, "_phien", return_value={"items": [{"id": "du-lieu-gia"}]}) as mcp:
                    result = MoHinhBDSG(environ=ENV, opener=transport).run("test", {"module_scope": scope}, core, actor)
                self.assertIn("Báo cáo", result)
                self.assertEqual(mcp.call_count, 1)
                self.assertEqual(mcp.call_args.args[1:], ("tools/call", {"name": "crm.list", "arguments": {"limit": 1}}))
                self.assertIn("du-lieu-gia", json.loads(transport.requests[1][0].data)["messages"][-1]["content"])
                audit = (core.kho.root / "nhat-ky-nhan.jsonl").read_text()
                self.assertIn("ket_noi.doc", audit)
                self.assertNotIn("du-lieu-gia", audit)
            finally:
                core.audit.close()

    def test_opted_in_module_read_and_exact_scope(self):
        scope = {"allow_reads": True, "selected_ids": ["bdsg_crm"], "read_tools": {"bdsg_crm": ["crm.list"]}}
        actor = {"id": "chu-quan", "role": "quan-tri"}
        args = {"platform_id": "bdsg_crm", "tool": "crm.list", "arguments": {}}
        transport = Transport([answer(calls=[call("ket_noi__doc", json.dumps(args))]), answer("Báo cáo từ dữ liệu công cụ")])
        core = Core()
        result = MoHinhBDSG(environ=ENV, opener=transport).run("test", {"module_scope": scope}, core, actor)
        self.assertIn("Báo cáo", result)
        self.assertEqual(core.calls, [(actor, "ket_noi.doc", args)])
        self.assertIn("ket_noi__doc", str(json.loads(transport.requests[0][0].data)["tools"]))
        for change in (lambda c: c.connections.config.clear(), lambda c: c.connections.config[0].update(state="da-khai-bao"), lambda c: c.connections.config[0].update(roles=["operator"]), lambda c: c.connections.config[0].update(read_tools=[])):
            core = Core()
            change(core)
            with self.assertRaises(LoiMoHinhBDSG):
                MoHinhBDSG(environ=ENV, opener=Transport([answer(calls=[call("ket_noi__doc", json.dumps(args))])])).run("test", {"module_scope": scope}, core, actor)
            self.assertEqual(core.calls, [])

    def test_module_scope_cannot_expand_or_be_used_by_operator(self):
        scope = {"allow_reads": True, "selected_ids": ["bdsg_crm"], "read_tools": {"bdsg_crm": ["crm.list"]}}
        for platform, tool, role in [("bdsg_land", "crm.list", "quan-tri"), ("bdsg_crm", "crm.new", "quan-tri"), ("bdsg_crm", "crm.list", "operator")]:
            core = Core()
            core.connections.config[0]["read_tools"].append("crm.new")
            args = {"platform_id": platform, "tool": tool, "arguments": {}}
            with self.assertRaises(LoiMoHinhBDSG):
                MoHinhBDSG(environ=ENV, opener=Transport([answer(calls=[call("ket_noi__doc", json.dumps(args))])])).run("test", {"module_scope": scope}, core, {"id": "test", "role": role})
            self.assertEqual(core.calls, [])

    def test_module_revocation_between_model_response_and_execution(self):
        core = Core()
        scope = {"allow_reads": True, "selected_ids": ["bdsg_crm"], "read_tools": {"bdsg_crm": ["crm.list"]}}
        args = {"platform_id": "bdsg_crm", "tool": "crm.list", "arguments": {}}
        def revoke(kind, *a, **kw):
            if kind == "tool-start":
                core.connections.config.clear()
        with self.assertRaises(LoiMoHinhBDSG):
            MoHinhBDSG(environ=ENV, opener=Transport([answer(calls=[call("ket_noi__doc", json.dumps(args))])])).run("test", {"module_scope": scope}, core, {"role": "quan-tri"}, revoke)
        self.assertEqual(core.calls, [])

    def test_empty_and_partial_configuration_fail_closed(self):
        empty = MoHinhBDSG(environ={})
        self.assertFalse(empty.configured)
        self.assertEqual(empty.configuration_error, "")
        self.assertEqual(empty.public_status(), {"configured": False, "mode": "quy-trinh", "provider": None, "model": None})
        partial = MoHinhBDSG(environ={"BDSG_MODEL_API_KEY": ENV["BDSG_MODEL_API_KEY"]})
        self.assertTrue(partial.configuration_error)
        self.assertNotIn(ENV["BDSG_MODEL_API_KEY"], partial.configuration_error)

    def test_destination_scope_and_no_public_secret(self):
        for url in ["https://outside.test/v1", "https://bdsg.vn.evil.test/v1", "http://llm.bdsg.vn/v1", "https://user:password@llm.bdsg.vn/v1", "https://llm.bdsg.vn/v1?q=x", "https://llm.bdsg.vn/v1#x", "https://llm.bdsg.vn:8443/v1"]:
            self.assertFalse(MoHinhBDSG(environ={**ENV, "BDSG_MODEL_BASE_URL": url}).configured, url)
        for url in ["https://bdsg.vn/v1", "https://llm.bdsg.vn/v1", "http://127.0.0.1:8000/v1", "http://localhost:8000/v1", "http://[::1]:8000/v1"]:
            model = MoHinhBDSG(environ={**ENV, "BDSG_MODEL_BASE_URL": url})
            self.assertTrue(model.configured, url)
            public = json.dumps(model.public_status())
            self.assertNotIn(url, public)
            self.assertNotIn(ENV["BDSG_MODEL_API_KEY"], public)

    def test_real_core_read_and_followup_model_result(self):
        transport = Transport([answer(calls=[call("nen_tang__danh_sach")]), answer("# Báo cáo có nguồn\nĐã đọc danh mục.")])
        core, actor, events = Core(), {"id": "operator-a", "role": "operator"}, []
        model = MoHinhBDSG(environ=ENV, opener=transport)
        text = model.run("Đề xuất nền tảng", {"products": []}, core, actor, lambda *a, **kw: events.append((a, kw)), lambda: False)
        self.assertIn("Báo cáo", text)
        self.assertEqual(core.calls, [(actor, "nen_tang.danh_sach", {})])
        request, timeout = transport.requests[0]
        self.assertEqual(request.full_url, "https://llm.bdsg.vn/v1/chat/completions")
        self.assertEqual(timeout, 30)
        declared = json.loads(request.data)["tools"]
        self.assertEqual({d["function"]["name"] for d in declared}, {"nen_tang__danh_sach", "mo_dun__danh_sach"})
        second = json.loads(transport.requests[1][0].data)
        self.assertEqual(second["messages"][-1]["role"], "tool")
        self.assertIn("bdsg_crm", second["messages"][-1]["content"])
        self.assertNotIn(ENV["BDSG_MODEL_API_KEY"], str(events))

    def test_unknown_or_write_tool_batch_never_executes(self):
        for name in ["kinh_doanh__tao_yeu_cau", "ket_noi__doc", "os__system", "agent__gui_tin"]:
            core = Core()
            model = MoHinhBDSG(environ=ENV, opener=Transport([answer(calls=[call("nen_tang__danh_sach"), call(name)])]))
            with self.assertRaises(LoiMoHinhBDSG):
                model.run("test", {}, core, {})
            self.assertEqual(core.calls, [])

    def test_cancellation_before_request_and_after_response(self):
        transport = Transport([answer("not-used")])
        with self.assertRaises(LoiMoHinhBDSG):
            MoHinhBDSG(environ=ENV, opener=transport).run("test", {}, Core(), {}, cancelled=lambda: True)
        self.assertEqual(transport.requests, [])
        states = iter([False, True])
        with self.assertRaises(LoiMoHinhBDSG):
            MoHinhBDSG(environ=ENV, opener=transport).run("test", {}, Core(), {}, cancelled=lambda: next(states))
        self.assertEqual(len(transport.requests), 1)

    def test_http_failure_and_bad_response_do_not_echo_secrets(self):
        for reply in [RuntimeError(ENV["BDSG_MODEL_API_KEY"] + ENV["BDSG_MODEL_BASE_URL"]), b"not json", b"x" * (MoHinhBDSG.MAX_RESPONSE + 1), {"choices": []}]:
            with self.assertRaises(LoiMoHinhBDSG) as error:
                MoHinhBDSG(environ=ENV, opener=Transport([reply])).run("test", {}, Core(), {})
            self.assertNotIn(ENV["BDSG_MODEL_API_KEY"], str(error.exception))
            self.assertNotIn(ENV["BDSG_MODEL_BASE_URL"], str(error.exception))

    def test_context_limit_and_eight_turn_limit(self):
        transport = Transport([])
        with self.assertRaises(LoiMoHinhBDSG):
            MoHinhBDSG(environ=ENV, opener=transport).run("test", {"text": "x" * (48 * 1024)}, Core(), {})
        self.assertEqual(transport.requests, [])
        transport = Transport([answer(calls=[call("nen_tang__danh_sach")])] * 8)
        with self.assertRaisesRegex(LoiMoHinhBDSG, "tám lượt"):
            MoHinhBDSG(environ=ENV, opener=transport).run("test", {}, Core(), {})
        self.assertEqual(len(transport.requests), 8)

    def test_provider_must_be_selected_and_key_never_crosses_provider(self):
        vendor_keys = {"OPENAI_API_KEY": "openai-fake", "ANTHROPIC_API_KEY": "anthropic-fake", "OPENAI_MODEL": "openai-exact", "ANTHROPIC_MODEL": "claude-exact"}
        self.assertFalse(MoHinhBDSG(environ=vendor_keys).configured)
        for selected, missing in [("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")]:
            env = {**vendor_keys, "BDSG_MODEL_PROVIDER": selected}
            del env[missing]
            model = MoHinhBDSG(environ=env)
            self.assertFalse(model.configured)
            self.assertTrue(model.configuration_error)
        for selected in ("openai", "anthropic"):
            model = MoHinhBDSG(environ={**ENV, **vendor_keys, "BDSG_MODEL_PROVIDER": selected})
            self.assertTrue(model.configured)
            self.assertEqual(model._key, vendor_keys["OPENAI_API_KEY" if selected == "openai" else "ANTHROPIC_API_KEY"])
            self.assertEqual(model.public_status()["mode"], "mo-hinh-api")
        self.assertFalse(MoHinhBDSG(environ={**vendor_keys, "BDSG_MODEL_PROVIDER": "other"}).configured)

    def test_openai_fixed_endpoint_and_current_chat_token_parameter(self):
        env = {"BDSG_MODEL_PROVIDER": "openai", "OPENAI_API_KEY": "openai-only-key", "OPENAI_MODEL": "model-explicit"}
        transport = Transport([answer("Kết quả OpenAI")])
        result = MoHinhBDSG(environ=env, opener=transport).run("test", {}, Core(), {})
        self.assertEqual(result, "Kết quả OpenAI")
        request = transport.requests[0][0]
        self.assertEqual(request.full_url, "https://api.openai.com/v1/chat/completions")
        headers = {k.lower(): v for k, v in request.header_items()}
        self.assertEqual(headers["authorization"], "Bearer openai-only-key")
        self.assertNotIn("x-api-key", headers)
        body = json.loads(request.data)
        self.assertEqual(body["model"], "model-explicit")
        self.assertEqual(body["max_completion_tokens"], 4096)
        self.assertNotIn("temperature", body)

    def test_anthropic_tool_roundtrip_and_headers(self):
        env = {"BDSG_MODEL_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "anthropic-only-key", "ANTHROPIC_MODEL": "claude-explicit"}
        transport = Transport([{"stop_reason": "tool_use", "content": [{"type": "text", "text": "Đọc danh mục"}, {"type": "tool_use", "id": "toolu-test", "name": "nen_tang__danh_sach", "input": {}}]}, {"stop_reason": "end_turn", "content": [{"type": "text", "text": "# Kết quả Claude"}]}])
        core = Core()
        result = MoHinhBDSG(environ=env, opener=transport).run("test", {}, core, {"id": "chu-quan"})
        self.assertEqual(result, "# Kết quả Claude")
        self.assertEqual(len(core.calls), 1)
        request = transport.requests[0][0]
        self.assertEqual(request.full_url, "https://api.anthropic.com/v1/messages")
        headers = {k.lower(): v for k, v in request.header_items()}
        self.assertEqual(headers["x-api-key"], "anthropic-only-key")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertNotIn("authorization", headers)
        first = json.loads(request.data)
        self.assertEqual(first["max_tokens"], 4096)
        self.assertEqual(first["model"], "claude-explicit")
        self.assertTrue(first["system"])
        self.assertEqual(first["tools"][0]["name"], "nen_tang__danh_sach")
        self.assertIn("input_schema", first["tools"][0])
        self.assertFalse(any(m["role"] == "system" for m in first["messages"]))
        second = json.loads(transport.requests[1][0].data)
        self.assertEqual(second["messages"][-2]["role"], "assistant")
        self.assertEqual(second["messages"][-2]["content"][-1]["type"], "tool_use")
        result_block = second["messages"][-1]["content"][0]
        self.assertEqual(result_block["type"], "tool_result")
        self.assertEqual(result_block["tool_use_id"], "toolu-test")
        self.assertIn("bdsg_crm", result_block["content"])

    def test_anthropic_batch_results_grouped_and_unknown_write_rejected(self):
        env = {"BDSG_MODEL_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "fake-anthropic", "ANTHROPIC_MODEL": "claude-test"}
        tools = [{"type": "tool_use", "id": "one", "name": "nen_tang__danh_sach", "input": {}}, {"type": "tool_use", "id": "two", "name": "mo_dun__danh_sach", "input": {}}]
        transport = Transport([{"content": tools}, {"content": [{"type": "text", "text": "done"}]}])
        core = Core()
        MoHinhBDSG(environ=env, opener=transport).run("test", {}, core, {})
        result_blocks = json.loads(transport.requests[1][0].data)["messages"][-1]["content"]
        self.assertEqual([b["tool_use_id"] for b in result_blocks], ["one", "two"])
        transport = Transport([{"content": [tools[0], {"type": "tool_use", "id": "bad", "name": "agent__gui_tin", "input": {}}]}])
        core = Core()
        with self.assertRaises(LoiMoHinhBDSG):
            MoHinhBDSG(environ=env, opener=transport).run("test", {}, core, {})
        self.assertEqual(core.calls, [])

    def test_vendor_failure_does_not_switch_or_expose_key_and_truncation_fails(self):
        for provider, prefix in [("openai", "OPENAI"), ("anthropic", "ANTHROPIC")]:
            env = {"BDSG_MODEL_PROVIDER": provider, "OPENAI_API_KEY": "secret-openai", "OPENAI_MODEL": "exact-openai", "ANTHROPIC_API_KEY": "secret-anthropic", "ANTHROPIC_MODEL": "exact-anthropic"}
            transport = Transport([RuntimeError(env[prefix + "_API_KEY"])])
            with self.assertRaises(LoiMoHinhBDSG) as error:
                MoHinhBDSG(environ=env, opener=transport).run("test", {}, Core(), {})
            self.assertEqual(len(transport.requests), 1)
            self.assertNotIn("secret-", str(error.exception))
            truncated = {"content": [{"type": "text", "text": "partial"}], "stop_reason": "max_tokens"} if provider == "anthropic" else {"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]}
            with self.assertRaises(LoiMoHinhBDSG):
                MoHinhBDSG(environ=env, opener=Transport([truncated])).run("test", {}, Core(), {})


if __name__ == "__main__":
    unittest.main()
