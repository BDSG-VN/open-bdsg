"""Agent chỉ lập dự thảo theo grant; provider HTTP tổng hợp, không ghi MCP."""
import json
import tempfile
import time
import unittest

from may_chu import UngDung
from trung_tam_ai import MoHinhLiteLLM
from thu_ai_don_vi import config
from thu_mo_hinh_bdsg import Response, answer, call
from thu_dau_noi_don_vi import TransportTongHop

OWNER = {'id': 'chu-quan', 'name': 'Chu quan thu', 'role': 'quan-tri'}
USER = {'id': 'agent-draft-user', 'name': 'Nguoi thu', 'role': 'operator'}


class ThuAgentDuThaoDonVi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.requests, self.hook = [], lambda: None
        self.function, self.write_tool = 'hanh_dong__de_xuat', 'crm.delete'
        owner = self
        class Provider:
            def __init__(self): self.turn = 0
            def open(self, request, timeout):
                body = json.loads(request.data)
                owner.requests.append(body)
                self.turn += 1
                if self.turn == 1:
                    context = json.loads(body['messages'][1]['content'].split('NGỮ CẢNH ĐƯỢC CẤP:\n', 1)[1])
                    owner.hook()
                    arguments = {'task_id': context['task_id'], 'tool': 'ket_noi.ghi',
                                 'arguments': {'platform_id': 'bdsg_crm', 'tool': owner.write_tool,
                                               'arguments': {'record_id': 'synthetic-only'}}}
                    return Response(answer(calls=[call(owner.function, json.dumps(arguments))]))
                return Response(answer('# Đã lập dự thảo thử nghiệm, chưa ghi nghiệp vụ'))
        self.app = UngDung(self.tmp.name, 'https://preview.test', True, unit_preview=True,
            unit_ai_probe=lambda *_: True,
            unit_ai_factory=lambda alias, key: MoHinhLiteLLM(alias, key, opener=Provider()))
        self.addCleanup(self.app.core.audit.close)
        self.addCleanup(self.app.tasks.close)
        self.app.kho.tao_chu('synthetic-password-only')
        self.app.kho.tao_agent(USER['id'], USER['name'], 'operator')
        self.unit = self.app.units.create(OWNER, {'name': 'Don vi thu agent', 'admin': USER['id']})['id']
        self.app.units.set_member(OWNER, {'unit_id': self.unit, 'identity': OWNER['id'], 'role': 'admin'})
        self.actor = self.app.units.bind(USER, self.unit)
        self.app.unit_ai.save(self.actor, config())
        self.transport = TransportTongHop()
        self.app.connectors.transport = self.transport
        self.settings = {'platform_id': 'bdsg_crm', 'url': 'https://crm.bdsg.vn/mcp',
                         'token': 'synthetic-agent-draft-token', 'read_tools': ['crm.list'],
                         'write_tools': ['crm.delete'], 'allow_writes': True}
        self.app.connectors.save(self.actor, self.settings)
        self.app.connectors.probe(self.actor, 'bdsg_crm')
        self.transport.calls.clear()

    def create(self, **extra):
        return self.app.tasks.create(self.actor, {'prompt': 'Lap de xuat CRM thu nghiem, chua thuc hien',
            'template': 'tong-quan', 'module_ids': ['bdsg_crm'], 'allow_action_drafts': True, **extra})['id']

    def finished(self, identifier):
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            task = self.app.tasks.detail(self.actor, identifier)
            if task['status'] in ('completed', 'cancelled', 'failed', 'interrupted'): return task
            time.sleep(.01)
        self.fail('Tac vu khong dung')

    def test_agent_member_co_opt_in_chi_tao_du_thao_khong_gui_tools_call(self):
        self.app.units.set_member(OWNER, {'unit_id': self.unit, 'identity': USER['id'], 'role': 'member'})
        self.actor = self.app.units.bind(USER, self.unit)
        task = self.finished(self.create())
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['allowed_module_write_tools'], {'bdsg_crm': ['crm.delete']})
        actions = self.app.actions.list(self.actor)['actions']
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['status'], 'awaiting')
        self.assertEqual(actions[0]['payload']['run'], task['run'])
        self.assertEqual(self.transport.calls, [])
        names = {tool['function']['name'] for tool in self.requests[0]['tools']}
        self.assertIn('hanh_dong__de_xuat', names)
        self.assertTrue(names.isdisjoint({'ket_noi__ghi', 'hanh_dong__duyet', 'hanh_dong__doi_soat'}))
        self.assertNotIn('synthetic-agent-draft-token', json.dumps([self.requests, task, actions]))

    def test_khong_opt_in_khong_co_cong_cu_du_thao(self):
        task = self.finished(self.create(allow_action_drafts=False))
        self.assertEqual(task['status'], 'failed')
        self.assertEqual(self.app.actions.list(self.actor), {'actions': []})
        self.assertNotIn('hanh_dong__de_xuat', {item['function']['name'] for item in self.requests[0]['tools']})

    def test_tool_khong_co_trong_snapshot_khong_duoc_de_xuat(self):
        self.write_tool = 'crm.create'
        self.assertEqual(self.finished(self.create())['status'], 'failed')
        self.assertEqual(self.app.actions.list(self.actor), {'actions': []})
        self.assertEqual(self.transport.calls, [])

    def test_agent_khong_duoc_duyet_hoac_doi_soat(self):
        for function in ('hanh_dong__duyet', 'hanh_dong__doi_soat', 'ket_noi__ghi'):
            self.function = function
            self.assertEqual(self.finished(self.create())['status'], 'failed')
        self.assertEqual(self.app.actions.list(self.actor), {'actions': []})
        self.assertEqual(self.transport.calls, [])

    def test_doi_connector_sau_provider_chan_du_thao_tu_grant_cu(self):
        def rotate():
            self.app.connectors.save(self.actor, {**self.settings, 'token': 'synthetic-new-token'})
            self.app.connectors.probe(self.actor, 'bdsg_crm')
            self.transport.calls.clear()
        self.hook = rotate
        self.assertEqual(self.finished(self.create())['status'], 'failed')
        self.assertEqual(self.app.actions.list(self.actor), {'actions': []})
        self.assertEqual(self.transport.calls, [])

    def test_followup_khong_tu_mo_rong_write_tools_hoac_revision(self):
        identifier = self.create()
        self.assertEqual(self.finished(identifier)['status'], 'completed')
        self.app.connectors.save(self.actor, self.settings)
        self.app.connectors.probe(self.actor, 'bdsg_crm')
        self.transport.calls.clear()
        self.app.tasks.followup(self.actor, identifier, 'Lap de xuat tiep theo trong grant ban dau')
        self.assertEqual(self.finished(identifier)['status'], 'failed')
        self.assertEqual(len(self.app.actions.list(self.actor)['actions']), 1)
        self.assertEqual(self.transport.calls, [])

    def test_doi_ai_sau_provider_khong_duoc_luu_du_thao(self):
        self.hook = lambda: self.app.unit_ai.save(self.actor, config())
        self.assertEqual(self.finished(self.create())['status'], 'failed')
        self.assertEqual(self.app.actions.list(self.actor), {'actions': []})
        self.assertEqual(self.transport.calls, [])


if __name__ == '__main__':
    unittest.main()
