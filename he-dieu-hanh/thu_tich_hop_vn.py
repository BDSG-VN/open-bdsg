"""Hợp đồng tổng hợp của API Việt Nam; không gọi tài khoản hay dịch vụ tính phí."""

import hashlib
import hmac
import io
import json
import os
import socket
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from may_chu import UngDung
from tich_hop_viet_nam import TichHopVietNam
from vn_adapters import decode, prepare
from vn_chu_ky import momo_query_signature, payos_preimage, verify_payos
from vn_hop_dong import catalogue, validate_settings
from vn_transport import LoiTichHop, PhanHoi, VanChuyenHTTPS, retry_after_seconds

OWNER = {"id": "chu-quan", "name": "Chu thu nghiem", "role": "quan-tri"}
KEY = "fake-token-only-for-local-contract-test"


class FakeTransport:
    def __init__(self, data=None, error=None):
        self.data = data or {
            "code": "00",
            "data": [
                {"id": 1, "name": "Ngan hang tong hop", "code": "TEST", "bin": "000000"}
            ],
        }
        self.error = error
        self.calls = []
        self.started = None
        self.release = None

    def request(self, host, method, path, headers=None, body=None, timeout=None):
        self.calls.append((host, method, path, headers, body))
        if self.started:
            self.started.set()
            if not self.release.wait(5):
                raise TimeoutError
        if self.error:
            raise self.error
        return PhanHoi(200, {}, self.data)


class ThuHopDong(unittest.TestCase):
    def test_catalogue_never_claims_account_access_or_bank_balance(self):
        result = catalogue()
        self.assertFalse(result["external_writes_enabled"])
        for item in result["providers"]:
            self.assertFalse(item["live_connection_verified"])
            self.assertNotIn("transfer", item["operations"])
        bank = next(
            item for item in result["providers"] if item["id"] == "bank_openapi"
        )
        self.assertTrue(bank["pending"])
        self.assertEqual(bank["operations"], {})

    def test_paths_credentials_and_tenant_binding_for_commerce(self):
        examples = [
            (
                "kiotviet",
                {"retailer": "shop-thu"},
                "public.kiotapi.com",
                "/products?pageSize=50&currentItem=0",
                "Retailer",
            ),
            (
                "sapo_web",
                {"store": "shop-thu"},
                "shop-thu.mysapo.net",
                "/admin/products.json?limit=50&page=1",
                "X-Sapo-Access-Token",
            ),
            (
                "haravan",
                {},
                "apis.haravan.com",
                "/com/products.json?limit=50&page=1",
                "Authorization",
            ),
        ]
        for identifier, settings, host, path, header in examples:
            with self.subTest(identifier=identifier):
                request = prepare(
                    identifier, settings, {"access_token": KEY}, "products", {}
                )
                self.assertEqual(
                    (request.host, request.method, request.path), (host, "GET", path)
                )
                self.assertIn(header, request.headers)
                self.assertNotIn(KEY, request.path)

    def test_unknown_endpoints_and_unsafe_tenants_are_not_accepted(self):
        for store in (
            "evil.example/path",
            "x.mysapo.net.evil.test",
            "127.0.0.1",
            "../x",
            "x\nHost: evil",
        ):
            with self.subTest(store=store), self.assertRaises(LoiTichHop):
                validate_settings("sapo_web", {"store": store})
        with self.assertRaises(LoiTichHop):
            prepare(
                "kiotviet",
                {"retailer": "shop"},
                {"access_token": KEY},
                "products",
                {"url": "https://example.test"},
            )
        with self.assertRaises(LoiTichHop):
            prepare("haravan", {}, {"access_token": KEY}, "delete_order", {})
        with self.assertRaises(LoiTichHop):
            validate_settings("meinvoice", {})

    def test_zalo_uses_official_oa_route_and_zbs_scope_separate(self):
        request = prepare("zalo_oa", {}, {"access_token": KEY}, "oa_info", {})
        self.assertEqual(
            (request.host, request.path), ("openapi.zalo.me", "/v2.0/oa/getoa")
        )
        self.assertEqual(request.headers, {"access_token": KEY})
        with self.assertRaises(LoiTichHop):
            prepare(
                "zalo_oa",
                {},
                {"access_token": KEY},
                "template_sample",
                {"template_id": "1"},
            )
        sample = prepare(
            "zalo_zbs",
            {},
            {"access_token": KEY},
            "template_sample",
            {"template_id": "1"},
        )
        self.assertEqual(sample.host, "business.openapi.zalo.me")
        self.assertEqual(sample.headers["Content-Type"], "application/json")
        result = decode(
            sample,
            PhanHoi(
                200,
                {},
                {
                    "error": 0,
                    "data": {
                        "balance_debt": 2000,
                        "customer_name": "customer_name_sample",
                    },
                },
            ),
            {},
        )
        self.assertEqual(
            result["items"],
            [
                {"template_id": "1", "parameter": "balance_debt", "sample_value": 2000},
                {
                    "template_id": "1",
                    "parameter": "customer_name",
                    "sample_value": "customer_name_sample",
                },
            ],
        )
        with self.assertRaises(LoiTichHop):
            decode(request, PhanHoi(200, {}, {"error": -216, "message": KEY}), {})

    def test_meta_pins_version_and_does_not_follow_next_url_or_return_token(self):
        request = prepare(
            "meta_pages",
            {"page_id": "12345", "graph_version": "v26.0"},
            {"access_token": KEY},
            "conversations",
            {},
        )
        result = decode(
            request,
            PhanHoi(
                200,
                {},
                {
                    "data": [
                        {
                            "id": 10,
                            "updated_time": "date",
                            "access_token": KEY,
                            "participants": {"email": "private"},
                        }
                    ],
                    "paging": {
                        "next": "https://evil.test/?token=" + KEY,
                        "cursors": {"after": "next-cursor"},
                    },
                },
            ),
            {},
        )
        self.assertEqual(result["items"], [{"id": "10", "updated_time": "date"}])
        self.assertEqual(
            result["next_arguments"], {"limit": 20, "after": "next-cursor"}
        )
        self.assertNotIn(KEY, json.dumps(result))
        with self.assertRaises(LoiTichHop):
            prepare(
                "meta_pages",
                {"page_id": "12345", "graph_version": "latest"},
                {"access_token": KEY},
                "page_info",
                {},
            )

    def test_tiktok_post_is_read_only_and_cursor_must_advance(self):
        request = prepare(
            "tiktok_display",
            {},
            {"access_token": KEY},
            "videos",
            {"limit": 1, "cursor": 10},
        )
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.body, {"max_count": 1, "cursor": 10})
        result = decode(
            request,
            PhanHoi(
                200,
                {},
                {
                    "error": {"code": "ok"},
                    "data": {
                        "videos": [{"id": 1234567890123456789, "title": "Clip thu"}],
                        "cursor": 20,
                        "has_more": True,
                    },
                },
            ),
            {},
        )
        self.assertEqual(result["items"][0]["id"], "1234567890123456789")
        self.assertEqual(result["next_arguments"], {"limit": 1, "cursor": 20})
        self.assertFalse(result["external_write_performed"])
        with self.assertRaises(LoiTichHop):
            decode(
                request,
                PhanHoi(
                    200,
                    {},
                    {
                        "error": {"code": "ok"},
                        "data": {"videos": [], "cursor": 10, "has_more": True},
                    },
                ),
                {},
            )

    def test_amis_inventory_query_does_not_invent_invoice_route(self):
        request = prepare(
            "amis_act",
            {"app_id": "app-thu"},
            {"access_token": KEY},
            "inventory",
            {"limit": 1},
        )
        self.assertEqual(
            (request.method, request.path),
            ("POST", "/apir/sync/actopen/get_dictionary"),
        )
        self.assertEqual(request.body["data_type"], 2)
        result = decode(
            request,
            PhanHoi(
                200,
                {},
                {
                    "Success": True,
                    "Data": '[{"inventory_item_id":"1","inventory_item_name":"Hang thu"}]',
                },
            ),
            {},
        )
        self.assertEqual(
            result["items"],
            [{"inventory_item_id": "1", "inventory_item_name": "Hang thu"}],
        )
        self.assertEqual(result["next_arguments"], {"limit": 1, "offset": 1})
        with self.assertRaises(LoiTichHop):
            prepare(
                "amis_act", {"app_id": "app-thu"}, {"access_token": KEY}, "invoices", {}
            )

    def test_decimal_strings_remain_exact_and_nonfinite_amounts_are_rejected(self):
        request = prepare("haravan", {}, {"access_token": KEY}, "orders", {})
        result = decode(
            request,
            PhanHoi(
                200,
                {},
                {
                    "orders": [
                        {
                            "id": 1234567890123456789,
                            "total_price": "12345678901234567890.12",
                        }
                    ]
                },
            ),
            {},
        )
        self.assertEqual(
            result["items"],
            [{"id": "1234567890123456789", "total_price": "12345678901234567890.12"}],
        )
        for amount in (True, float("nan"), float("inf"), "-1", "10,000"):
            with self.subTest(amount=amount), self.assertRaises(LoiTichHop):
                decode(
                    request,
                    PhanHoi(200, {}, {"orders": [{"id": 1, "total_price": amount}]}),
                    {},
                )

    def test_page_sizes_and_malformed_envelopes_fail_closed(self):
        request = prepare(
            "kiotviet",
            {"retailer": "shop"},
            {"access_token": KEY},
            "products",
            {"limit": 1},
        )
        good = decode(
            request,
            PhanHoi(200, {}, {"total": 2, "data": [{"id": 1, "name": "Hang thu"}]}),
            {},
        )
        self.assertEqual(good["next_arguments"], {"limit": 1, "offset": 1})
        for bad in (
            {"data": []},
            {"total": 2, "data": [{"id": 1}, {"id": 2}]},
            {"total": 0, "data": [{"id": 1}]},
        ):
            with self.subTest(bad=bad), self.assertRaises(LoiTichHop):
                decode(request, PhanHoi(200, {}, bad), {})
        for invalid in (True, -1, 0, 101, "50"):
            with self.subTest(invalid=invalid), self.assertRaises(LoiTichHop):
                prepare(
                    "kiotviet",
                    {"retailer": "shop"},
                    {"access_token": KEY},
                    "products",
                    {"limit": invalid},
                )

    def test_payos_signature_is_checked_and_identity_cannot_change(self):
        credentials = {
            "client_id": "fake-id",
            "api_key": "fake-api",
            "checksum_key": "fake-checksum",
        }
        request = prepare(
            "payos", {}, credentials, "payment_status", {"payment_id": "123"}
        )
        data = {
            "id": "payment-test",
            "orderCode": 123,
            "amount": 10000,
            "status": "PENDING",
        }
        preimage = "amount=10000&id=payment-test&orderCode=123&status=PENDING"
        self.assertEqual(payos_preimage(data), preimage)
        signature = hmac.new(
            b"fake-checksum", preimage.encode(), hashlib.sha256
        ).hexdigest()
        result = decode(
            request,
            PhanHoi(200, {}, {"code": "00", "data": data, "signature": signature}),
            credentials,
        )
        self.assertTrue(result["signature_verified"])
        self.assertFalse(result["settlement_applied"])
        with self.assertRaises(LoiTichHop):
            verify_payos(data, "0" * 64, "fake-checksum")
        with self.assertRaises(LoiTichHop):
            decode(
                prepare(
                    "payos", {}, credentials, "payment_status", {"payment_id": "other"}
                ),
                PhanHoi(200, {}, {"code": "00", "data": data, "signature": signature}),
                credentials,
            )

    def test_momo_query_signature_excludes_request_id_and_never_executes_transfer(self):
        raw = b"accessKey=fake-access&orderId=order-1&partnerCode=fake-partner"
        self.assertEqual(
            momo_query_signature(
                "fake-partner", "order-1", "fake-access", "fake-secret"
            ),
            hmac.new(b"fake-secret", raw, hashlib.sha256).hexdigest(),
        )
        request = prepare(
            "momo",
            {"partner_code": "fake-partner", "environment": "sandbox"},
            {"access_key": "fake-access", "secret_key": "fake-secret"},
            "payment_status",
            {"order_id": "order-1"},
        )
        self.assertEqual(
            (request.host, request.path),
            ("test-payment.momo.vn", "/v2/gateway/api/query"),
        )
        data = {
            "orderId": "order-1",
            "requestId": request.body["requestId"],
            "partnerCode": "fake-partner",
            "resultCode": 9000,
            "amount": 10000,
        }
        result = decode(request, PhanHoi(200, {}, data), {})
        self.assertEqual(result["provider_code"], 9000)
        self.assertFalse(result["settlement_applied"])
        with self.assertRaises(LoiTichHop):
            decode(request, PhanHoi(200, {}, {**data, "orderId": "wrong-order"}), {})


class ThuKhoTichHop(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        key = root / "vault.key"
        key.write_bytes(os.urandom(32))
        self.environment = patch.dict(
            os.environ, {"BDSG_INTEGRATION_VAULT_KEY_FILE": str(key)}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.app = UngDung(root / "data", "https://test.example", True)
        self.app.kho.tao_chu("mat-khau-chi-dung-trong-test")
        self.addCleanup(self.app.core.audit.close)
        self.addCleanup(self.app.tasks.close)
        self.transport = FakeTransport()
        self.integration = self.app.vn_integrations
        self.integration.transport = self.transport

    def save(self, **fields):
        return self.integration.save(
            OWNER,
            {
                "provider": "vietqr",
                "label": "Danh muc thu",
                "settings": {},
                "credentials": {},
                "operations": ["banks"],
                **fields,
            },
        )

    def read(self, row, key="request-test-01", **fields):
        return self.integration.read(
            OWNER,
            {
                "id": row["id"],
                "operation": "banks",
                "arguments": {},
                "request_key": key,
                **fields,
            },
        )

    def test_configuration_does_not_call_network_and_secret_is_encrypted(self):
        row = self.save(
            provider="zalo_oa",
            credentials={"access_token": KEY},
            operations=["oa_info"],
        )
        self.assertEqual(self.transport.calls, [])
        self.assertEqual(row["state"], "configured")
        self.assertNotIn(KEY, json.dumps(self.integration.list(OWNER)))
        for path in self.app.kho.root.glob("van-hanh.db*"):
            self.assertNotIn(KEY.encode(), path.read_bytes())
        with self.assertRaises(PermissionError):
            self.integration.list({"id": "operator-a", "role": "operator"})

    def test_readiness_is_local_and_tracks_verified_expired_revoked_states(self):
        self.integration.clock = lambda: 1000
        row = self.save(expires_at=2000)
        self.assertEqual(row["readiness"], {
            "can_attempt_read": True, "blockers": [], "last_read_verified": False,
        })
        self.assertEqual(self.transport.calls, [])
        self.read(row)
        current = self.integration.list(OWNER)["connections"][0]
        self.assertTrue(current["readiness"]["last_read_verified"])
        self.integration.clock = lambda: 2001
        current = self.integration.list(OWNER)["connections"][0]
        self.assertFalse(current["readiness"]["can_attempt_read"])
        self.assertFalse(current["readiness"]["last_read_verified"])
        self.assertIn("authorization_required", current["readiness"]["blockers"])
        with self.assertRaises(LoiTichHop) as failure:
            self.integration.validate_read(OWNER, row["id"], "banks", {})
        self.assertEqual(failure.exception.code, "authorization_required")
        revoked = self.integration.disconnect(OWNER, {"id": row["id"], "expected_revision": 1})
        self.assertIn("connection_changed", revoked["readiness"]["blockers"])
        self.assertEqual(len(self.transport.calls), 1)

    def test_expiry_during_read_discards_provider_payload(self):
        self.integration.clock = lambda: 1000
        row = self.save(expires_at=2000)
        original = self.transport.request
        def response_after_expiry(*args, **kwargs):
            result = original(*args, **kwargs)
            self.integration.clock = lambda: 2001
            return result
        with patch.object(self.transport, "request", side_effect=response_after_expiry):
            with self.assertRaises(LoiTichHop) as failure:
                self.read(row)
        self.assertEqual(failure.exception.code, "authorization_required")
        with self.app.kho.ket_noi() as db:
            run = db.execute("SELECT state,result,error_code FROM vn_runs").fetchone()
        self.assertEqual((run["state"], run["result"], run["error_code"]),
                         ("failed", None, "authorization_required"))

    def test_expiry_while_acquiring_transaction_denies_send_replay_and_commit(self):
        for expired_transaction, replay in ((1, False), (1, True), (2, False)):
            with self.subTest(transaction=expired_transaction, replay=replay):
                self.integration.clock = lambda: 1000
                row = self.save(expires_at=2000)
                request_key = "transaction-test-" + row["id"]
                if replay:
                    self.read(row, key=request_key)
                calls_before = len(self.transport.calls)
                original = self.app.kho.ket_noi
                acquired = [0]
                integration = self.integration

                class ConnectionAfterWait:
                    def __init__(self, db):
                        self.db = db

                    def execute(self, sql, *args):
                        result = self.db.execute(sql, *args)
                        if sql == "BEGIN IMMEDIATE":
                            acquired[0] += 1
                            if acquired[0] == expired_transaction:
                                # Đồng hồ đổi sau khi lấy khóa, như thời gian đã trôi khi chờ.
                                integration.clock = lambda: 2001
                        return result

                    def __getattr__(self, name):
                        return getattr(self.db, name)

                @contextmanager
                def connection():
                    with original() as db:
                        yield ConnectionAfterWait(db)

                with patch.object(self.app.kho, "ket_noi", side_effect=connection):
                    with self.assertRaises(LoiTichHop) as failure:
                        self.read(row, key=request_key)
                self.assertEqual(failure.exception.code, "authorization_required")
                self.assertEqual(len(self.transport.calls) - calls_before,
                                 1 if expired_transaction == 2 else 0)
                with self.app.kho.ket_noi() as db:
                    runs = db.execute(
                        "SELECT state,result,error_code FROM vn_runs WHERE connection_id=?",
                        (row["id"],),
                    ).fetchall()
                if replay:
                    # Payload cũ còn lưu, nhưng không được trả lại sau khi hết quyền.
                    self.assertEqual(len(runs), 1)
                    self.assertEqual(runs[0]["state"], "succeeded")
                elif expired_transaction == 1:
                    self.assertEqual(runs, [])
                else:
                    self.assertEqual(len(runs), 1)
                    self.assertEqual((runs[0]["state"], runs[0]["result"], runs[0]["error_code"]),
                                     ("failed", None, "authorization_required"))

    def test_local_validation_observes_auth_failure_and_cooldown_without_network(self):
        row = self.save()
        self.transport.error = LoiTichHop("authorization_required")
        with self.assertRaises(LoiTichHop):
            self.read(row)
        current = self.integration.list(OWNER)["connections"][0]
        self.assertIn("authorization_required", current["readiness"]["blockers"])
        with self.assertRaises(LoiTichHop) as failure:
            self.integration.validate_read(OWNER, row["id"], "banks", {})
        self.assertEqual(failure.exception.code, "authorization_required")
        updated = self.save(id=row["id"], expected_revision=1)
        self.transport.error = LoiTichHop("rate_limited", 300)
        with self.assertRaises(LoiTichHop):
            self.read(updated, key="rate-request-001")
        with self.assertRaises(LoiTichHop) as failure:
            self.integration.validate_read(OWNER, updated["id"], "banks", {})
        self.assertEqual(failure.exception.code, "rate_limited")
        self.assertGreaterEqual(failure.exception.retry_after, 299)
        self.assertEqual(len(self.transport.calls), 2)

    def test_read_is_idempotent_within_revision_and_arguments(self):
        row = self.save()
        first = self.read(row)
        second = self.read(row)
        self.assertEqual(len(self.transport.calls), 1)
        self.assertTrue(second["replayed"])
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(
            self.integration.runs(OWNER, {"id": row["id"]})["runs"][0]["records"], 1
        )
        other = self.save(label="Ket noi khac")
        with self.assertRaises(LoiTichHop):
            self.read(other)
        self.assertEqual(len(self.transport.calls), 1)

    def test_stale_update_and_scope_omission_are_denied(self):
        row = self.save()
        updated = self.save(id=row["id"], expected_revision=1, label="Ten moi")
        self.assertEqual(updated["revision"], 2)
        with self.assertRaises(LoiTichHop):
            self.save(id=row["id"], expected_revision=1)
        with self.assertRaises(LoiTichHop):
            self.read(updated, operation="transfer")
        self.assertEqual(len(self.transport.calls), 0)

    def test_kept_credentials_cannot_be_forwarded_to_a_different_tenant(self):
        row = self.save(
            provider="sapo_web",
            settings={"store": "shop-thu"},
            credentials={"access_token": KEY},
            operations=["products"],
        )
        values = {
            "id": row["id"],
            "expected_revision": 1,
            "provider": "sapo_web",
            "label": "Ten thu",
            "settings": {"store": "shop-khac"},
            "operations": ["products"],
        }
        with self.assertRaises(LoiTichHop):
            self.integration.save(OWNER, values)
        values["settings"] = {"store": "shop-thu"}
        self.assertEqual(self.integration.save(OWNER, values)["revision"], 2)

    def test_disconnect_invalidates_cached_read_and_never_returns_credentials(self):
        row = self.save()
        self.read(row)
        disconnected = self.integration.disconnect(
            OWNER, {"id": row["id"], "expected_revision": row["revision"]}
        )
        self.assertFalse(disconnected["enabled"])
        self.assertFalse(disconnected["has_credentials"])
        with self.assertRaises(LoiTichHop):
            self.read(row)
        self.assertEqual(len(self.transport.calls), 1)

    def test_revocation_during_read_discards_response(self):
        row = self.save()
        self.transport.started, self.transport.release = (
            threading.Event(),
            threading.Event(),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.read, row)
            self.assertTrue(self.transport.started.wait(3))
            self.integration.disconnect(
                OWNER, {"id": row["id"], "expected_revision": 1}
            )
            self.transport.release.set()
            with self.assertRaises(LoiTichHop):
                future.result(timeout=5)
        self.assertEqual(
            self.integration.runs(OWNER, {"id": row["id"]})["runs"][0]["state"],
            "failed",
        )

    def test_auth_failure_is_not_retried_until_owner_updates(self):
        row = self.save()
        self.transport.error = LoiTichHop("authorization_required")
        for key in ("request-one", "request-two"):
            with self.assertRaises(LoiTichHop):
                self.read(row, key)
        self.assertEqual(len(self.transport.calls), 1)
        self.assertEqual(
            self.integration.list(OWNER)["connections"][0]["state"],
            "authorization_required",
        )

    def test_missing_expiry_does_not_extend_access_during_label_edit(self):
        self.integration.clock = lambda: 1000
        row = self.save(expires_at=2000)
        updated = self.save(id=row["id"], expected_revision=1, label="Doi ten")
        self.assertEqual(updated["expires_at"], 2000)
        self.integration.clock = lambda: 3000
        with self.assertRaises(LoiTichHop):
            self.read(updated)
        self.assertEqual(len(self.transport.calls), 0)

    def test_http200_expired_token_is_persisted_and_not_called_again(self):
        cases = [
            ("zalo_oa", {}, "oa_info", {}, {"error": -220}, "authorization_required"),
            (
                "zalo_zbs",
                {},
                "template_sample",
                {"template_id": "1"},
                {"error": -124},
                "authorization_required",
            ),
            (
                "zalo_zbs",
                {},
                "template_sample",
                {"template_id": "1"},
                {"error": -117},
                "permission_denied",
            ),
            (
                "meta_pages",
                {"page_id": "123", "graph_version": "v26.0"},
                "page_info",
                {},
                {"error": {"code": 190}},
                "authorization_required",
            ),
            (
                "tiktok_display",
                {},
                "profile",
                {},
                {"error": {"code": "access_token_invalid"}},
                "authorization_required",
            ),
            (
                "amis_act",
                {"app_id": "app-thu"},
                "inventory",
                {},
                {"Success": False, "ErrorCode": "ExpiredToken"},
                "authorization_required",
            ),
        ]
        for case_index, (
            provider_id,
            settings,
            operation,
            arguments,
            response,
            state,
        ) in enumerate(cases):
            with self.subTest(provider=provider_id):
                self.transport.calls.clear()
                self.transport.data = response
                row = self.save(
                    provider=provider_id,
                    settings=settings,
                    credentials={"access_token": KEY},
                    operations=[operation],
                )
                for index in range(2):
                    with self.assertRaises(LoiTichHop) as failure:
                        self.read(
                            row,
                            key=provider_id
                            + "-request-"
                            + str(case_index)
                            + "-"
                            + str(index),
                            operation=operation,
                            arguments=arguments,
                        )
                    self.assertEqual(failure.exception.code, state)
                self.assertEqual(len(self.transport.calls), 1)

    def test_empty_page_record_cannot_be_marked_as_read_success(self):
        self.transport.data = {}
        row = self.save(
            provider="meta_pages",
            settings={"page_id": "123", "graph_version": "v26.0"},
            credentials={"access_token": KEY},
            operations=["page_info"],
        )
        with self.assertRaises(LoiTichHop):
            self.read(row, operation="page_info")
        state = next(
            item["state"]
            for item in self.integration.list(OWNER)["connections"]
            if item["id"] == row["id"]
        )
        self.assertNotEqual(state, "last_read_succeeded")

    def test_cooldown_and_rate_limit_survive_restart_without_replaying_calls(self):
        row = self.save()
        self.transport.error = LoiTichHop("rate_limited", 60)
        with self.assertRaises(LoiTichHop):
            self.read(row)
        restarted = TichHopVietNam(self.app.kho, self.transport)
        with self.assertRaises(LoiTichHop):
            restarted.read(
                OWNER,
                {"id": row["id"], "operation": "banks", "request_key": "after-restart"},
            )
        self.assertEqual(len(self.transport.calls), 1)

    def test_kernel_requires_admin_and_global_write_gate_for_configuration(self):
        token = self.app.kho.tao_agent("operator-a", "Operator", "operator")
        actor = self.app.kho.tu_token(token)
        self.assertFalse(self.app.core.goi(actor, "tich_hop_vn.danh_sach", {})["ok"])
        self.assertTrue(self.app.core.goi(OWNER, "tich_hop_vn.danh_sach", {})["ok"])
        closed = UngDung(
            self.app.kho.root.parent / "closed", "https://test.example", False
        )
        closed.kho.tao_chu("mat-khau-chi-dung-trong-test")
        try:
            result = closed.core.goi(
                OWNER,
                "tich_hop_vn.luu",
                {
                    "provider": "vietqr",
                    "label": "Ngan hang thu",
                    "settings": {},
                    "credentials": {},
                    "operations": ["banks"],
                },
            )
            self.assertFalse(result["ok"])
        finally:
            closed.tasks.close()
            closed.core.audit.close()


class FakeResponse:
    status = 200

    def __init__(self, raw=b'{"data":[]}', headers=None):
        self.raw = io.BytesIO(raw)
        self.headers = headers or [("Content-Type", "application/json")]

    def read1(self, length):
        return self.raw.read(length)

    def getheaders(self):
        return self.headers


class FakeConnection:
    response = None
    closed = False

    def __init__(self, *args):
        self.args = args

    def request(self, *args, **kwargs):
        pass

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class ThuVanChuyen(unittest.TestCase):
    def test_retry_after_seconds_and_http_date_are_not_shortened(self):
        self.assertEqual(LoiTichHop("rate_limited", 3600).retry_after, 3600)
        self.assertEqual(retry_after_seconds("3600", now=0), 3600)
        self.assertEqual(
            retry_after_seconds("Thu, 01 Jan 1970 01:00:00 GMT", now=0), 3600
        )
        self.assertEqual(
            retry_after_seconds("Thu, 01 Jan 1970 00:00:00 GMT", now=3600), 0
        )
        self.assertEqual(retry_after_seconds("invalid", now=0), 60)

    @staticmethod
    def resolver(host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]

    def test_private_dns_and_redirect_are_not_followed(self):
        for address in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"):
            transport = VanChuyenHTTPS(
                resolver=lambda *args, _address=address, **kwargs: [
                    (0, 0, 0, "", (_address, 443))
                ]
            )
            with self.subTest(address=address), self.assertRaises(LoiTichHop):
                transport.request("example.test", "GET", "/path")
        connection = FakeConnection()
        connection.response = FakeResponse()
        connection.response.status = 302
        transport = VanChuyenHTTPS(self.resolver, lambda *args: connection)
        with self.assertRaises(LoiTichHop):
            transport.request("example.test", "GET", "/path")
        self.assertTrue(connection.closed)

    def test_large_response_non_json_and_429_do_not_leak_payload(self):
        cases = [
            FakeResponse(b"x" * (2 * 1024 * 1024 + 1)),
            FakeResponse(b"<html>error secret</html>", [("Content-Type", "text/html")]),
        ]
        limited = FakeResponse(
            b"{}", [("Retry-After", "120"), ("Content-Type", "application/json")]
        )
        limited.status = 429
        cases.append(limited)
        for response in cases:
            connection = FakeConnection()
            connection.response = response
            transport = VanChuyenHTTPS(
                self.resolver, lambda *args, _connection=connection: _connection
            )
            with (
                self.subTest(status=response.status),
                self.assertRaises(LoiTichHop) as failure,
            ):
                transport.request("example.test", "GET", "/path")
            self.assertNotIn("secret", str(failure.exception))
            if response.status == 429:
                self.assertEqual(failure.exception.retry_after, 120)


if __name__ == "__main__":
    unittest.main()
