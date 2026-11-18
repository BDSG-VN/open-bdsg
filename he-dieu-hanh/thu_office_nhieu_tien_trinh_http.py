"""Hai gateway độc lập dùng cùng kho; engine/scanner chỉ là dữ liệu tổng hợp."""
import base64
import concurrent.futures
import http.client
import json
import multiprocessing
import os
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from chu_ky_office import sign, verify
from may_chu import UngDung, tao_may_chu
from thu_don_vi_http import CoSoDonViHTTP
from thu_office_tich_hop import Scanner, SECRET, changed_document


def serve_worker(folder, origin, engine_port, ready, stop):
    app = UngDung(folder, origin, True, unit_preview=True, unit_office_preview=True)
    app.office.scanner = Scanner()
    app.office_editor.secret = SECRET
    app.office_editor.engine_port = engine_port
    server = tao_may_chu(app, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ready.send((os.getpid(), server.server_port))
        stop.wait(60)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        app.tasks.close()
        app.core.audit.close()
        ready.close()


class ThuOfficeNhieuTienTrinhHTTP(CoSoDonViHTTP):
    app_options = {'unit_office_preview': True}

    @contextmanager
    def workers(self, engine_port):
        context = multiprocessing.get_context('spawn')
        processes, ports = [], []
        try:
            for _ in range(2):
                reader, writer = context.Pipe(duplex=False)
                stop = context.Event()
                process = context.Process(target=serve_worker, args=(
                    self.tmp.name, self.app.origin, engine_port, writer, stop))
                process.start()
                writer.close()
                processes.append((process, stop, reader))
                self.assertTrue(reader.poll(20), 'Gateway con chưa sẵn sàng')
                pid, port = reader.recv()
                self.assertEqual(pid, process.pid)
                self.assertNotEqual(pid, os.getpid())
                ports.append(port)
            self.assertNotEqual(processes[0][0].pid, processes[1][0].pid)
            yield ports
        finally:
            for process, stop, _ in processes:
                stop.set()
            for process, _, reader in processes:
                process.join(timeout=10)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
                reader.close()
            for process, _, _ in processes:
                self.assertEqual(process.exitcode, 0, 'Gateway phải tự dừng sạch')

    def at(self, port, path, body, authenticated=True):
        headers = {'Content-Type': 'application/json', 'Origin': self.app.origin if authenticated else ''}
        if authenticated:
            headers.update(Cookie=self.cookies['nguoi-a'], **{'X-BDSG-Unit': self.units[0]})
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=15)
        try:
            connection.request('POST', path, json.dumps(body), headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read()), {}
        finally:
            connection.close()

    def tool_at(self, port, name, args):
        return self.value(self.at(port, '/api/tools', {'name': name, 'arguments': args}))

    def test_concurrent_open_retry_and_duplicate_callback_commit_one_version(self):
        document = changed_document('Luu qua hai tien trinh HTTP doc lap')
        commands, downloads = [], []
        command_entered, release_command, retry_finished = threading.Event(), threading.Event(), threading.Event()
        download_barrier = threading.Barrier(2)

        class Engine(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                claims = verify(payload['token'], SECRET, 'command')
                commands.append((claims['c'], claims['key'], claims['userdata']))
                command_entered.set()
                if not release_command.wait(10):
                    self.send_error(503)
                    return
                raw = b'{"error":0}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                downloads.append(self.path)
                # Cả hai callback phải đọc phiên trước khi bên nào commit.
                download_barrier.wait(timeout=10)
                self.send_response(200)
                self.send_header('Content-Length', str(len(document)))
                self.end_headers()
                self.wfile.write(document)

        engine = ThreadingHTTPServer(('127.0.0.1', 0), Engine)
        engine_thread = threading.Thread(target=engine.serve_forever, daemon=True)
        engine_thread.start()
        self.addCleanup(engine.server_close)
        self.addCleanup(engine.shutdown)
        self.addCleanup(release_command.set)
        self.app.office.scanner = Scanner()
        self.app.office_editor.secret = SECRET
        project = self.value(self.tool('du_an.tao', {'name': 'Du an hai gateway'}))['id']
        file = self.value(self.tool('van_phong.tao_office', {
            'project_id': project, 'name': 'hai-gateway.docx', 'request_key': 'd'*32}))

        with self.workers(engine.server_port) as ports, concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            open_barrier = threading.Barrier(2)

            def open_at(port):
                open_barrier.wait(timeout=10)
                return self.tool_at(port, 'van_phong.mo_soan_thao', {'id': file['id']})

            opened = list(pool.map(open_at, ports))
            self.assertEqual(opened[0]['key'], opened[1]['key'])
            key = opened[0]['key']
            save_barrier = threading.Barrier(8)

            def save_at(index):
                save_barrier.wait(timeout=10)
                receipt = self.tool_at(ports[index % 2], 'van_phong.luu_soan_thao', {
                    'key': key, 'request_key': 'cung-y-dinh-hai-gateway'})
                retry_finished.set()
                return receipt

            futures = [pool.submit(save_at, index) for index in range(8)]
            try:
                self.assertTrue(command_entered.wait(10))
                self.assertTrue(retry_finished.wait(10), 'Retry không được chờ engine hay phát lệnh mới')
            finally:
                release_command.set()
            receipts = [future.result(timeout=15) for future in futures]
            request_id = receipts[0]['request_id']
            self.assertEqual({receipt['request_id'] for receipt in receipts}, {request_id})
            self.assertEqual(commands, [('forcesave', key, request_id)])
            for port in ports:
                self.assertEqual(self.tool_at(port, 'van_phong.doc', {'id': file['id']})['file']['version'], 1)

            token = sign({'payload': {'key': key, 'status': 6, 'userdata': request_id,
                'users': ['nguoi-a'], 'url': f'http://127.0.0.1:{engine.server_port}/cache/files/{key}/output.docx'},
                'operation': 'callback', 'exp': time.time()+300}, SECRET)
            callbacks = list(pool.map(lambda port: self.at(port, '/api/office-callback', {'token': token}, False), ports))
            self.assertEqual([response[:2] for response in callbacks], [(200, {'error': 0})]*2)
            self.assertEqual(len(downloads), 2)
            for port in ports:
                current = self.tool_at(port, 'van_phong.doc', {'id': file['id']})
                self.assertEqual(current['file']['version'], 2)
                self.assertEqual(base64.b64decode(current['content_base64']), document)
                progress = self.tool_at(port, 'van_phong.phien_soan_thao', {'key': key, 'request_id': request_id})
                self.assertEqual(progress['command_state'], 'committed')
                self.assertEqual(self.tool_at(port, 'van_phong.luu_soan_thao', {
                    'key': key, 'request_key': 'cung-y-dinh-hai-gateway'})['state'], 'da-luu')
                self.assertEqual(self.at(port, '/api/office-callback', {'token': token}, False)[:2], (200, {'error': 0}))
            self.assertEqual(len(commands), 1)
            self.assertEqual(len(downloads), 2)


if __name__ == '__main__':
    unittest.main()
