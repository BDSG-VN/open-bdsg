"""Cổng editor đơn vị opt-in: đi qua HTTP và nhân, không lách allowlist."""
import unittest
import tempfile
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from thu_don_vi_http import CoSoDonViHTTP
from thu_office_tich_hop import Scanner, SECRET
from chu_ky_office import verify
from may_chu import UngDung, OFFICE_PREVIEW_TOOLS


class ThuOfficePreviewHTTP(CoSoDonViHTTP):
    app_options = {'unit_office_preview': True}

    def create_file(self):
        self.app.office.scanner = Scanner()
        self.app.office_editor.secret = SECRET
        project = self.value(self.tool('du_an.tao', {'name': 'Du an Office sandbox'}))['id']
        file = self.value(self.tool('van_phong.tao_office', {
            'project_id': project, 'name': 'tai-lieu.docx', 'request_key': 'a'*32}))
        return project, file

    def denied(self, response):
        status, body, _ = response
        self.assertTrue(status == 403 or (status == 200 and body.get('ok') is False), response)

    def test_opt_in_operator_creates_opens_and_reads_progress_through_http(self):
        project, file = self.create_file()
        opened = self.value(self.tool('van_phong.mo_soan_thao', {'id': file['id']}))
        self.assertEqual(opened['config']['documentType'], 'word')
        progress = self.value(self.tool('van_phong.phien_soan_thao', {'key': opened['key']}))
        self.assertEqual(progress['state'], 'active')
        self.assertFalse(progress['pending'])

    def test_same_owner_other_unit_and_system_root_cannot_open_or_poll_file(self):
        _, file = self.create_file()
        opened = self.value(self.tool('van_phong.mo_soan_thao', {'id': file['id']}))
        for who, unit in (('nguoi-a', self.units[1]), ('nguoi-b', self.units[0]), ('chu-quan', self.units[0])):
            self.denied(self.tool('van_phong.mo_soan_thao', {'id': file['id']}, who=who, unit=unit))
            response = self.tool('van_phong.phien_soan_thao', {'key': opened['key']}, who=who, unit=unit)
            self.denied(response)
            self.assertNotIn(opened['key'], str(response[1]))

    def test_project_viewer_cannot_open_editor_even_with_unit_membership(self):
        project, file = self.create_file()
        self.assertEqual(self.request('/api/units/members', {'identity': 'nguoi-b', 'role': 'member'},
            'chu-quan', self.units[0])[0], 200)
        self.value(self.tool('don_vi.chia_se_du_an', {'id': project, 'unit_id': self.units[0],
            'identity': 'nguoi-b', 'role': 'viewer'}))
        self.value(self.tool('van_phong.mo_soan_thao', {'id': file['id']}))
        self.denied(self.tool('van_phong.mo_soan_thao', {'id': file['id']}, who='nguoi-b'))

    def test_actor_or_unit_arguments_cannot_override_http_scope(self):
        _, file = self.create_file()
        for name, value in (('actor', {'id': 'chu-quan'}), ('owner', 'chu-quan'),
                            ('unit_scope', {}), ('unit_id', self.units[1])):
            self.assertEqual(self.tool('van_phong.mo_soan_thao', {'id': file['id'], name: value})[0], 400)

    def test_legitimate_mcp_credential_stays_read_only_and_cannot_gain_office_tools(self):
        project, file = self.create_file()
        actor = self.app.units.bind({'id': 'nguoi-a', 'name': 'nguoi-a', 'role': 'operator'}, self.units[0])
        service = self.app.inbound_mcp
        issued = service.create(actor, {'name': 'Credential thu Office', 'client_id': 'office-test',
            'tools': ['du_an.danh_sach'], 'project_ids': [project], 'expires_in': 900})
        delegated = service.authenticate(issued['credential'])
        self.assertTrue(self.app.core.goi(delegated, 'du_an.danh_sach', {})['ok'])
        for name in OFFICE_PREVIEW_TOOLS:
            result = self.app.core.goi(delegated, name, {'project_id': project, 'name': 'cam.docx', 'id': file['id']})
            self.assertFalse(result['ok'], name)
            self.assertEqual(result['loai_loi'], 'quyen')

    def test_capability_is_truthful_and_does_not_open_google_or_agent_tools(self):
        me = self.request('/api/me', who='nguoi-a')[1]
        self.assertIs(me['workspace']['capabilities']['office_editor'], True)
        project, _ = self.create_file()
        status = self.value(self.tool('van_phong.trang_thai', {'project_id': project}))
        self.assertEqual(status['editor_state'], 'da-cau-hinh')
        self.app.office_editor.secret = ''
        self.assertEqual(self.value(self.tool('van_phong.trang_thai', {'project_id': project}))['editor_state'], 'chua-cau-hinh')
        self.assertEqual(self.tool('van_phong.google_nhap', {})[0], 403)
        self.app.kho.tao_agent('office-agent', 'Office agent thu', 'agent')
        agent = {'id': 'office-agent', 'name': 'Office agent thu', 'role': 'agent'}
        catalogue = self.app.core.nhan.danh_sach_cong_cu(self.app.core.danh_tinh(agent))
        names = {tool['ten'] for tool in catalogue}
        self.assertTrue(names.isdisjoint(OFFICE_PREVIEW_TOOLS))

    def test_http_save_retries_once_and_abandon_fences_pending_receipt(self):
        _, file = self.create_file()
        opened = self.value(self.tool('van_phong.mo_soan_thao', {'id': file['id']}))
        commands = []
        class Engine(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                if self.path != '/command':
                    self.send_error(404)
                    return
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                commands.append(verify(payload['token'], SECRET, 'command')['c'])
                raw = b'{"error":0}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        engine = ThreadingHTTPServer(('127.0.0.1', 0), Engine)
        threading.Thread(target=engine.serve_forever, daemon=True).start()
        self.addCleanup(engine.server_close)
        self.addCleanup(engine.shutdown)
        self.app.office_editor.engine_port = engine.server_port
        args = {'key': opened['key'], 'request_key': 'save-http-1'}
        saved = self.value(self.tool('van_phong.luu_soan_thao', args))
        self.assertEqual(self.value(self.tool('van_phong.luu_soan_thao', args))['request_id'], saved['request_id'])
        self.assertEqual(commands, ['forcesave'])
        progress = self.value(self.tool('van_phong.phien_soan_thao', {
            'key': opened['key'], 'request_id': saved['request_id']}))
        self.assertTrue(progress['pending'])
        self.assertNotEqual(progress['command_state'], 'committed')
        abandoned = self.value(self.tool('van_phong.bo_phien_soan_thao', {
            'file_id': file['id'], 'key': opened['key'], 'request_key': 'abandon-http-1',
            'acknowledge_unsaved_changes': True, 'acknowledge_shared_session': True}))
        self.assertGreater(abandoned['revoked_sessions'], 0)
        progress = self.value(self.tool('van_phong.phien_soan_thao', {'key': opened['key']}))
        self.assertEqual((progress['state'], progress['command_state'], progress['pending']),
            ('revoked', 'abandoned', False))
        self.denied(self.tool('van_phong.luu_soan_thao', {'key': opened['key'], 'request_key': 'new-after-abandon'}))
        self.assertEqual(self.value(self.tool('van_phong.doc', {'id': file['id']}))['file']['version'], 1)

    def test_global_write_gate_blocks_editor_writes_without_blocking_existing_progress_read(self):
        project, file = self.create_file()
        opened = self.value(self.tool('van_phong.mo_soan_thao', {'id': file['id']}))
        self.app.core.nhan.chinh_sach.cong_ghi.dong()
        self.denied(self.tool('van_phong.tao_office', {'project_id': project, 'name': 'blocked.docx', 'request_key': 'b'*32}))
        self.denied(self.tool('van_phong.mo_soan_thao', {'id': file['id']}))
        self.denied(self.tool('van_phong.luu_soan_thao', {'key': opened['key'], 'request_key': 'write-off'}))
        self.assertEqual(self.value(self.tool('van_phong.phien_soan_thao', {'key': opened['key']}))['state'], 'active')

    def test_revocation_fences_http_progress_after_successful_open(self):
        # Giữ một admin khác để phép thử không bị chặn bởi quy tắc cuối cùng.
        self.assertEqual(self.request('/api/units/members', {'identity': 'nguoi-b', 'role': 'admin'},
            'chu-quan', self.units[0])[0], 200)
        _, file = self.create_file()
        opened = self.value(self.tool('van_phong.mo_soan_thao', {'id': file['id']}))
        self.assertEqual(self.request('/api/units/members', {'identity': 'nguoi-a', 'role': 'revoke'},
            'chu-quan', self.units[0])[0], 200)
        self.denied(self.tool('van_phong.phien_soan_thao', {'key': opened['key']}))

    def test_opt_in_does_not_change_a_separate_default_instance_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            control = UngDung(folder, 'https://control.test', True, unit_preview=True)
            try:
                identity = {'id': 'policy-probe', 'name': 'Policy probe', 'role': 'operator'}
                current = {row['ten'] for row in self.app.core.nhan.danh_sach_cong_cu(self.app.core.danh_tinh(identity))}
                other = {row['ten'] for row in control.core.nhan.danh_sach_cong_cu(control.core.danh_tinh(identity))}
                self.assertTrue(OFFICE_PREVIEW_TOOLS <= current)
                self.assertTrue(OFFICE_PREVIEW_TOOLS.isdisjoint(other))
            finally:
                control.tasks.close()
                control.core.audit.close()


class ThuOfficeMacDinhHTTP(CoSoDonViHTTP):
    def test_default_stays_closed_in_http_core_and_capability(self):
        self.assertIs(self.request('/api/me', who='nguoi-a')[1]['workspace']['capabilities']['office_editor'], False)
        actor = self.app.units.bind({'id': 'nguoi-a', 'name': 'nguoi-a', 'role': 'operator'}, self.units[0])
        catalogue = self.app.core.mcp(actor, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
        names = {tool['name'] for tool in catalogue['result']['tools']}
        self.assertTrue(names.isdisjoint(OFFICE_PREVIEW_TOOLS))
        for name in OFFICE_PREVIEW_TOOLS:
            self.assertEqual(self.tool(name, {})[0], 403)


class ThuCoOfficePreview(unittest.TestCase):
    def test_bad_flag_or_legacy_mode_is_rejected_before_creating_data(self):
        with tempfile.TemporaryDirectory() as folder:
            for index, (flag, units) in enumerate(((True, False), ('true', True), (1, True), (None, True))):
                path = Path(folder)/str(index)
                with self.assertRaises(ValueError):
                    UngDung(path, 'https://preview.test', unit_preview=units, unit_office_preview=flag)
                self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
