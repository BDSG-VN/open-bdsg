"""Nguồn token qua worker/SQLite/adapter HTTP tổng hợp, không API trả phí."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

import thu_mcp_uy_quyen_don_vi as foundation
from may_chu import UngDung
from mcp_uy_quyen_don_vi import LoiChungThuMCP
from sao_luu_he_thong import backup, restore
from thu_ai_don_vi import config
from thu_mo_hinh_bdsg import Response, answer
from trung_tam_ai import MoHinhLiteLLM


class ThuMCPTacVuDonVi(unittest.TestCase):
    setUp = foundation.ThuUyQuyenMCPDonVi.setUp

    def issue(self, *, allow_ai=False, actor=None, project=None):
        return self.service.create(actor or self.actor, {
            'name': 'Client tac vu thu', 'client_id': 'synthetic-task-client',
            'tools': ['cong_viec.tao', 'cong_viec.tiep_tuc', 'cong_viec.dung', 'cong_viec.chi_tiet'],
            'project_ids': [project or self.project], 'expires_in': 900,
            'task_profile': {'allow_ai': allow_ai}})

    def create(self, actor, **extra):
        response = self.service.call(actor, 'cong_viec.tao', {
            'prompt': 'Tong hop danh muc thu nghiem theo uy quyen', 'template': 'tong-quan',
            'project_id': self.project, 'module_ids': [], **extra})
        self.assertTrue(response['ok'], response)
        return response['ket_qua']['id']

    def finished(self, identifier, actor=None):
        until = time.monotonic()+5
        while time.monotonic() < until:
            task = self.app.tasks.detail(actor or self.actor, identifier)
            if task['status'] in ('completed', 'failed', 'interrupted', 'cancelled'): return task
            time.sleep(.01)
        self.fail('Worker khong ket thuc')

    def configure_ai(self, hook=lambda: None):
        requests = []
        class Provider:
            def open(self, request, timeout):
                requests.append(json.loads(request.data))
                hook()
                return Response(answer('# ONLY-LATE-PROVIDER-CONTENT'))
        self.app.unit_ai.probe = lambda *_: True
        self.app.unit_ai.factory = lambda alias, key: MoHinhLiteLLM(alias, key, opener=Provider())
        self.app.unit_ai.save(self.actor, config())
        return requests

    def test_tao_tac_vu_qua_nhan_worker_giu_nguon_va_tra_bao_cao(self):
        issued = self.issue()
        actor = self.service.authenticate(issued['credential'])
        task = self.finished(self.create(actor))
        self.assertEqual(task['status'], 'completed')
        self.assertTrue(task['mcp_delegated'])
        self.assertEqual(len(task['artifacts']), 1)
        self.assertNotIn(issued['credential'], json.dumps(task))
        response = self.service.call(actor, 'cong_viec.chi_tiet', {'id': task['id']})
        self.assertTrue(response['ok'])

    def test_profile_bat_buoc_va_khong_cap_cong_cu_ngoai_danh_muc(self):
        for profile in (None, {}, {'allow_ai': 1}, {'allow_ai': False, 'all': True}):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                self.service.create(self.actor, {'name': 'Client thu', 'client_id': 'synthetic-client',
                    'tools': ['cong_viec.tao'], 'project_ids': [self.project], 'expires_in': 900,
                    'task_profile': profile})
        actor = self.service.authenticate(self.issue()['credential'])
        for key, value in (('allow_module_reads', True), ('allow_action_drafts', True),
                           ('document_ids', ['synthetic-file']), ('mcp_delegated', False)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.service.call(actor, 'cong_viec.tao', {'prompt': 'Thu ngoai profile tac vu', key: value})
        with self.assertRaises(PermissionError):
            self.service.call(actor, 'cong_viec.tao', {'prompt': 'Thu du an ngoai grant', 'project_id': self.other_project})
        self.assertEqual(self.app.tasks.list(self.actor)['tasks'], [])

    def test_read_token_khong_tao_tac_vu_ke_ca_goi_backend(self):
        issued = foundation.ThuUyQuyenMCPDonVi.grant(self)
        actor = self.service.authenticate(issued['credential'])
        with self.assertRaises(PermissionError):
            self.app.tasks.create(actor, {'prompt': 'Khong duoc tao tu read token', 'template': 'tong-quan'})
        self.assertEqual(self.app.tasks.list(self.actor)['tasks'], [])

    def test_token_chi_tao_khong_tu_cap_followup_cancel(self):
        issued = self.service.create(self.actor, {'name': 'Client chi tao', 'client_id': 'synthetic-create',
            'tools': ['cong_viec.tao'], 'project_ids': [self.project], 'expires_in': 900,
            'task_profile': {'allow_ai': False}})
        actor = self.service.authenticate(issued['credential'])
        identifier = self.create(actor)
        self.finished(identifier)
        with self.assertRaises(PermissionError): self.app.tasks.cancel(actor, identifier)
        with self.assertRaises(PermissionError): self.app.tasks.followup(actor, identifier, 'Thu them quyen chua cap')

    def test_followup_cung_nguon_khong_cho_web_hoac_token_khac_tiep_quan(self):
        actor = self.service.authenticate(self.issue()['credential'])
        identifier = self.create(actor)
        self.assertEqual(self.finished(identifier)['status'], 'completed')
        other = self.service.authenticate(self.issue()['credential'])
        with self.assertRaises(PermissionError):
            self.service.call(other, 'cong_viec.tiep_tuc', {'id': identifier, 'text': 'Thu nhan quyen tu token khac'})
        with self.assertRaises(PermissionError):
            self.app.tasks.followup(self.actor, identifier, 'Thu tiep quan web chua duoc cap')
        result = self.service.call(actor, 'cong_viec.tiep_tuc', {'id': identifier, 'text': 'Tong hop luot hai trong quyen cu'})
        self.assertTrue(result['ok'])
        task = self.finished(identifier)
        self.assertEqual((task['run'], task['status']), (2, 'completed'))
        self.assertEqual(len(task['artifacts']), 2)

    def test_token_khong_nhan_tac_vu_web_va_web_van_hoat_dong(self):
        identifier = self.app.tasks.create(self.actor, {'prompt': 'Tac vu web khong gan nguon MCP', 'template': 'tong-quan'})['id']
        self.assertEqual(self.finished(identifier)['status'], 'completed')
        actor = self.service.authenticate(self.issue()['credential'])
        with self.assertRaises(PermissionError):
            self.service.call(actor, 'cong_viec.tiep_tuc', {'id': identifier, 'text': 'Thu tiep quan tac vu web'})
        self.app.tasks.followup(self.actor, identifier, 'Tiep tuc tu web voi quyen hop le')
        self.assertEqual(self.finished(identifier)['run'], 2)

    def test_profile_khong_ai_chan_truoc_provider_va_khong_luu_task(self):
        requests = self.configure_ai()
        actor = self.service.authenticate(self.issue()['credential'])
        result = self.service.call(actor, 'cong_viec.tao', {'prompt': 'Thu AI chua duoc profile cap', 'template': 'tong-quan', 'project_id': self.project})
        self.assertFalse(result['ok'])
        self.assertEqual(requests, [])
        self.assertEqual(self.app.tasks.list(self.actor)['tasks'], [])

    def test_ai_duoc_cap_chay_va_khong_nhan_credential_trong_context(self):
        requests = self.configure_ai()
        issued = self.issue(allow_ai=True)
        task = self.finished(self.create(self.service.authenticate(issued['credential'])))
        self.assertEqual(task['status'], 'completed')
        self.assertIn('ONLY-LATE-PROVIDER-CONTENT', json.dumps(task['artifacts']))
        self.assertEqual(len(requests), 1)
        self.assertNotIn(issued['credential'], json.dumps(requests))

    def test_thu_hoi_luc_provider_dang_cho_chan_callback_va_artifact(self):
        entered, released = threading.Event(), threading.Event()
        self.addCleanup(released.set)
        def wait():
            entered.set()
            if not released.wait(3): raise RuntimeError('Test barrier timeout')
        self.configure_ai(wait)
        issued = self.issue(allow_ai=True)
        identifier = self.create(self.service.authenticate(issued['credential']))
        self.assertTrue(entered.wait(3))
        self.service.revoke(self.actor, issued['id'])
        released.set()
        task = self.finished(identifier)
        self.assertEqual(task['status'], 'failed')
        self.assertEqual(task['artifacts'], [])
        self.assertNotIn('ONLY-LATE-PROVIDER-CONTENT', json.dumps(task))

    def test_het_han_luc_provider_dang_cho_chan_ket_qua(self):
        def expire(): self.now += 901
        self.configure_ai(expire)
        task = self.finished(self.create(self.service.authenticate(self.issue(allow_ai=True)['credential'])))
        self.assertEqual(task['status'], 'failed')
        self.assertEqual(task['artifacts'], [])
        self.assertNotIn('ONLY-LATE-PROVIDER-CONTENT', json.dumps(task))

    def test_dung_bang_token_va_web_sau_thu_hoi_khong_luu_ket_qua_muon(self):
        for via_web in (False, True):
            with self.subTest(via_web=via_web):
                entered, released = threading.Event(), threading.Event()
                self.addCleanup(released.set)
                def wait():
                    entered.set()
                    if not released.wait(3): raise RuntimeError('Test barrier timeout')
                self.configure_ai(wait)
                issued = self.issue(allow_ai=True)
                actor = self.service.authenticate(issued['credential'])
                identifier = self.create(actor)
                self.assertTrue(entered.wait(3))
                if via_web:
                    self.service.revoke(self.actor, issued['id'])
                    self.app.tasks.cancel(self.actor, identifier)
                else:
                    self.assertTrue(self.service.call(actor, 'cong_viec.dung', {'id': identifier})['ok'])
                released.set()
                task = self.finished(identifier)
                self.assertEqual(task['status'], 'cancelled')
                self.assertEqual(task['artifacts'], [])
                self.assertNotIn('ONLY-LATE-PROVIDER-CONTENT', json.dumps(task))

    def test_thu_hoi_truoc_giu_ngan_sach_chan_provider(self):
        requests = self.configure_ai()
        issued = self.issue(allow_ai=True)
        original = self.app.unit_ai.factory
        def revoke_before_reserve(alias, key):
            self.service.revoke(self.actor, issued['id'])
            return original(alias, key)
        self.app.unit_ai.factory = revoke_before_reserve
        task = self.finished(self.create(self.service.authenticate(issued['credential'])))
        self.assertEqual(task['status'], 'failed')
        self.assertEqual(requests, [])
        self.assertEqual(task['artifacts'], [])

    def test_thu_hoi_cap_lai_project_luc_provider_chan_luot_cu(self):
        grant = {'id': self.project, 'identity': foundation.MEMBER['id']}
        self.app.projects.share(self.actor, {**grant, 'role': 'viewer'})
        def regrant():
            self.app.projects.share(self.actor, {**grant, 'role': 'revoke'})
            self.app.projects.share(self.actor, {**grant, 'role': 'viewer'})
        self.configure_ai(regrant)
        actor = self.service.authenticate(self.issue(allow_ai=True, actor=self.member)['credential'])
        task = self.finished(self.create(actor), self.member)
        self.assertEqual(task['status'], 'failed')
        self.assertNotIn('ONLY-LATE-PROVIDER-CONTENT', json.dumps(task))
        self.assertEqual(task['artifacts'], [])

    def test_restart_giu_nguon_nhung_khong_replay_va_followup_can_cung_token(self):
        issued = self.issue()
        identifier = self.create(self.service.authenticate(issued['credential']))
        self.assertEqual(self.finished(identifier)['run'], 1)
        self.app.tasks.close()
        restarted = UngDung(self.app.kho.root, 'https://preview.test', True, unit_preview=True)
        try:
            web = restarted.units.bind(foundation.USER, self.units[0])
            task = restarted.tasks.detail(web, identifier)
            self.assertEqual((task['run'], len(task['artifacts'])), (1, 1))
            actor = restarted.inbound_mcp.authenticate(issued['credential'])
            response = restarted.inbound_mcp.call(actor, 'cong_viec.tiep_tuc',
                {'id': identifier, 'text': 'Tiep tuc sau restart bang dung nguon'})
            self.assertTrue(response['ok'])
            task = self.finished(identifier)
            self.assertEqual((task['run'], task['status'], len(task['artifacts'])), (2, 'completed', 2))
        finally:
            restarted.tasks.close(); restarted.core.audit.close()

    def test_phuc_hoi_du_lieu_khong_dung_lai_nguon_luot_cu(self):
        issued = self.issue()
        actor = self.service.authenticate(issued['credential'])
        identifier = self.create(actor)
        task = self.finished(identifier)
        with tempfile.TemporaryDirectory() as folder:
            bundle, target = Path(folder)/'bundle', Path(folder)/'restored'
            backup(self.app.kho.root, bundle)
            self.service.revoke(self.actor, issued['id'])
            restore(bundle, target)
            restored = UngDung(target/'data', 'https://preview.test', True, unit_preview=True)
            try:
                web = restored.units.bind(foundation.USER, self.units[0])
                with restored.kho.ket_noi() as db, self.assertRaises(LoiChungThuMCP):
                    restored.inbound_mcp.restore_task(web, task, db)
                with self.assertRaises(PermissionError):
                    restored.tasks.followup(web, identifier, 'Khong hoi sinh nguon cu sau restore')
            finally:
                restored.tasks.close(); restored.core.audit.close()


if __name__ == '__main__': unittest.main()
