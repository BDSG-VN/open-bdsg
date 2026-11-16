"""Kiểm vận hành qua HTTP và bản sao vào thư mục mới, chỉ dùng dữ liệu tổng hợp."""

import http.client
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path

from may_chu import UngDung, tao_may_chu
from sao_luu_he_thong import backup, restore, verify
from van_hanh_may_chu import MayChuCoGioiHan


class ThuVanHanh(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = UngDung(self.root / "data", "https://example.test", True)
        self.app.kho.tao_chu("chi-dung-kiem-thu")
        self.server = tao_may_chu(self.app, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.app.schedules.close()
        self.app.tasks.close()
        self.app.core.audit.close()
        self.temp.cleanup()

    def request(self, path, body=None, cookie=None):
        with closing(
            http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        ) as connection:
            headers = {"Origin": self.app.origin, "Content-Type": "application/json"}
            if cookie:
                headers["Cookie"] = cookie
            connection.request(
                "GET" if body is None else "POST",
                path,
                json.dumps(body) if body is not None else None,
                headers,
            )
            response = connection.getresponse()
            return (
                response.status,
                json.loads(response.read()),
                dict(response.getheaders()),
            )

    def test_readiness_and_admin_report_do_not_disclose_private_data(self):
        self.assertEqual(self.request("/api/ready")[:2], (200, {"status": "ready"}))
        self.assertEqual(self.request("/api/system")[0], 401)
        token, _ = self.app.kho.dang_nhap("chu-quan", "chi-dung-kiem-thu", "test")
        status, report, _ = self.request("/api/system", cookie="bdsg_session=" + token)
        self.assertEqual(status, 200)
        self.assertEqual(report["tasks"], {})
        self.assertEqual(
            report["capabilities"]["google_account_access"], "requires-per-user-consent"
        )
        self.assertNotIn(self.temp.name, json.dumps(report))
        self.assertNotIn("client_secret", json.dumps(report))
        self.app.kho.tao_nguoi_dung(
            {"id": "chu-quan", "role": "quan-tri"},
            {
                "id": "operator-a",
                "name": "Nguoi thu",
                "password": "mat-khau-chi-dung-thu",
            },
        )
        token, _ = self.app.kho.dang_nhap(
            "operator-a", "mat-khau-chi-dung-thu", "test-2"
        )
        self.assertEqual(
            self.request("/api/system", cookie="bdsg_session=" + token)[0], 403
        )

    def test_readiness_detects_missing_database_without_recreating_it(self):
        missing = self.root / "missing.db"
        original = self.app.kho.db
        self.app.kho.db = missing
        try:
            self.assertEqual(
                self.request("/api/ready")[:2], (503, {"status": "not-ready"})
            )
            self.assertFalse(missing.exists())
        finally:
            self.app.kho.db = original

    def test_low_disk_and_draining_stop_new_work(self):
        self.app.operations.min_free_bytes = 2**90
        self.assertEqual(self.request("/api/ready")[0], 503)
        self.app.operations.draining.set()
        self.assertEqual(
            self.request("/api/login", {"username": "x", "password": "x"})[0], 503
        )
        self.assertEqual(self.request("/api/catalogue")[0], 503)
        self.assertEqual(self.request("/api/suc-khoe")[0], 200)

    def test_online_backup_restore_keeps_data_and_refuses_overwrite(self):
        secrets_dir = self.root / "secrets"
        secrets_dir.mkdir()
        (secrets_dir / "google-vault.key").write_bytes(b"x" * 32)
        (secrets_dir / "unrelated-private.txt").write_text("khong-duoc-sao-chep")
        bundle = self.root / "snapshot"
        backup(self.app.kho.root, bundle, secrets_dir)
        with self.app.kho.ket_noi() as db:
            db.execute(
                "INSERT INTO yeu_cau VALUES ('sau-snapshot','chu-quan','Moi','','','moi',0)"
            )
        restored = self.root / "restored"
        self.assertFalse(restore(bundle, restored)["live_service_changed"])
        with closing(sqlite3.connect(restored / "data/van-hanh.db")) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM chu").fetchone()[0], 1)
            self.assertEqual(
                db.execute("SELECT count(*) FROM yeu_cau").fetchone()[0], 0
            )
        self.assertEqual(
            (restored / "secrets/google-vault.key").read_bytes(), b"x" * 32
        )
        self.assertFalse((restored / "secrets/unrelated-private.txt").exists())
        with self.assertRaises(FileExistsError):
            restore(bundle, self.app.kho.root)
        with self.assertRaises(ValueError):
            backup(self.app.kho.root, self.app.kho.root / "bad-backup")

    def test_backup_rejects_corruption_unlisted_files_and_path_traversal(self):
        bundle = self.root / "snapshot"
        backup(self.app.kho.root, bundle)
        extra = bundle / "extra.txt"
        extra.write_text("ngoai-manifest")
        with self.assertRaises(ValueError):
            verify(bundle)
        extra.unlink()
        manifest_path = bundle / "manifest.json"
        original = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(original)
        manifest["files"]["../secret"] = {"sha256": "x", "bytes": 0}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError):
            restore(bundle, self.root / "must-not-exist")
        self.assertFalse((self.root / "must-not-exist").exists())
        manifest_path.write_text(original, encoding="utf-8")
        with (bundle / "data/van-hanh.db").open("ab") as output:
            output.write(b"bad")
        with self.assertRaises(ValueError):
            verify(bundle)

    def test_idle_connections_are_bounded_and_capacity_recovers(self):
        # Dùng handler thực của ứng dụng, chỉ đổi hạn mức xuống một để đo overload.
        server = MayChuCoGioiHan(
            ("127.0.0.1", 0),
            self.server.RequestHandlerClass,
            max_connections=1,
            socket_timeout=0.5,
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        first = socket.create_connection(server.server_address, timeout=2)
        first.sendall(b"GET /api/ready HTTP/1.0\r\n")
        # Cùng thread accept xử lý theo thứ tự TCP; kết nối đầu chiếm slot tới timeout.
        second = socket.create_connection(server.server_address, timeout=2)
        try:
            self.assertIn(b"503 Service Unavailable", second.recv(4096))
            first.settimeout(2)
            self.assertEqual(first.recv(4096), b"")
            with closing(
                http.client.HTTPConnection(*server.server_address, timeout=2)
            ) as connection:
                connection.request("GET", "/api/ready")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
        finally:
            first.close()
            second.close()
            server.shutdown()
            server.server_close()

    @unittest.skipIf(os.name == "nt", "SIGTERM cần tiến trình Linux thật")
    def test_sigterm_exits_cleanly_and_preserves_database(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        folder = self.root / "signal-data"
        process = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).with_name("may_chu.py")),
                "serve",
                "--data",
                str(folder),
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 10
            while True:
                try:
                    with closing(
                        http.client.HTTPConnection("127.0.0.1", port, timeout=1)
                    ) as connection:
                        connection.request("GET", "/api/suc-khoe")
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        response.read()
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        self.fail("Tiến trình không sẵn sàng")
                    time.sleep(0.02)
            process.terminate()
            process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0)
            with closing(sqlite3.connect(folder / "van-hanh.db")) as db:
                self.assertEqual(
                    db.execute("PRAGMA integrity_check").fetchone(), ("ok",)
                )
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    unittest.main()
