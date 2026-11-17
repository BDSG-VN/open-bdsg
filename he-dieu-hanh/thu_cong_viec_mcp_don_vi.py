"""Task MCP qua nhân thật, provider/HTTP tổng hợp, không gọi mạng."""
import json
import tempfile
import threading
import time
import unittest

from kho import Kho
from don_vi import DonVi
from du_an import DuAn
from dieu_phoi import DieuPhoi
from cong_viec import CongViec
from dau_noi_don_vi import DauNoiDonVi
from ai_don_vi import AITheoDonVi
from trung_tam_ai import MoHinhLiteLLM
from thu_ai_don_vi import config
from thu_cong_viec import A, OWNER, NhanThu
from thu_dau_noi_don_vi import TransportTongHop
from mcp_truyen_tai import TruyenTaiMCP
from thu_mcp_truyen_tai import Exchange, Response
from thu_mo_hinh_bdsg import Response as ProviderResponse, answer, call


class ThuCongViecMCPDonVi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.kho = Kho(self.tmp.name)
        self.kho.tao_chu('synthetic-password-only')
        self.kho.tao_agent(A['id'], A['name'], 'operator')
        self.units = DonVi(self.kho)
        self.unit = self.units.create(OWNER, {'name': 'Đơn vị thử', 'admin': A['id']})['id']
        self.units.set_member(OWNER, {'unit_id':self.unit, 'identity':OWNER['id'], 'role':'admin'})
        self.actor = self.units.bind(A, self.unit)
        self.core = DieuPhoi(self.kho, NhanThu.catalogue, ghi=True)
        self.addCleanup(self.core.audit.close)
        self.core.nhan.chinh_sach.khai_vai('operator', doc=['nen_tang.danh_sach', 'nen_tang.ket_noi', 'ket_noi.doc'])
        self.transport = TransportTongHop()
        self.connectors = DauNoiDonVi(self.kho, self.units, self.core.catalogue,
            origin='https://thanhhoa.bdsg.vn', transport=self.transport)
        self.core.connection_call = self.connectors.call
        self.core.connection_summary = self.connectors.summary
        self.tasks = CongViec(self.kho, self.core, units=self.units)
        self.addCleanup(self.tasks.close)
        self.tasks.projects = DuAn(self.kho, units=self.units)
        self.tasks.scoped_connectors = self.connectors
        self.requests = []
        self.provider_hook = lambda: None
        self.want_tool = 'crm.list'
        owner = self
        class ProviderTransport:
            def __init__(inner):
                inner.turn = 0
            def open(inner, request, timeout):
                body = json.loads(request.data)
                owner.requests.append((body['messages'], body['tools']))
                inner.turn += 1
                if inner.turn == 1:
                    owner.provider_hook()
                    return ProviderResponse(answer(calls=[call('ket_noi__doc', json.dumps({
                        'platform_id':'bdsg_crm','tool':owner.want_tool,'arguments':{}}))]))
                return ProviderResponse(answer('# Báo cáo tổng hợp thử'))
        self.ai = AITheoDonVi(self.kho, self.units, self.tasks.projects,
            probe=lambda key, aliases: True,
            adapter_factory=lambda alias,key:MoHinhLiteLLM(alias,key,opener=ProviderTransport()))
        self.tasks.scoped_ai = self.ai
        settings = config()
        settings['policy']['tasks_per_user'] = 10
        self.ai.save(self.actor, settings)
        self.settings = {'platform_id':'bdsg_crm', 'url':'https://crm.bdsg.vn/mcp',
            'token':'synthetic-private-connector-token', 'read_tools':['crm.list']}
        self.connectors.save(self.actor, self.settings)
        self.connectors.probe(self.actor, 'bdsg_crm')
        self.transport.calls.clear()

    def create(self, **extra):
        return self.tasks.create(self.actor, {'prompt':'Tổng hợp dữ liệu CRM được cấp rõ ràng',
            'template':'tong-quan', 'module_ids':['bdsg_crm'], 'allow_module_reads':True, **extra})['id']

    def finished(self, identifier, unit=None):
        unit = unit or self.unit
        deadline = time.monotonic()+5
        while time.monotonic()<deadline:
            try:
                self.actor = self.units.bind(A, unit)
                task = self.tasks.detail(self.actor, identifier)
            except PermissionError:
                time.sleep(.01)
                continue
            if task['status'] in ('completed','failed','cancelled','interrupted'): return task
            time.sleep(.01)
        self.fail('Tác vụ không dừng trong thời gian kiểm')

    def test_operator_doc_qua_nhan_va_chup_dung_cong_cu_revision_khong_lo_token(self):
        revision = self.connectors.summary(self.actor)[0]['revision']
        task = self.finished(self.create())
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['allowed_module_tools'], {'bdsg_crm':['crm.list']})
        self.assertEqual(task['module_connector_revisions'], {'bdsg_crm':revision})
        self.assertEqual(len(self.transport.calls), 1)
        self.assertIn('ket_noi.doc', (self.kho.root/'nhat-ky-nhan.jsonl').read_text(encoding='utf-8'))
        self.assertNotIn(self.settings['token'], json.dumps([task, self.requests], ensure_ascii=False))
        self.assertEqual(self.actor['role'], 'operator')

    def test_khong_opt_in_khong_cap_cong_cu_doc_ngoai(self):
        task = self.finished(self.create(allow_module_reads=False))
        self.assertEqual(task['status'], 'failed')
        self.assertEqual(self.transport.calls, [])
        names = {tool['function']['name'] for tool in self.requests[0][1]}
        self.assertNotIn('ket_noi__doc', names)
        self.assertTrue(names <= {'nen_tang__danh_sach', 'nen_tang__ket_noi'})

    def test_followup_khong_mo_rong_quyen_hoac_dung_revision_moi(self):
        identifier = self.create()
        original = self.finished(identifier)
        self.assertEqual(original['status'], 'completed')
        self.connectors.save(self.actor, {**self.settings, 'read_tools':['crm.list','crm.delete']})
        self.connectors.probe(self.actor, 'bdsg_crm')
        self.transport.calls.clear()
        self.tasks.followup(self.actor, identifier, 'Tiếp tục trong đúng phạm vi lần đầu đã giao')
        task = self.finished(identifier)
        self.assertEqual(task['status'], 'failed')
        self.assertEqual(task['allowed_module_tools'], original['allowed_module_tools'])
        self.assertEqual(task['module_connector_revisions'], original['module_connector_revisions'])
        self.assertEqual(self.transport.calls, [])
        self.assertEqual(len(task['artifacts']), 1)

    def test_model_khong_the_goi_cong_cu_khac_da_chup(self):
        self.want_tool = 'crm.delete'
        task = self.finished(self.create())
        self.assertEqual(task['status'], 'failed')
        self.assertEqual(self.transport.calls, [])

    def test_hai_worker_cung_identity_khong_tron_dau_noi_hai_don_vi(self):
        first_unit = self.unit
        other_unit = self.units.create(OWNER, {'name':'Đơn vị song song', 'admin':A['id']})['id']
        other = self.units.bind(A, other_unit)
        other_settings = {**self.settings, 'url':'https://crm-b.bdsg.vn/mcp',
                          'token':'synthetic-other-unit-token'}
        self.ai.save(other, config('synthetic-other-unit-key'))
        self.connectors.save(other, other_settings)
        self.connectors.probe(other, 'bdsg_crm')
        self.transport.calls.clear()
        barrier = threading.Barrier(2)
        self.transport.before_send = lambda: barrier.wait(3)
        first = self.create()
        self.actor = other
        second = self.create()
        one = self.finished(first, first_unit)
        two = self.finished(second, other_unit)
        self.assertEqual([one['status'], two['status']], ['completed','completed'])
        self.assertEqual({row[:2] for row in self.transport.calls}, {
            (self.settings['url'], self.settings['token']), (other_settings['url'], other_settings['token'])})
        self.assertNotEqual(one['module_connector_revisions'], two['module_connector_revisions'])
        self.assertEqual(self.core.connections.config, [])

    def test_member_chi_doc_khi_co_grant_cu_the_khong_muon_vai_quan_tri(self):
        self.units.set_member(OWNER, {'unit_id':self.unit, 'identity':A['id'], 'role':'member'})
        self.actor = self.units.bind(A, self.unit)
        with self.assertRaises(ValueError): self.create()
        root = self.units.bind(OWNER, self.unit)
        self.connectors.save(root, {**self.settings, 'read_roles':['member']})
        self.connectors.probe(root, 'bdsg_crm')
        self.transport.calls.clear()
        result = self.finished(self.create())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.actor['role'], 'operator')
        self.assertEqual(len(self.transport.calls), 1)
        with self.assertRaises(PermissionError): self.connectors.save(self.actor, self.settings)

    def test_doi_cau_hinh_truoc_cong_cu_chan_gui_mcp(self):
        self.provider_hook = lambda: self.connectors.save(self.actor, self.settings)
        self.assertEqual(self.finished(self.create())['status'], 'failed')
        self.assertEqual(self.transport.calls, [])

    def test_task_mcp_handshake_cleanup_va_che_token_trong_du_lieu_upstream(self):
        exchange = Exchange()
        def request(*args):
            response = exchange(*args)
            if args[5]:
                body = json.loads(args[5])
                if body['method'] == 'tools/call':
                    return Response(200, {'jsonrpc':'2.0', 'id':body['id'], 'result':{
                        'content':[{'type':'text','text':'Dữ liệu '+self.settings['token']}]}})
            return response
        self.connectors.transport = TruyenTaiMCP(
            resolver=lambda *a,**k:[(2,1,6,'',('1.1.1.1',443))], exchange=request)
        task = self.finished(self.create())
        self.assertEqual(task['status'], 'completed')
        self.assertEqual([json.loads(row[5])['method'] for row in exchange.requests if row[5]],
                         ['initialize','notifications/initialized','tools/call'])
        self.assertEqual(exchange.requests[-1][3], 'DELETE')
        self.assertNotIn(self.settings['token'], json.dumps([task,self.requests]))
        self.assertIn('CHUNG-THU-DA-CHE', json.dumps(self.requests))

    def test_json_khong_the_truyen_guard_hoac_revision_de_tu_cap_quyen(self):
        for field in ('tool_guard', 'expected_revision'):
            result = self.core.goi(self.actor, 'ket_noi.doc', {
                'platform_id':'bdsg_crm','tool':'crm.list','arguments':{},field:'gia-mao'})
            self.assertFalse(result['ok'])
        self.assertEqual(self.transport.calls, [])

    def test_huy_sau_result_khong_dua_du_lieu_vao_model_hoac_bao_cao(self):
        def cancel():
            identifier = self.tasks.list(self.actor)['tasks'][0]['id']
            self.tasks.cancel(self.actor, identifier)
        self.transport.after_send = cancel
        task = self.finished(self.create())
        self.assertEqual(task['status'], 'cancelled')
        self.assertEqual(task['artifacts'], [])
        self.assertEqual(len(self.requests), 1)

    def test_huy_thu_hoi_hoac_doi_config_trong_initialize_chan_moi_http_tiep_theo(self):
        for mode in ('cancel', 'membership', 'rotate', 'disconnect', 'project', 'ai'):
            with self.subTest(mode=mode):
                # Mỗi lượt có endpoint đã xác minh, callback chỉ được kích hoạt sau probe.
                self.connectors.transport = self.transport
                self.connectors.save(self.actor, self.settings)
                self.connectors.probe(self.actor, 'bdsg_crm')
                exchange = Exchange()
                project_id = ''
                if mode == 'project':
                    other = self.units.create(OWNER, {'name':'Nguồn dự án', 'admin':A['id']})['id']
                    source = self.units.bind(A, other)
                    project_id = self.tasks.projects.create(source, {'name':'Dự án tổng hợp'})['id']
                    grant = {'id':project_id, 'identity':A['id'], 'unit_id':self.unit}
                    self.tasks.projects.share(source, {**grant,'role':'viewer'})
                def request(*args):
                    response = exchange(*args)
                    if args[5] and json.loads(args[5])['method'] == 'initialize':
                        identifier = self.tasks.list(self.actor)['tasks'][0]['id']
                        if mode == 'cancel': self.tasks.cancel(self.actor, identifier)
                        if mode == 'membership':
                            data = {'unit_id':self.unit, 'identity':A['id']}
                            self.units.set_member(OWNER, {**data, 'role':'revoke'})
                            self.units.set_member(OWNER, {**data, 'role':'admin'})
                            self.actor = self.units.bind(A, self.unit)
                        if mode == 'rotate': self.connectors.save(self.actor, self.settings)
                        if mode == 'disconnect': self.connectors.disconnect(self.actor, 'bdsg_crm')
                        if mode == 'project': self.tasks.projects.share(source, {**grant,'role':'revoke'})
                        if mode == 'ai': self.ai.save(self.actor, config('synthetic-rotated-ai-key'))
                    return response
                self.connectors.transport = TruyenTaiMCP(
                    resolver=lambda *a,**k:[(2,1,6,'',('1.1.1.1',443))], exchange=request)
                task = self.finished(self.create(project_id=project_id))
                self.assertIn(task['status'], ('failed','cancelled'))
                self.assertEqual(task['artifacts'], [])
                methods = [json.loads(row[5])['method'] for row in exchange.requests if row[5]]
                self.assertEqual(methods, ['initialize'])
                self.assertEqual(len(exchange.requests), 1)
                self.connectors.transport = self.transport


if __name__ == '__main__':
    unittest.main()
