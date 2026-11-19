"""Phục hồi dữ liệu và tách thế hệ editor qua HTTP/nhân với dữ liệu tổng hợp."""
import base64
import json
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from chu_ky_office import sign, verify
from may_chu import UngDung, tao_may_chu
from sao_luu_he_thong import backup, restore
from thu_don_vi_http import CoSoDonViHTTP
from thu_office_tich_hop import Scanner, SECRET, changed_document


class ThuKhoiPhucOfficeHTTP(CoSoDonViHTTP):
    app_options = {'unit_office_preview': True}

    @contextmanager
    def recovered(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle, destination = Path(folder)/'snapshot', Path(folder)/'restored'
            backup(self.app.kho.root, bundle)
            self.assertFalse((bundle/'data/office-editor-epoch').exists())
            restore(bundle, destination)
            app = UngDung(destination/'data', self.app.origin, True,
                          unit_preview=True, unit_office_preview=True)
            app.office.scanner = Scanner()
            app.office_editor.secret = SECRET
            server = tao_may_chu(app, 0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            original_app, original_server = self.app, self.server
            self.app, self.server = app, server
            try:
                yield app
            finally:
                self.app, self.server = original_app, original_server
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)
                app.tasks.close()
                app.core.audit.close()
                self.assertFalse(worker.is_alive())

    def source(self, opened):
        url = opened['config']['document']['url']
        parsed = urlsplit(url)
        token = sign({'payload': {'url': url}, 'operation': 'download',
                      'exp': time.time()+300}, SECRET)
        return self.request(parsed.path+'?'+parsed.query,
                            headers={'Origin': '', 'Authorization': 'Bearer '+token})

    def denied(self, response):
        status, body, _ = response
        self.assertTrue(status == 403 or (status == 200 and body.get('ok') is False), response)

    def test_restore_preserves_three_formats_and_units_but_never_revives_old_editor(self):
        self.app.office.scanner = Scanner()
        self.app.office_editor.secret = SECRET
        files = []
        for index, extension in enumerate(('docx', 'xlsx', 'pptx'), 1):
            project = self.value(self.tool('du_an.tao', {'name': 'Du an phuc hoi '+extension}))['id']
            file = self.value(self.tool('van_phong.tao_office', {
                'project_id': project, 'name': 'phuc-hoi.'+extension, 'request_key': f'{index:032x}'}))
            opened = self.value(self.tool('van_phong.mo_soan_thao', {'id': file['id']}))
            status, content, _ = self.source(opened)
            self.assertEqual(status, 200)
            self.assertTrue(content.startswith(b'PK'))
            files.append((file, opened, content))
        with self.recovered():
            self.assertIs(self.request('/api/me', who='nguoi-a')[1]['workspace']['capabilities']['office_editor'], True)
            for file, old, content in files:
                with self.subTest(format=file['name']):
                    self.assertEqual(self.source(old)[0], 403)
                    self.denied(self.tool('van_phong.phien_soan_thao', {'key': old['key']}))
                    self.denied(self.tool('van_phong.luu_soan_thao', {'key': old['key'], 'request_key': 'sau-phuc-hoi'}))
                    callback = sign({'payload': {'key': old['key'], 'status': 4},
                                     'operation': 'callback', 'exp': time.time()+300}, SECRET)
                    self.assertEqual(self.request('/api/office-callback', {'token': callback},
                                                  headers={'Origin': ''})[:2], (200, {'error': 1}))
                    self.denied(self.tool('van_phong.doc', {'id': file['id']}, unit=self.units[1]))
                    current = self.value(self.tool('van_phong.doc', {'id': file['id']}))
                    self.assertEqual(current['file']['version'], 1)
                    fresh = self.value(self.tool('van_phong.mo_soan_thao', {'id': file['id']}))
                    self.assertNotEqual(fresh['key'], old['key'])
                    self.assertEqual(self.source(fresh)[:2], (200, content))
                    self.assertEqual(self.value(self.tool('van_phong.phien_soan_thao', {'key': fresh['key']}))['state'], 'active')

    def test_pending_save_is_not_redispatched_or_committed_by_old_callback_after_restore(self):
        calls = []
        document = changed_document('Noi dung moi sau phuc hoi qua HTTP')

        class Engine(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                claims = verify(payload['token'], SECRET, 'command')
                calls.append(('command', claims['key'], claims['userdata']))
                raw = b'{"error":0}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                calls.append(('download', self.path))
                self.send_response(200)
                self.send_header('Content-Length', str(len(document)))
                self.end_headers()
                self.wfile.write(document)

        engine = ThreadingHTTPServer(('127.0.0.1', 0), Engine)
        engine_thread = threading.Thread(target=engine.serve_forever, daemon=True)
        engine_thread.start()
        self.addCleanup(engine.server_close)
        self.addCleanup(engine.shutdown)
        self.app.office.scanner = Scanner()
        self.app.office_editor.secret = SECRET
        self.app.office_editor.engine_port = engine.server_port
        project = self.value(self.tool('du_an.tao', {'name': 'Du an cho luu khi phuc hoi'}))['id']
        file = self.value(self.tool('van_phong.tao_office', {
            'project_id': project, 'name': 'cho-luu.docx', 'request_key': 'c'*32}))
        old = self.value(self.tool('van_phong.mo_soan_thao', {'id': file['id']}))
        pending = self.value(self.tool('van_phong.luu_soan_thao', {
            'key': old['key'], 'request_key': 'luu-truoc-phuc-hoi'}))
        self.assertEqual(calls, [('command', old['key'], pending['request_id'])])

        def callback(opened, request_id):
            payload = {'key': opened['key'], 'status': 6, 'userdata': request_id,
                       'users': ['nguoi-a'], 'url': f'http://127.0.0.1:{engine.server_port}/cache/files/'+opened['key']+'/output.docx'}
            token = sign({'payload': payload, 'operation': 'callback', 'exp': time.time()+300}, SECRET)
            return self.request('/api/office-callback', {'token': token}, headers={'Origin': ''})[:2]

        with self.recovered() as app:
            app.office_editor.engine_port = engine.server_port
            self.denied(self.tool('van_phong.phien_soan_thao', {
                'key': old['key'], 'request_id': pending['request_id']}))
            self.denied(self.tool('van_phong.luu_soan_thao', {
                'key': old['key'], 'request_key': 'luu-truoc-phuc-hoi'}))
            self.assertEqual(callback(old, pending['request_id']), (200, {'error': 1}))
            self.assertEqual(len(calls), 1)
            self.assertEqual(self.value(self.tool('van_phong.doc', {'id': file['id']}))['file']['version'], 1)
            fresh = self.value(self.tool('van_phong.mo_soan_thao', {'id': file['id']}))
            self.assertNotEqual(fresh['key'], old['key'])
            saved = self.value(self.tool('van_phong.luu_soan_thao', {
                'key': fresh['key'], 'request_key': 'luu-sau-phuc-hoi'}))
            self.assertEqual(self.value(self.tool('van_phong.luu_soan_thao', {
                'key': fresh['key'], 'request_key': 'luu-sau-phuc-hoi'}))['request_id'], saved['request_id'])
            self.assertEqual(len(calls), 2)
            self.assertEqual(callback(old, pending['request_id']), (200, {'error': 1}))
            self.assertEqual(len(calls), 2)
            self.assertEqual(callback(fresh, saved['request_id']), (200, {'error': 0}))
            self.assertEqual(len(calls), 3)
            current = self.value(self.tool('van_phong.doc', {'id': file['id']}))
            self.assertEqual(current['file']['version'], 2)
            self.assertEqual(base64.b64decode(current['content_base64']), document)
            progress = self.value(self.tool('van_phong.phien_soan_thao', {
                'key': fresh['key'], 'request_id': saved['request_id']}))
            self.assertEqual(progress['command_state'], 'committed')


if __name__ == '__main__':
    unittest.main()
