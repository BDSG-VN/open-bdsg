"""Phê duyệt qua gateway/nhân thật; MCP tổng hợp, không ghi nền tảng thật."""
import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from may_chu import UngDung
from hanh_dong_don_vi import HanhDongDonVi
from thu_dau_noi_don_vi import TransportTongHop
from mcp_truyen_tai import TruyenTaiMCP
from thu_mcp_truyen_tai import Exchange
from sao_luu_he_thong import backup, restore


OWNER = {'id': 'chu-quan', 'name': 'Chu quan thu', 'role': 'quan-tri'}
ADMIN = {'id': 'admin-thu', 'name': 'Admin thu', 'role': 'operator'}
MEMBER = {'id': 'member-thu', 'name': 'Member thu', 'role': 'operator'}


class ThuHanhDongDonVi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = UngDung(self.tmp.name, 'https://preview.test', True, unit_preview=True)
        self.addCleanup(self.app.core.audit.close)
        self.addCleanup(self.app.tasks.close)
        self.app.kho.tao_chu('synthetic-password-only')
        for actor in (ADMIN, MEMBER):
            self.app.kho.tao_agent(actor['id'], actor['name'], actor['role'])
        self.unit = self.app.units.create(OWNER, {'name': 'Don vi thu A', 'admin': ADMIN['id']})['id']
        self.app.units.set_member(OWNER, {'unit_id': self.unit, 'identity': MEMBER['id'], 'role': 'member'})
        self.app.units.set_member(OWNER, {'unit_id': self.unit, 'identity': OWNER['id'], 'role': 'admin'})
        self.admin = self.app.units.bind(ADMIN, self.unit)
        self.member = self.app.units.bind(MEMBER, self.unit)
        self.transport = TransportTongHop()
        self.app.connectors.transport = self.transport
        self.settings = {'platform_id': 'bdsg_crm', 'url': 'https://crm.bdsg.vn/mcp',
                         'token': 'synthetic-private-write-key', 'read_tools': ['crm.list'],
                         'write_tools': ['crm.delete'], 'allow_writes': True}
        self.app.connectors.save(self.admin, self.settings)
        self.app.connectors.probe(self.admin, 'bdsg_crm')
        self.transport.calls.clear()
        self.now = time.time()
        self.app.actions.clock = lambda: self.now

    def tool(self, actor, name, arguments):
        return self.app.core.goi(actor, name, arguments)

    def task(self, **extra):
        task = self.app.tasks.create(self.member, {'prompt': 'Tong hop du lieu thu nghiem',
            'template': 'tong-quan', 'module_ids': ['bdsg_crm'], **extra})
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            current = self.app.tasks.detail(self.member, task['id'])
            if current['status'] == 'completed':
                return current['id']
            if current['status'] in ('failed', 'cancelled', 'interrupted'):
                self.fail(current['status'])
            time.sleep(.01)
        self.fail('Tac vu khong hoan thanh')

    def proposal(self, **extra):
        response = self.tool(self.member, 'hanh_dong.de_xuat', {'task_id': self.task(**extra),
            'tool': 'ket_noi.ghi', 'arguments': {'platform_id': 'bdsg_crm', 'tool': 'crm.delete',
                                              'arguments': {'record_id': 'synthetic-record-only'}}})
        self.assertTrue(response['ok'], response)
        return response['ket_qua']

    def decision(self, action, approve=True, actor=None):
        return self.tool(actor or self.admin, 'hanh_dong.duyet',
            {'id': action['id'], 'digest': action['digest'], 'approve': approve})

    def writes(self):
        return [item for item in self.transport.calls if item[2] == 'tools/call']

    def test_member_de_xuat_admin_duyet_dung_payload_qua_nhan_mot_lan(self):
        action = self.proposal()
        self.assertEqual(action['status'], 'awaiting')
        self.assertEqual(self.writes(), [])
        result = self.decision(action)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['ket_qua']['status'], 'completed')
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][3], {'name': 'crm.delete', 'arguments': {'record_id': 'synthetic-record-only'}})
        self.assertNotIn(self.settings['token'], json.dumps(result))
        self.assertFalse(self.decision(action)['ok'])
        self.assertEqual(len(self.writes()), 1)

    def test_ghi_truc_tiep_va_json_smuggle_bi_chan_ke_ca_admin(self):
        args = {'platform_id': 'bdsg_crm', 'tool': 'crm.delete', 'arguments': {}}
        for extra in ({}, {'tool_guard': True}, {'expected_revision': 'pretend'}, {'approval': 'pretend'}):
            self.assertFalse(self.tool(self.admin, 'ket_noi.ghi', {**args, **extra})['ok'])
        with self.assertRaises(PermissionError):
            self.app.connectors.call(self.admin, **args, ghi=True)
        self.assertEqual(self.writes(), [])

    def test_member_va_owner_la_member_khong_duyet_duoc(self):
        action = self.proposal()
        self.assertFalse(self.decision(action, actor=self.member)['ok'])
        self.app.units.set_member(OWNER, {'unit_id': self.unit, 'identity': OWNER['id'], 'role': 'member'})
        root_member = self.app.units.bind(OWNER, self.unit)
        self.assertFalse(self.decision(action, actor=root_member)['ok'])
        self.assertEqual(self.writes(), [])

    def test_doi_digest_het_han_va_tu_choi_khong_gui_mang(self):
        action = self.proposal()
        self.assertFalse(self.tool(self.admin, 'hanh_dong.duyet', {
            'id': action['id'], 'digest': '0'*64, 'approve': True})['ok'])
        self.now += 901
        self.assertFalse(self.decision(action)['ok'])
        rejected = self.decision(action, approve=False)
        self.assertTrue(rejected['ok'], rejected)
        self.assertEqual(rejected['ket_qua']['status'], 'rejected')
        self.assertEqual(self.writes(), [])

    def test_hai_don_vi_khong_xem_hoac_duyet_action_cua_nhau(self):
        action = self.proposal()
        unit_b = self.app.units.create(OWNER, {'name': 'Don vi thu B', 'admin': ADMIN['id']})['id']
        actor_b = self.app.units.bind(ADMIN, unit_b)
        self.assertEqual(self.app.actions.list(actor_b), {'actions': []})
        with self.assertRaises(PermissionError):
            self.app.actions.get(actor_b, action['id'])
        self.assertFalse(self.decision(action, actor=actor_b)['ok'])
        self.assertEqual(self.writes(), [])

    def test_admin_khong_tu_co_quyen_du_an_rieng_cua_member(self):
        project = self.app.projects.create(self.member, {'name': 'Du an rieng thu'})['id']
        action = self.proposal(project_id=project)
        self.assertEqual(self.app.actions.list(self.admin), {'actions': []})
        self.assertFalse(self.decision(action)['ok'])
        self.app.projects.share(self.member, {'id': project, 'identity': ADMIN['id'], 'role': 'viewer'})
        self.assertEqual(len(self.app.actions.list(self.admin)['actions']), 1)
        self.assertEqual(self.decision(action)['ket_qua']['status'], 'completed')

    def test_duyet_song_song_chi_gui_mot_yeu_cau(self):
        action = self.proposal()
        barrier = threading.Barrier(2)
        def decide():
            barrier.wait(timeout=3)
            return self.decision(action)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: decide(), range(2)))
        self.assertEqual(sum(bool(result['ok']) for result in results), 1)
        self.assertEqual(len(self.writes()), 1)

    def test_thu_hoi_va_them_lai_nguoi_de_xuat_khong_khoi_phuc_de_xuat_cu(self):
        action = self.proposal()
        change = {'unit_id': self.unit, 'identity': MEMBER['id']}
        self.app.units.set_member(OWNER, {**change, 'role': 'revoke'})
        self.app.units.set_member(OWNER, {**change, 'role': 'member'})
        self.assertFalse(self.decision(action)['ok'])
        self.assertEqual(self.writes(), [])

    def test_doi_khoa_hoac_ngat_sau_de_xuat_can_de_xuat_moi(self):
        action = self.proposal()
        self.app.connectors.save(self.admin, {**self.settings, 'token': 'synthetic-new-key'})
        self.app.connectors.probe(self.admin, 'bdsg_crm')
        self.assertFalse(self.decision(action)['ok'])
        self.assertEqual(self.writes(), [])

    def test_mat_quyen_nguoi_duyet_truoc_send_khong_gui_va_khong_retry(self):
        action = self.proposal()
        def revoke():
            self.app.units.set_member(OWNER, {'unit_id': self.unit, 'identity': ADMIN['id'], 'role': 'member'})
        self.transport.before_send = revoke
        result = self.decision(action)
        self.assertFalse(result['ok'])
        self.assertEqual(self.writes(), [])
        self.member = self.app.units.bind(MEMBER, self.unit)
        self.assertEqual(self.app.actions.get(self.member, action['id'])['status'], 'unknown')

    def test_loi_sau_gui_khong_lo_chung_thu_va_khong_gui_lai(self):
        action = self.proposal()
        def fail():
            raise OSError(self.settings['token'])
        self.transport.after_send = fail
        result = self.decision(action)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['ket_qua']['status'], 'unknown')
        self.assertNotIn(self.settings['token'], json.dumps(result))
        self.assertFalse(self.decision(action)['ok'])
        self.assertEqual(len(self.writes()), 1)

    def test_cau_hinh_khong_tron_cong_cu_ghi_vao_duong_doc(self):
        with self.assertRaises(ValueError):
            self.app.connectors.save(self.admin, {**self.settings, 'read_tools': ['crm.delete']})
        self.assertEqual(self.app.connectors.summary(self.member)[0]['write_tools'], [])
        self.assertFalse(self.tool(self.member, 'ket_noi.doc', {
            'platform_id': 'bdsg_crm', 'tool': 'crm.delete', 'arguments': {}})['ok'])
        self.assertEqual(self.writes(), [])

    def test_thu_hoi_trong_initialize_chan_tools_call_thuc_te(self):
        action = self.proposal()
        exchange, methods = Exchange(), []
        def request(*args):
            response = exchange(*args)
            if args[5]:
                method = json.loads(args[5])['method']
                methods.append(method)
                if method == 'initialize':
                    self.app.units.set_member(OWNER, {'unit_id': self.unit, 'identity': MEMBER['id'], 'role': 'revoke'})
            return response
        self.app.connectors.transport = TruyenTaiMCP(
            resolver=lambda *_args, **_kw: [(2, 1, 6, '', ('1.1.1.1', 443))], exchange=request)
        response = self.decision(action)
        self.assertTrue(response['ok'], response)
        self.assertEqual(response['ket_qua']['status'], 'unknown')
        self.assertEqual(methods, ['initialize'])

    def test_restart_khong_replay_claim_dang_thuc_thi(self):
        action = self.proposal()
        entered, release = threading.Event(), threading.Event()
        def pending():
            entered.set()
            if not release.wait(5):
                raise TimeoutError('synthetic-wait')
        self.transport.before_send = pending
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.decision, action)
            try:
                self.assertTrue(entered.wait(3))
                recovered = HanhDongDonVi(self.app.kho, self.app.core, self.app.tasks,
                                          self.app.units, self.app.connectors)
                self.assertEqual(recovered.get(self.admin, action['id'])['status'], 'unknown')
            finally:
                release.set()
            response = future.result(timeout=5)
        self.assertEqual(response['ket_qua']['status'], 'unknown')
        self.assertEqual(self.writes(), [])
        self.assertFalse(self.decision(action)['ok'])

    def test_hai_don_vi_duyet_song_song_khong_tron_chung_thu(self):
        first = self.proposal()
        unit_b = self.app.units.create(OWNER, {'name': 'Don vi thu B', 'admin': ADMIN['id']})['id']
        self.app.units.set_member(OWNER, {'unit_id': unit_b, 'identity': MEMBER['id'], 'role': 'member'})
        admin_b = self.app.units.bind(ADMIN, unit_b)
        self.member = self.app.units.bind(MEMBER, unit_b)
        self.app.connectors.save(admin_b, {**self.settings, 'url': 'https://crm-b.bdsg.vn/mcp',
                                          'token': 'synthetic-private-write-key-b'})
        self.app.connectors.probe(admin_b, 'bdsg_crm')
        self.transport.calls.clear()
        second = self.proposal()
        barrier = threading.Barrier(2)
        self.transport.before_send = lambda: barrier.wait(timeout=3)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.decision, action, True, actor)
                       for action, actor in ((first, self.admin), (second, admin_b))]
            results = [future.result(timeout=5) for future in futures]
        self.assertTrue(all(result['ok'] and result['ket_qua']['status'] == 'completed' for result in results), results)
        self.assertEqual({(call[0], call[1]) for call in self.writes()}, {
            ('https://crm.bdsg.vn/mcp', 'synthetic-private-write-key'),
            ('https://crm-b.bdsg.vn/mcp', 'synthetic-private-write-key-b')})

    def test_huy_tac_vu_da_hoan_thanh_cung_huy_du_thao_chua_gui(self):
        action = self.proposal()
        self.app.tasks.cancel(self.member, action['task_id'])
        self.assertEqual(self.app.actions.get(self.member, action['id'])['status'], 'cancelled')
        self.assertFalse(self.decision(action)['ok'])
        self.assertEqual(self.writes(), [])
        denied = self.tool(self.member, 'hanh_dong.de_xuat', {
            'task_id': action['task_id'], 'tool': 'ket_noi.ghi', 'arguments': action['payload']['arguments']})
        self.assertFalse(denied['ok'])

    def test_mcp_bao_is_error_khong_duoc_nhan_la_hoan_thanh_nghiep_vu(self):
        action = self.proposal()
        delegate = self.transport.goi
        def business_error(*args):
            delegate(*args)
            return {'isError': True, 'content': [{'type': 'text', 'text': 'synthetic-business-error'}]}
        self.transport.goi = business_error
        response = self.decision(action)
        self.assertEqual(response['ket_qua']['status'], 'unknown')
        self.assertEqual(len(self.writes()), 1)
        self.assertFalse(self.decision(action)['ok'])

    def test_luot_moi_khong_dung_phe_duyet_cua_luot_cu(self):
        action = self.proposal()
        self.app.tasks.followup(self.member, action['task_id'], 'Bo sung yeu cau thu nghiem')
        self.assertFalse(self.decision(action)['ok'])
        self.assertEqual(self.writes(), [])

    def test_het_han_truoc_send_khong_gui_mang(self):
        action = self.proposal()
        def expire(): self.now += 901
        self.transport.before_send = expire
        response = self.decision(action)
        self.assertEqual(response['ket_qua']['status'], 'unknown')
        self.assertEqual(self.writes(), [])

    def test_huy_khi_dang_thuc_thi_chan_gui_tiep_va_giu_unknown(self):
        action = self.proposal()
        self.transport.before_send = lambda: self.app.tasks.cancel(self.member, action['task_id'])
        response = self.decision(action)
        self.assertEqual(response['ket_qua']['status'], 'unknown')
        self.assertEqual(self.writes(), [])

    def test_thu_hoi_quyen_du_an_nguoi_duyet_truoc_send_chan_gui(self):
        project = self.app.projects.create(self.member, {'name': 'Du an thu phan quyen'})['id']
        grant = {'id': project, 'identity': ADMIN['id']}
        self.app.projects.share(self.member, {**grant, 'role': 'viewer'})
        action = self.proposal(project_id=project)
        self.transport.before_send = lambda: self.app.projects.share(self.member, {**grant, 'role': 'revoke'})
        self.assertFalse(self.decision(action)['ok'])
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.app.actions.get(self.member, action['id'])['status'], 'unknown')

    def test_snapshot_restore_action_va_grant_chung_thu_nhat_quan(self):
        action = self.proposal()
        with tempfile.TemporaryDirectory() as directory:
            bundle, target = Path(directory)/'bundle', Path(directory)/'restored'
            backup(self.app.kho.root, bundle)
            restore(bundle, target)
            restored = UngDung(target/'data', 'https://preview.test', True, unit_preview=True)
            try:
                fresh_admin = restored.units.bind(ADMIN, self.unit)
                fresh_member = restored.units.bind(MEMBER, self.unit)
                self.assertEqual(restored.actions.get(fresh_member, action['id'])['digest'], action['digest'])
                with self.assertRaises(PermissionError):
                    restored.actions.get(self.member, action['id'])
                transport = TransportTongHop()
                restored.connectors.transport = transport
                response = restored.core.goi(fresh_admin, 'hanh_dong.duyet', {
                    'id': action['id'], 'digest': action['digest'], 'approve': True})
                self.assertTrue(response['ok'], response)
                self.assertEqual(response['ket_qua']['status'], 'completed')
                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(transport.calls[0][1], 'synthetic-private-write-key')
                self.assertNotIn('synthetic-private-write-key', json.dumps(response))
            finally:
                restored.tasks.close()
                restored.core.audit.close()

    def test_unknown_chan_de_xuat_va_action_da_cho_den_khi_admin_doi_soat(self):
        first, queued = self.proposal(), self.proposal()
        def fail(): raise OSError('synthetic-no-confirmation')
        self.transport.after_send = fail
        self.assertEqual(self.decision(first)['ket_qua']['status'], 'unknown')
        self.transport.after_send = lambda: None
        self.assertFalse(self.decision(queued)['ok'])
        duplicate = {'task_id': first['task_id'], 'tool': 'ket_noi.ghi',
                     'arguments': first['payload']['arguments']}
        self.assertFalse(self.tool(self.member, 'hanh_dong.de_xuat', duplicate)['ok'])
        args = {'id': first['id'], 'digest': first['digest'], 'outcome': 'not-applied',
                'note': 'Da doi soat nguon tong hop, chua thuc hien.'}
        self.assertFalse(self.tool(self.member, 'hanh_dong.doi_soat', args)['ok'])
        self.assertFalse(self.tool(self.admin, 'hanh_dong.doi_soat', {**args, 'digest': 'wrong'})['ok'])
        self.assertEqual(len(self.writes()), 1)
        result = self.tool(self.admin, 'hanh_dong.doi_soat', args)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['ket_qua']['status'], 'reconciled-not-applied')
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.decision(queued)['ket_qua']['status'], 'completed')
        self.assertEqual(len(self.writes()), 2)


if __name__ == '__main__':
    unittest.main()
