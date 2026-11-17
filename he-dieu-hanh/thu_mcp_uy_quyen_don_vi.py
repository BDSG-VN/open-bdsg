"""Grant và dữ liệu qua nhân thật; không bật HTTP hoặc dùng credential thật."""
import json
import tempfile
import time
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from may_chu import UngDung
from mcp_uy_quyen_don_vi import LoiChungThuMCP
from sao_luu_he_thong import backup, restore

OWNER = {'id': 'chu-quan', 'role': 'quan-tri', 'name': 'Chu quan thu'}
USER = {'id': 'mcp-user', 'role': 'operator', 'name': 'Nguoi cap thu'}
MEMBER = {'id': 'mcp-member', 'role': 'operator', 'name': 'Thanh vien thu'}


class ThuUyQuyenMCPDonVi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = UngDung(self.tmp.name, 'https://preview.test', True, unit_preview=True)
        self.addCleanup(self.app.core.audit.close)
        self.addCleanup(self.app.tasks.close)
        self.app.kho.tao_chu('synthetic-password-only')
        for actor in (USER, MEMBER):
            self.app.kho.tao_agent(actor['id'], actor['name'], 'operator')
        self.units = [self.app.units.create(OWNER, {'name': name, 'admin': USER['id']})['id']
                      for name in ('Don vi MCP A', 'Don vi MCP B')]
        for identifier in self.units:
            self.app.units.set_member(OWNER, {'unit_id': identifier, 'identity': MEMBER['id'], 'role': 'member'})
        self.actor = self.app.units.bind(USER, self.units[0])
        self.actor_b = self.app.units.bind(USER, self.units[1])
        self.member = self.app.units.bind(MEMBER, self.units[0])
        self.service = self.app.inbound_mcp
        self.now = time.time()
        self.service.clock = lambda: self.now
        self.project = self.app.projects.create(self.actor, {'name': 'Du an duoc cap', 'context': 'ONLY-GRANTED-CONTEXT'})['id']
        self.other_project = self.app.projects.create(self.actor, {'name': 'Du an ngoai grant', 'context': 'OUTSIDE-PROJECT'})['id']

    def grant(self, actor=None, **extra):
        return self.service.create(actor or self.actor, {'name': 'Client thu nghiem', 'client_id': 'synthetic-client',
            'tools': ['du_an.danh_sach', 'cong_viec.danh_sach', 'cong_viec.chi_tiet'],
            'project_ids': [self.project], 'expires_in': 900, **extra})

    def task(self, project):
        identifier = self.app.tasks.create(self.actor, {'prompt': 'Tong hop du lieu kiem thu MCP',
            'template': 'tong-quan', 'module_ids': [], 'project_id': project})['id']
        for _ in range(300):
            task = self.app.tasks.detail(self.actor, identifier)
            if task['status'] == 'completed': return identifier
            if task['status'] in ('failed', 'cancelled', 'interrupted'): self.fail(task['status'])
            time.sleep(.01)
        self.fail('Tac vu thu khong ket thuc')

    def test_credential_chi_tra_mot_lan_khong_o_metadata_log_hoac_legacy(self):
        issued = self.grant()
        credential = issued['credential']
        actor = self.service.authenticate(credential)
        self.assertEqual(actor['id'], USER['id'])
        metadata = self.service.list(self.actor)
        self.assertTrue(credential not in json.dumps(metadata), 'Metadata không được chứa credential')
        self.assertNotIn('token_hash', json.dumps(metadata))
        self.assertNotIn('issuer_epoch', json.dumps(metadata))
        self.assertIsNone(self.app.kho.tu_token(credential))
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder)/'snapshot'
            backup(self.app.kho.root, bundle)
            self.assertTrue(credential.encode() not in (bundle/'data/van-hanh.db').read_bytes(),
                            'Snapshot không được lưu credential thô')
        self.assertCountEqual([row['name'] for row in self.service.tools(actor)['tools']], issued['tools'])
        response = self.service.call(actor, 'du_an.danh_sach', {})
        self.assertTrue(response['ok'])
        self.assertTrue(credential not in (self.app.kho.root/'nhat-ky-nhan.jsonl').read_text(encoding='utf-8'),
                        'Nhật ký không được chứa credential')

    def test_tools_va_danh_sach_chi_trong_grant_ke_ca_goi_core_truc_tiep(self):
        actor = self.service.authenticate(self.grant()['credential'])
        response = self.app.core.goi(actor, 'du_an.danh_sach', {})
        self.assertTrue(response['ok'])
        self.assertEqual([row['id'] for row in response['ket_qua']['projects']], [self.project])
        self.assertIn('ONLY-GRANTED-CONTEXT', json.dumps(response))
        self.assertNotIn('OUTSIDE-PROJECT', json.dumps(response))
        with self.assertRaises(PermissionError):
            self.service.call(actor, 'mo_hinh.cau_hinh', {})
        self.assertFalse(self.app.core.goi(actor, 'hanh_dong.duyet', {'id': 'unknown', 'digest': 'unknown', 'approve': True})['ok'])
        bypass = self.app.core.mcp(actor, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
        self.assertIn('error', bypass)

    def test_task_list_va_detail_khong_ro_ra_ngoai_project_scope(self):
        allowed, denied, standalone = self.task(self.project), self.task(self.other_project), self.task('')
        actor = self.service.authenticate(self.grant()['credential'])
        listed = self.service.call(actor, 'cong_viec.danh_sach', {})
        self.assertEqual([row['id'] for row in listed['ket_qua']['tasks']], [allowed])
        self.assertEqual(self.service.call(actor, 'cong_viec.chi_tiet', {'id': allowed})['ket_qua']['id'], allowed)
        for identifier in (denied, standalone):
            with self.subTest(identifier=identifier), self.assertRaises(PermissionError):
                self.service.call(actor, 'cong_viec.chi_tiet', {'id': identifier})
        separate = self.service.authenticate(self.grant(project_ids=[''])['credential'])
        self.assertEqual([row['id'] for row in self.service.call(separate, 'cong_viec.danh_sach', {})['ket_qua']['tasks']], [standalone])

    def test_khong_wildcard_extra_args_hoac_tu_cap_lai_quyen(self):
        for extra in ({'tools': ['*']}, {'project_ids': []}, {'tools': ['ket_noi.ghi']}, {'expires_in': True}):
            with self.subTest(extra=extra), self.assertRaises(ValueError): self.grant(**extra)
        actor = self.service.authenticate(self.grant()['credential'])
        with self.assertRaises(ValueError):
            self.service.call(actor, 'du_an.danh_sach', {'unit_id': self.units[1]})
        with self.assertRaises(PermissionError):
            self.grant(actor)
        with self.assertRaises(PermissionError):
            self.service.list(actor)

    def test_unit_a_khong_doi_scope_sang_b_bang_dict(self):
        issued = self.grant()
        actor = self.service.authenticate(issued['credential'])
        forged = {**actor, 'unit_scope': self.actor_b['unit_scope']}
        with self.assertRaises(LoiChungThuMCP): self.service.tools(forged)
        self.assertEqual(self.service.list(self.actor_b), {'grants': []})
        with self.assertRaises(PermissionError): self.service.revoke(self.actor_b, issued['id'])
        reference = self.service.reference(actor, self._connection())
        forged = {**self.actor, 'mcp_delegation': reference}
        with self.assertRaises(LoiChungThuMCP): self.service.tools(forged)

    def _connection(self):
        context = self.app.kho.ket_noi()
        connection = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        return connection

    def test_audience_client_expiry_va_revoke_kiem_moi_luot(self):
        issued = self.grant()
        key = issued['credential']
        for extra in ({'resource': 'https://other.test/mcp'}, {'client_id': 'other-client'}):
            with self.subTest(extra=extra), self.assertRaises(LoiChungThuMCP): self.service.authenticate(key, **extra)
        actor = self.service.authenticate(key, resource='https://preview.test/mcp', client_id='synthetic-client')
        self.now += 901
        with self.assertRaises(LoiChungThuMCP): self.service.tools(actor)
        self.now -= 901
        self.service.revoke(self.actor, issued['id'])
        with self.assertRaises(LoiChungThuMCP): self.service.authenticate(key)
        with self.assertRaises(LoiChungThuMCP): self.service.call(actor, 'du_an.danh_sach', {})

    def test_revoke_rejoin_thay_role_khong_khoi_phuc_token_cu(self):
        issued = self.grant()
        change = {'unit_id': self.units[0], 'identity': USER['id']}
        self.app.units.set_member(OWNER, {'unit_id': self.units[0], 'identity': OWNER['id'], 'role': 'admin'})
        self.app.units.set_member(OWNER, {**change, 'role': 'revoke'})
        self.app.units.set_member(OWNER, {**change, 'role': 'admin'})
        with self.assertRaises(LoiChungThuMCP): self.service.authenticate(issued['credential'])

    def test_member_chi_xem_cua_minh_admin_thu_hoi_khong_nhin_project_ids(self):
        private = self.app.projects.create(self.member, {'name': 'Du an rieng member'})['id']
        issued = self.grant(self.member, project_ids=[private])
        self.assertEqual(len(self.service.list(self.member)['grants']), 1)
        metadata = self.service.list(self.actor)['grants'][0]
        self.assertNotIn('project_ids', metadata)
        self.assertNotIn(private, json.dumps(metadata))
        self.service.revoke(self.actor, issued['id'])
        with self.assertRaises(LoiChungThuMCP): self.service.authenticate(issued['credential'])

    def test_root_khong_scope_va_root_member_khong_thu_hoi_cua_nguoi_khac(self):
        issued = self.grant()
        with self.assertRaises(PermissionError): self.service.list(OWNER)
        self.app.units.set_member(OWNER, {'unit_id': self.units[0], 'identity': OWNER['id'], 'role': 'member'})
        root_member = self.app.units.bind(OWNER, self.units[0])
        with self.assertRaises(PermissionError): self.service.revoke(root_member, issued['id'])

    def test_thu_hoi_trong_khi_doc_chan_tra_ket_qua_cu(self):
        issued = self.grant()
        actor = self.service.authenticate(issued['credential'])
        original = self.app.projects.list
        def read_then_revoke(current):
            response = original(current)
            self.service.revoke(self.actor, issued['id'])
            return response
        self.app.projects.list = read_then_revoke
        response = self.app.core.goi(actor, 'du_an.danh_sach', {})
        self.assertFalse(response['ok'])
        self.assertNotIn('ONLY-GRANTED-CONTEXT', json.dumps(response))

    def test_thu_hoi_project_grant_chan_token_khong_ro_context(self):
        self.app.projects.share(self.actor, {'id': self.project, 'identity': MEMBER['id'], 'role': 'viewer'})
        issued = self.grant(self.member)
        self.app.projects.share(self.actor, {'id': self.project, 'identity': MEMBER['id'], 'role': 'revoke'})
        with self.assertRaises(LoiChungThuMCP): self.service.authenticate(issued['credential'])

    def test_restart_giu_raw_credential_nhung_context_cu_khong_tai_su_dung(self):
        issued = self.grant()
        old_actor = self.service.authenticate(issued['credential'])
        restarted = UngDung(self.app.kho.root, 'https://preview.test', True, unit_preview=True)
        try:
            with self.assertRaises(LoiChungThuMCP): restarted.inbound_mcp.tools(old_actor)
            fresh = restarted.inbound_mcp.authenticate(issued['credential'])
            self.assertEqual(restarted.inbound_mcp.call(fresh, 'du_an.danh_sach', {})['ket_qua']['projects'][0]['id'], self.project)
        finally:
            restarted.tasks.close(); restarted.core.audit.close()

    def test_restore_khong_lam_song_lai_token_snapshot_cu(self):
        issued = self.grant()
        with tempfile.TemporaryDirectory() as directory:
            bundle, target = Path(directory)/'bundle', Path(directory)/'restored'
            backup(self.app.kho.root, bundle)
            self.service.revoke(self.actor, issued['id'])
            restore(bundle, target)
            restored = UngDung(target/'data', 'https://preview.test', True, unit_preview=True)
            try:
                with self.assertRaises(LoiChungThuMCP): restored.inbound_mcp.authenticate(issued['credential'])
                actor = restored.units.bind(USER, self.units[0])
                metadata = restored.inbound_mcp.list(actor)['grants']
                self.assertEqual(len(metadata), 1)
                self.assertFalse(metadata[0]['issuer_current'])
            finally:
                restored.tasks.close(); restored.core.audit.close()

    def test_hai_unit_cung_identity_doc_song_song_khong_tron_context(self):
        project_b = self.app.projects.create(self.actor_b, {'name': 'Du an cua B', 'context': 'B-ONLY-CONTEXT'})['id']
        first = self.service.authenticate(self.grant()['credential'])
        second = self.service.authenticate(self.grant(self.actor_b, project_ids=[project_b])['credential'])
        original, barrier = self.app.projects.list, threading.Barrier(2)
        def interleaved(actor):
            result = original(actor)
            barrier.wait(timeout=3)
            return result
        self.app.projects.list = interleaved
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.service.call, actor, 'du_an.danh_sach', {}) for actor in (first, second)]
            results = [future.result(timeout=5) for future in futures]
        self.assertEqual([[row['id'] for row in result['ket_qua']['projects']] for result in results],
                         [[self.project], [project_b]])
        self.assertNotIn('B-ONLY-CONTEXT', json.dumps(results[0]))
        self.assertNotIn('ONLY-GRANTED-CONTEXT', json.dumps(results[1]))

    def test_het_han_trong_khi_doc_chan_ket_qua(self):
        actor = self.service.authenticate(self.grant()['credential'])
        original = self.app.projects.list
        def read_then_expire(current):
            response = original(current)
            self.now += 901
            return response
        self.app.projects.list = read_then_expire
        response = self.app.core.goi(actor, 'du_an.danh_sach', {})
        self.assertFalse(response['ok'])
        self.assertNotIn('ONLY-GRANTED-CONTEXT', json.dumps(response))

    def test_thu_hoi_project_trong_khi_doc_chan_ket_qua(self):
        grant = {'id': self.project, 'identity': MEMBER['id']}
        self.app.projects.share(self.actor, {**grant, 'role': 'viewer'})
        actor = self.service.authenticate(self.grant(self.member)['credential'])
        original = self.app.projects.list
        def read_then_unshare(current):
            response = original(current)
            self.app.projects.share(self.actor, {**grant, 'role': 'revoke'})
            return response
        self.app.projects.list = read_then_unshare
        response = self.app.core.goi(actor, 'du_an.danh_sach', {})
        self.assertFalse(response['ok'])
        self.assertNotIn('ONLY-GRANTED-CONTEXT', json.dumps(response))


if __name__ == '__main__':
    unittest.main()
