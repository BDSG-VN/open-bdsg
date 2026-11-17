"""Nguồn grant qua AI/MCP/dự thảo thật trong gateway; transport tổng hợp."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

import thu_agent_du_thao_don_vi as fixture
from may_chu import UngDung
from mcp_uy_quyen_don_vi import LoiChungThuMCP
from sao_luu_he_thong import backup, restore
from thu_ai_don_vi import config
from thu_mo_hinh_bdsg import Response, answer, call
from trung_tam_ai import MoHinhLiteLLM


class ThuMCPMoDunDonVi(unittest.TestCase):
    def setUp(self):
        fixture.ThuAgentDuThaoDonVi.setUp(self)
        self.service = self.app.inbound_mcp
        self.now = time.time()
        self.service.clock = lambda: self.now

    def issue(self, actor=None, **profile):
        return self.service.create(actor or self.actor, {'name': 'Client mo dun thu', 'client_id': 'synthetic-module',
            'tools': ['cong_viec.tao', 'cong_viec.tiep_tuc', 'cong_viec.dung'],
            'project_ids': [''], 'expires_in': 900,
            'task_profile': {'allow_ai': True, 'module_drafts': {'bdsg_crm': ['crm.delete']}, **profile}})

    def create(self, issued, **extra):
        actor = self.service.authenticate(issued['credential'])
        result = self.service.call(actor, 'cong_viec.tao', {'prompt': 'Lap de xuat CRM trong nguon uy quyen',
            'template': 'tong-quan', 'module_ids': ['bdsg_crm'], 'allow_action_drafts': True, **extra})
        self.assertTrue(result['ok'], result)
        return result['ket_qua']['id']

    def finished(self, identifier, actor=None):
        until = time.monotonic()+5
        while time.monotonic() < until:
            task = self.app.tasks.detail(actor or self.actor, identifier)
            if task['status'] in ('completed', 'failed', 'interrupted', 'cancelled'): return task
            time.sleep(.01)
        self.fail('Worker khong ket thuc')

    def proposal(self, issued=None):
        issued = issued or self.issue()
        task = self.finished(self.create(issued))
        self.assertEqual(task['status'], 'completed')
        actions = self.app.actions.list(self.actor)['actions']
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['status'], 'awaiting')
        return issued, actions[0]

    def decide(self, action, actor=None):
        return self.app.core.goi(actor or self.actor, 'hanh_dong.duyet',
            {'id': action['id'], 'digest': action['digest'], 'approve': True})

    def writes(self):
        return [item for item in self.transport.calls if item[2] == 'tools/call']

    def read_provider(self):
        owner = self
        class Provider:
            def __init__(self): self.turn = 0
            def open(self, request, timeout):
                body = json.loads(request.data)
                owner.requests.append(body)
                self.turn += 1
                if self.turn == 1:
                    owner.hook()
                    return Response(answer(calls=[call('ket_noi__doc', json.dumps({
                        'platform_id': 'bdsg_crm', 'tool': 'crm.list', 'arguments': {}}))]))
                return Response(answer('# MODULE-READ-COMPLETED'))
        self.app.unit_ai.factory = lambda alias, key: MoHinhLiteLLM(alias, key, opener=Provider())

    def test_agent_tao_du_thao_admin_duyet_qua_nhan_chi_gui_mot_lan(self):
        issued, action = self.proposal()
        self.assertEqual(action['payload']['mcp_source'], {'id': issued['id'], 'revision': issued['revision']})
        self.assertEqual(self.writes(), [])
        token_actor = self.service.authenticate(issued['credential'])
        for name in ('hanh_dong.duyet', 'hanh_dong.doi_soat', 'ket_noi.ghi', 'cau_hinh.luu_dau_noi'):
            with self.subTest(name=name), self.assertRaises(PermissionError):
                self.service.call(token_actor, name, {})
        result = self.decide(action)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['ket_qua']['status'], 'completed')
        self.assertEqual(len(self.writes()), 1)
        self.assertFalse(self.decide(action)['ok'])
        self.assertEqual(len(self.writes()), 1)
        self.assertNotIn(issued['credential'], json.dumps([self.requests, action, result]))
        self.assertNotIn(self.settings['token'], json.dumps([self.requests, action, result]))

    def test_thu_hoi_sau_du_thao_chan_duyet_va_token_moi_khong_hoi_sinh(self):
        issued, action = self.proposal()
        self.service.revoke(self.actor, issued['id'])
        self.issue()
        self.assertFalse(self.decide(action)['ok'])
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.app.actions.get(self.actor, action['id'])['status'], 'awaiting')

    def test_het_han_sau_du_thao_chan_duyet(self):
        _, action = self.proposal()
        self.now += 901
        self.assertFalse(self.decide(action)['ok'])
        self.assertEqual(self.writes(), [])

    def test_thu_hoi_sau_kiem_owner_truoc_claim_khong_chuyen_executing(self):
        issued, action = self.proposal()
        original = self.app.connectors.prepare_write
        def revoke_after_check(actor, platform, tool):
            result = original(actor, platform, tool)
            self.service.revoke(self.actor, issued['id'])
            return result
        self.app.connectors.prepare_write = revoke_after_check
        self.assertFalse(self.decide(action)['ok'])
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.app.actions.get(self.actor, action['id'])['status'], 'awaiting')

    def test_thu_hoi_sau_owner_check_truoc_insert_khong_luu_du_thao(self):
        issued = self.issue()
        original, count = self.app.connectors.prepare_write, [0]
        def revoke_before_insert(actor, platform, tool):
            result = original(actor, platform, tool)
            count[0] += 1
            if count[0] == 2: self.service.revoke(self.actor, issued['id'])
            return result
        self.app.connectors.prepare_write = revoke_before_insert
        task = self.finished(self.create(issued))
        self.assertEqual(task['status'], 'failed')
        self.assertEqual(count[0], 2)
        self.assertEqual(self.app.actions.list(self.actor)['actions'], [])
        self.assertEqual(self.writes(), [])

    def test_thu_hoi_ngay_truoc_send_chan_gui_va_giu_unknown(self):
        issued, action = self.proposal()
        self.transport.before_send = lambda: self.service.revoke(self.actor, issued['id'])
        result = self.decide(action)
        self.assertTrue(result['ok'])
        self.assertEqual(result['ket_qua']['status'], 'unknown')
        self.assertEqual(self.writes(), [])
        self.assertFalse(self.decide(action)['ok'])

    def test_thu_hoi_sau_send_khong_nhan_hoan_thanh_hoac_retry(self):
        issued, action = self.proposal()
        self.transport.after_send = lambda: self.service.revoke(self.actor, issued['id'])
        result = self.decide(action)
        self.assertTrue(result['ok'])
        self.assertEqual(result['ket_qua']['status'], 'unknown')
        self.assertEqual(len(self.writes()), 1)
        self.assertFalse(self.decide(action)['ok'])
        self.assertEqual(len(self.writes()), 1)

    def final_response_change(self, change):
        issued, action = self.proposal()
        original = self.app.core.goi
        fired = []
        class LateResponse(dict):
            def get(response, key, default=None):
                # Adapter nhân trả kết quả lazy: thay đổi sau guard mạng cuối,
                # trước giao dịch xuất bản; bài kiểm vẫn gọi interface decide.
                if key == 'ket_qua' and not fired:
                    fired.append(True)
                    change(issued)
                return super().get(key, default)
        def delayed(actor, name, arguments, **options):
            result = original(actor, name, arguments, **options)
            return LateResponse(result) if name == 'ket_noi.ghi' else result
        self.app.core.goi = delayed
        result = self.decide(action)
        self.assertTrue(result['ok'])
        self.assertEqual(fired, [True])
        self.assertEqual(result['ket_qua']['status'], 'unknown')
        stored = self.app.actions.get(self.actor, action['id'])
        self.assertEqual(stored['status'], 'unknown')
        self.assertNotIn(self.settings['url'], json.dumps(stored['result']))
        self.assertEqual(len(self.writes()), 1)
        self.assertFalse(self.decide(action)['ok'])
        self.assertEqual(len(self.writes()), 1)

    def test_thu_hoi_sau_guard_cuoi_truoc_commit_khong_luu_response(self):
        self.final_response_change(lambda issued: self.service.revoke(self.actor, issued['id']))

    def test_het_han_sau_guard_cuoi_truoc_commit_khong_luu_response(self):
        def expire(_issued): self.now += 901
        self.final_response_change(expire)

    def test_doi_connector_sau_guard_cuoi_truoc_commit_khong_luu_response(self):
        self.final_response_change(lambda _issued: self.app.connectors.save(self.actor, self.settings))

    def test_doc_mcp_dung_profile_va_gui_qua_guard_nhan(self):
        self.read_provider()
        issued = self.issue(module_drafts={}, module_reads={'bdsg_crm': ['crm.list']})
        task = self.finished(self.create(issued, allow_action_drafts=False, allow_module_reads=True))
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['allowed_module_tools'], {'bdsg_crm': ['crm.list']})
        self.assertEqual(task['allowed_module_write_tools'], {})
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][3]['name'], 'crm.list')
        self.assertEqual(self.app.actions.list(self.actor)['actions'], [])

    def test_thu_hoi_sau_doc_mcp_chan_ket_qua_va_artifact(self):
        self.read_provider()
        issued = self.issue(module_drafts={}, module_reads={'bdsg_crm': ['crm.list']})
        self.transport.after_send = lambda: self.service.revoke(self.actor, issued['id'])
        task = self.finished(self.create(issued, allow_action_drafts=False, allow_module_reads=True))
        self.assertEqual(task['status'], 'failed')
        self.assertEqual(task['artifacts'], [])
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(len(self.requests), 1)

    def test_thu_hoi_luc_provider_tra_tool_khong_luu_du_thao(self):
        issued = self.issue()
        self.hook = lambda: self.service.revoke(self.actor, issued['id'])
        task = self.finished(self.create(issued))
        self.assertEqual(task['status'], 'failed')
        self.assertEqual(self.app.actions.list(self.actor)['actions'], [])
        self.assertEqual(self.writes(), [])

    def test_khong_cap_tool_chua_co_khong_wildcard_va_khong_ghi_thanh_doc(self):
        for profile in ({'module_reads': {'bdsg_crm': ['crm.delete']}},
                        {'module_drafts': {'bdsg_crm': ['crm.list']}},
                        {'module_reads': {'bdsg_crm': ['*']}},
                        {'module_drafts': {'bdsg_crm': ['crm.create']}},
                        {'module_reads': {'unknown': ['crm.list']}}):
            with self.subTest(profile=profile), self.assertRaises((PermissionError, ValueError)):
                self.issue(**profile)
        self.assertEqual(self.service.list(self.actor)['grants'], [])

    def test_doi_connector_khong_tu_cap_them_cho_token_followup_cu(self):
        issued, action = self.proposal()
        self.app.connectors.save(self.actor, self.settings)
        self.app.connectors.probe(self.actor, 'bdsg_crm')
        self.transport.calls.clear()
        with self.assertRaises(LoiChungThuMCP): self.service.authenticate(issued['credential'])
        self.assertFalse(self.decide(action)['ok'])
        self.assertEqual(self.writes(), [])

    def test_task_chi_chup_tap_con_tool_da_cap_khong_lay_het_connector(self):
        original = self.transport.goi
        def discovery(config, method, parameters, guard):
            result = original(config, method, parameters, guard)
            if method == 'tools/list':
                result['tools'].extend([{'name': 'crm.more'}, {'name': 'crm.update'}])
            return result
        self.transport.goi = discovery
        self.app.connectors.save(self.actor, {**self.settings, 'read_tools': ['crm.list', 'crm.more'],
                                               'write_tools': ['crm.delete', 'crm.update']})
        self.app.connectors.probe(self.actor, 'bdsg_crm')
        self.transport.calls.clear()
        issued = self.issue(module_reads={'bdsg_crm': ['crm.list']})
        task = self.finished(self.create(issued, allow_module_reads=True))
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['allowed_module_tools'], {'bdsg_crm': ['crm.list']})
        self.assertEqual(task['allowed_module_write_tools'], {'bdsg_crm': ['crm.delete']})
        self.write_tool = 'crm.update'
        self.assertEqual(self.finished(self.create(issued))['status'], 'failed')
        self.assertEqual(len(self.app.actions.list(self.actor)['actions']), 1)
        self.assertEqual(self.writes(), [])

    def test_member_lap_du_thao_nhung_can_admin_duyet(self):
        self.app.units.set_member(fixture.OWNER, {'unit_id': self.unit, 'identity': fixture.USER['id'], 'role': 'member'})
        self.actor = self.app.units.bind(fixture.USER, self.unit)
        _, action = self.proposal()
        self.assertFalse(self.decide(action)['ok'])
        admin = self.app.units.bind(fixture.OWNER, self.unit)
        result = self.decide(action, admin)
        self.assertTrue(result['ok'])
        self.assertEqual(result['ket_qua']['status'], 'completed')
        self.assertEqual(len(self.writes()), 1)

    def test_hai_don_vi_cung_identity_worker_khong_tron_nguon_va_chung_thu(self):
        second = self.app.units.create(fixture.OWNER, {'name': 'Don vi MCP thu B', 'admin': fixture.USER['id']})['id']
        actor_b = self.app.units.bind(fixture.USER, second)
        self.app.unit_ai.save(actor_b, config())
        settings_b = {**self.settings, 'url': 'https://crm-b.bdsg.vn/mcp', 'token': 'synthetic-only-unit-b'}
        self.app.connectors.save(actor_b, settings_b)
        self.app.connectors.probe(actor_b, 'bdsg_crm')
        self.transport.calls.clear()
        issued_a, issued_b = self.issue(), self.issue(actor_b)
        barrier = threading.Barrier(2)
        self.hook = lambda: barrier.wait(timeout=3)
        first, other = self.create(issued_a), self.create(issued_b)
        self.assertEqual(self.finished(first)['status'], 'completed')
        self.assertEqual(self.finished(other, actor_b)['status'], 'completed')
        action_a = self.app.actions.list(self.actor)['actions'][0]
        action_b = self.app.actions.list(actor_b)['actions'][0]
        self.assertEqual(action_a['payload']['mcp_source']['id'], issued_a['id'])
        self.assertEqual(action_b['payload']['mcp_source']['id'], issued_b['id'])
        self.assertFalse(self.decide(action_b)['ok'])
        self.assertTrue(self.decide(action_a)['ok'])
        self.assertTrue(self.decide(action_b, actor_b)['ok'])
        self.assertEqual(len(self.writes()), 2)
        self.assertEqual({row[0] for row in self.writes()}, {self.settings['url'], settings_b['url']})

    def test_web_khong_tu_lap_du_thao_thay_nguon_token(self):
        _, action = self.proposal()
        with self.assertRaises(PermissionError):
            self.app.actions.propose(self.actor, {'task_id': action['task_id'], 'tool': 'ket_noi.ghi',
                                                 'arguments': action['payload']['arguments']})
        self.assertEqual(len(self.app.actions.list(self.actor)['actions']), 1)

    def test_restore_du_thao_khong_hoi_sinh_nguon_snapshot_cu(self):
        issued, action = self.proposal()
        with tempfile.TemporaryDirectory() as folder:
            bundle, target = Path(folder)/'bundle', Path(folder)/'restored'
            backup(self.app.kho.root, bundle)
            self.service.revoke(self.actor, issued['id'])
            restore(bundle, target)
            restored = UngDung(target/'data', 'https://preview.test', True, unit_preview=True)
            restored.connectors.transport = self.transport
            try:
                web = restored.units.bind(fixture.USER, self.unit)
                result = restored.core.goi(web, 'hanh_dong.duyet',
                    {'id': action['id'], 'digest': action['digest'], 'approve': True})
                self.assertFalse(result['ok'])
                self.assertEqual(self.writes(), [])
                self.assertEqual(restored.actions.get(web, action['id'])['status'], 'awaiting')
            finally:
                restored.tasks.close(); restored.core.audit.close()


if __name__ == '__main__': unittest.main()
