"""Đầu nối doanh nghiệp qua interface công khai; dữ liệu tổng hợp, không gọi mạng."""
import json
import tempfile
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from kho import Kho
from don_vi import DonVi
from dau_noi_don_vi import DauNoiDonVi
from sao_luu_he_thong import backup, restore
from mcp_truyen_tai import TruyenTaiMCP
from thu_mcp_truyen_tai import Exchange

OWNER = {"id": "chu-quan", "role": "quan-tri"}
ADMIN = {"id": "quan-tri-thu", "role": "operator"}
MEMBER = {"id": "thanh-vien-thu", "role": "operator"}
CATALOGUE = [{"id": "crm", "name": "CRM thử nghiệm"}]


class TransportTongHop:
    def __init__(self):
        self.calls = []
        self.before_send = lambda: None
        self.after_send = lambda: None

    def goi(self, config, method, parameters, guard):
        self.before_send()
        guard()
        self.calls.append((config["url"], config["token"], method, parameters))
        self.after_send()
        return {"tools": [{"name": "crm.list"}, {"name": "crm.delete"}]} if method == "tools/list" else {
            "content": [{"type": "text", "text": config["url"]}]}


class ThuDauNoiDonVi(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kho = Kho(self.temp.name)
        self.kho.tao_chu("synthetic-password-only")
        for actor in (ADMIN, MEMBER):
            self.kho.tao_agent(actor["id"], actor["id"], "operator")
        self.units = DonVi(self.kho)
        self.unit_ids = [self.units.create(OWNER, {"name": name, "admin": ADMIN["id"]})["id"]
                         for name in ("Đơn vị thử A", "Đơn vị thử B")]
        self.actors = [self.units.bind(ADMIN, unit) for unit in self.unit_ids]
        self.service = DauNoiDonVi(self.kho, self.units, CATALOGUE,
                                  origin="https://thanhhoa.bdsg.vn")

    def config(self, suffix="a", **updates):
        return {"platform_id": "crm", "url": "https://crm-"+suffix+".bdsg.vn/mcp",
                "token": "synthetic-private-token-"+suffix, "read_tools": ["crm.list"],
                **updates}

    def test_cung_nen_tang_khac_don_vi_khong_dung_chung_cau_hinh_hoac_chung_thu(self):
        self.service.save(self.actors[0], self.config())
        self.service.save(self.actors[1], self.config("b"))
        fresh = DauNoiDonVi(self.kho, self.units, CATALOGUE, origin="https://thanhhoa.bdsg.vn")
        for actor, suffix in zip(self.actors, ("a", "b")):
            result = fresh.list(actor)
            self.assertEqual(len(result["connections"]), 1)
            self.assertEqual(result["connections"][0]["url"], "https://crm-"+suffix+".bdsg.vn/mcp")
            self.assertTrue(result["connections"][0]["has_token"])
            self.assertNotIn("synthetic-private-token", json.dumps(result))

    def test_quyen_quan_tri_theo_membership_khong_theo_vai_toan_cong(self):
        unit = self.unit_ids[1]
        self.units.set_member(OWNER, {"unit_id": unit, "identity": MEMBER["id"], "role": "admin"})
        self.units.set_member(OWNER, {"unit_id": unit, "identity": ADMIN["id"], "role": "member"})
        member = self.units.bind(ADMIN, unit)
        for actor in (member, OWNER, self.actors[1]):
            for operation in (lambda: self.service.save(actor, self.config()), lambda: self.service.list(actor)):
                with self.assertRaises(PermissionError):
                    operation()
        self.service.save(self.actors[0], self.config())
        self.assertEqual(len(self.service.list(self.actors[0])["connections"]), 1)

    def test_ngat_xoa_khoa_va_ket_noi_lai_can_chung_thu_moi(self):
        actor = self.actors[0]
        original = self.service.save(actor, self.config())
        self.service.save(actor, self.config(token=""))
        disconnected = self.service.disconnect(actor, "crm")
        self.assertFalse(disconnected["has_token"])
        self.assertFalse(disconnected["enabled"])
        self.assertNotEqual(disconnected["revision"], original["revision"])
        with self.assertRaises(ValueError):
            self.service.save(actor, self.config(token=""))
        self.assertEqual(self.service.list(self.actors[1]), {"connections": []})

    def test_probe_khong_tu_cap_cong_cu_va_moi_luot_dung_dung_khoa_don_vi(self):
        transport = TransportTongHop()
        self.service = DauNoiDonVi(self.kho, self.units, CATALOGUE,
                                  origin="https://thanhhoa.bdsg.vn", transport=transport)
        for actor, suffix in zip(self.actors, ("a", "b")):
            self.service.save(actor, self.config(suffix))
            with self.assertRaises(PermissionError):
                self.service.call(actor, "crm", "crm.list", {})
            self.assertEqual(self.service.probe(actor, "crm")["state"], "da-xac-minh")
            result = self.service.call(actor, "crm", "crm.list", {})
            self.assertEqual(result["content"][0]["text"], "https://crm-"+suffix+".bdsg.vn/mcp")
            with self.assertRaises(PermissionError):
                self.service.call(actor, "crm", "crm.delete", {})
            with self.assertRaises(PermissionError):
                self.service.call(actor, "crm", "crm.list", {}, ghi=True)
        self.assertEqual([call[1] for call in transport.calls], [
            "synthetic-private-token-a", "synthetic-private-token-a",
            "synthetic-private-token-b", "synthetic-private-token-b"])

    def test_khong_nhan_tool_rong_hoac_co_ghi_khong_dung_kieu(self):
        transport = TransportTongHop()
        self.service = DauNoiDonVi(self.kho, self.units, CATALOGUE,
                                  origin="https://thanhhoa.bdsg.vn", transport=transport)
        self.service.save(self.actors[0], self.config())
        self.service.probe(self.actors[0], "crm")
        for tool in (None, "", [], "*"):
            with self.subTest(tool=tool), self.assertRaises((ValueError, PermissionError)):
                self.service.call(self.actors[0], "crm", tool, {})
        self.assertEqual(len(transport.calls), 1)
        for writes in ({}, None, ""):
            with self.subTest(writes=writes), self.assertRaises(ValueError):
                self.service.save(self.actors[0], self.config(write_tools=writes))

    def ready(self):
        transport = TransportTongHop()
        service = DauNoiDonVi(self.kho, self.units, CATALOGUE,
                             origin="https://thanhhoa.bdsg.vn", transport=transport)
        service.save(self.actors[0], self.config())
        service.probe(self.actors[0], "crm")
        return service, transport

    def test_doi_khoa_trong_callback_chan_gui_truoc_transport(self):
        service, transport = self.ready()
        transport.before_send = lambda: service.save(self.actors[0], self.config(token="synthetic-rotated-token"))
        with self.assertRaises(PermissionError):
            service.call(self.actors[0], "crm", "crm.list", {})
        self.assertEqual(len(transport.calls), 1, "Chỉ probe cũ đã gửi; call bị chặn trước gửi")

    def test_ngat_sau_khi_gui_khong_tra_ket_qua_cu_hoac_tu_retry(self):
        service, transport = self.ready()
        transport.after_send = lambda: service.disconnect(self.actors[0], "crm")
        with self.assertRaises(PermissionError):
            service.call(self.actors[0], "crm", "crm.list", {})
        self.assertEqual(len(transport.calls), 2, "Có một call đã gửi, không tự gọi lại")
        self.assertFalse(service.list(self.actors[0])["connections"][0]["enabled"])

    def test_thu_hoi_khi_probe_khong_ghi_metadata_tu_context_cu(self):
        transport = TransportTongHop()
        service = DauNoiDonVi(self.kho, self.units, CATALOGUE,
                             origin="https://thanhhoa.bdsg.vn", transport=transport)
        unit = self.unit_ids[0]
        self.units.set_member(OWNER, {"unit_id": unit, "identity": MEMBER["id"], "role": "admin"})
        service.save(self.actors[0], self.config())
        transport.after_send = lambda: self.units.set_member(OWNER, {
            "unit_id": unit, "identity": ADMIN["id"], "role": "revoke"})
        with self.assertRaises(PermissionError):
            service.probe(self.actors[0], "crm")
        current = service.list(self.units.bind(MEMBER, unit))["connections"][0]
        self.assertEqual(current["state"], "da-khai-bao")
        self.assertIsNone(current["checked_at"])

    def test_snapshot_phuc_hoi_cung_membership_va_token_khong_dung_lai_context_cu(self):
        service, transport = self.ready()
        with tempfile.TemporaryDirectory() as folder:
            bundle, target = Path(folder)/"snapshot", Path(folder)/"restored"
            backup(self.kho.root, bundle)
            restore(bundle, target)
            kho = Kho(target/"data")
            units = DonVi(kho)
            restored = DauNoiDonVi(kho, units, CATALOGUE,
                                  origin="https://thanhhoa.bdsg.vn", transport=transport)
            with self.assertRaises(PermissionError):
                restored.list(self.actors[0])
            actor = units.bind(ADMIN, self.unit_ids[0])
            self.assertEqual(restored.list(actor), service.list(self.actors[0]))
            restored.call(actor, "crm", "crm.list", {})
            self.assertEqual(transport.calls[-1][1], "synthetic-private-token-a")
            restored.disconnect(actor, "crm")
            self.assertTrue(service.list(self.actors[0])["connections"][0]["enabled"])

    def test_loi_va_phan_hoi_upstream_khong_lam_lo_token(self):
        service, transport = self.ready()
        original = transport.goi
        def reflect(config, method, parameters, guard):
            original(config, method, parameters, guard)
            return {"content": [{"text": "echo "+config["token"]}]}
        transport.goi = reflect
        result = service.call(self.actors[0], "crm", "crm.list", {})
        self.assertNotIn("synthetic-private-token-a", json.dumps(result))
        self.assertIn("CHUNG-THU-DA-CHE", result["content"][0]["text"])
        def failure():
            raise ValueError("synthetic-private-token-a")
        transport.before_send = failure
        with self.assertRaises(ValueError) as raised:
            service.call(self.actors[0], "crm", "crm.list", {})
        self.assertNotIn("synthetic-private-token-a", str(raised.exception))
        probe = service.probe(self.actors[0], "crm")
        self.assertEqual(probe["state"], "loi-ket-noi")
        self.assertNotIn("synthetic-private-token-a", json.dumps(probe))

    def test_hai_worker_cung_doi_tuong_khong_doi_cau_hinh_cho_nhau(self):
        service, transport = self.ready()
        service.save(self.actors[1], self.config("b"))
        service.probe(self.actors[1], "crm")
        barrier = threading.Barrier(2)
        transport.before_send = lambda: barrier.wait(timeout=3)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(service.call, actor, "crm", "crm.list", {}) for actor in self.actors]
            results = [future.result(timeout=5) for future in futures]
        self.assertEqual([result["content"][0]["text"] for result in results], [
            "https://crm-a.bdsg.vn/mcp", "https://crm-b.bdsg.vn/mcp"])
        self.assertEqual(sorted((entry[0], entry[1]) for entry in transport.calls[-2:]), [
            ("https://crm-a.bdsg.vn/mcp", "synthetic-private-token-a"),
            ("https://crm-b.bdsg.vn/mcp", "synthetic-private-token-b")])

    def test_doi_khoa_sau_initialize_chan_notification_va_tools_list(self):
        exchange = Exchange()
        actor = self.actors[0]
        def rotate(*args):
            response = exchange(*args)
            if args[5] and json.loads(args[5])["method"] == "initialize":
                service.save(actor, self.config(token="synthetic-rotated-during-handshake"))
            return response
        transport = TruyenTaiMCP(resolver=lambda *_args, **_options: [(2, 1, 6, "", ("1.1.1.1", 443))], exchange=rotate)
        service = DauNoiDonVi(self.kho, self.units, CATALOGUE,
                             origin="https://thanhhoa.bdsg.vn", transport=transport)
        service.save(actor, self.config())
        with self.assertRaises(PermissionError):
            service.probe(actor, "crm")
        self.assertEqual([json.loads(entry[5])["method"] for entry in exchange.requests], ["initialize"])
        self.assertEqual(service.list(actor)["connections"][0]["state"], "da-khai-bao")


if __name__ == "__main__":
    unittest.main()
