"""Kiểm cổng từ bản sao tổng hợp; không đọc dữ liệu hoặc chứng thư thật."""

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from v28_khoi_phuc_dich_vu import ROOT, _environment, _worker, isolated_network, run_drill
import v28_khoi_phuc_dich_vu as gateway_drill
sys.path.insert(0, str(ROOT / "he-dieu-hanh"))
from may_chu import UngDung
from sao_luu_he_thong import backup, digest


class ThuKhoiPhucDichVu(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "synthetic"
        app = UngDung(self.data, "https://example.invalid", False)
        app.kho.tao_chu("synthetic-password-only")
        app.kho.tao_agent("operator-test", "Synthetic", "operator")
        with app.kho.ket_noi() as db:
            db.execute("INSERT INTO du_an VALUES('project','chu-quan','Synthetic','','',0,0,0)")
            db.execute("INSERT INTO du_an_members VALUES('project','operator-test','editor')")
            db.execute("INSERT INTO office_files VALUES('file','project','synthetic.txt','chu-quan',1,1,0,0,0)")
            content = b"SYNTHETIC PRIVATE CONTENT NOT FOR OUTPUT"
            db.execute("INSERT INTO office_versions VALUES('file',1,?,?,?,?,0)",
                       (content, len(content), hashlib.sha256(content).hexdigest(), "chu-quan"))
            task = {"id": "task", "owner": "chu-quan", "status": "completed", "runtime_running": False}
            db.execute("INSERT INTO cong_viec_tasks VALUES('task','chu-quan',0,0,'completed',?)", (json.dumps(task),))
        app.schedules.close()
        app.tasks.close()
        app.core.audit.close()
        self.bundle, self.destination = self.root / "snapshot", self.root / "restored-new"
        backup(self.data, self.bundle)
        self.original_hash = digest(self.bundle / "data/van-hanh.db")

    def run_fixture(self, **kwargs):
        return run_drill(self.bundle, self.destination, ROOT, mode="synthetic", **kwargs)

    def test_gateway_real_subprocess_restores_data_identity_and_stops_cleanly(self):
        report, code = self.run_fixture()
        self.assertEqual(code, 0, report)
        self.assertEqual(report["status"], "ok")
        self.assertTrue(all(report["checks"].values()), report)
        self.assertEqual(report["counts"], {"files": 1, "versions": 1, "projects": 1, "tasks": 1})
        self.assertFalse(report["isolation_verified"])
        self.assertFalse(report["schedules_started"])
        self.assertFalse(report["external_services_tested"])
        self.assertFalse(report["whole_host_recovery_tested"])
        self.assertEqual(digest(self.bundle / "data/van-hanh.db"), self.original_hash)
        for private in (str(self.root), "SYNTHETIC PRIVATE CONTENT", "synthetic-password", "operator-test", "token_hash"):
            self.assertNotIn(private, json.dumps(report))

    def test_existing_destination_is_retained_and_source_unchanged(self):
        self.destination.mkdir()
        (self.destination / "keep").write_text("keep")
        report, code = self.run_fixture()
        self.assertEqual(code, 1)
        self.assertFalse(report["checks"]["data_restore"])
        self.assertEqual((self.destination / "keep").read_text(), "keep")
        self.assertEqual(digest(self.bundle / "data/van-hanh.db"), self.original_hash)

    def test_mode_isolated_fails_closed_before_copy_when_not_enforced(self):
        with patch("v28_khoi_phuc_dich_vu.isolated_network", return_value=False):
            report, code = run_drill(self.bundle, self.destination, ROOT)
        self.assertEqual(code, 1)
        self.assertFalse(self.destination.exists())
        self.assertFalse(report["isolation_verified"])

    def test_synthetic_rejects_configuration_even_without_keys(self):
        configured = self.root / "configured"
        (self.data / "model-private.json").write_text('{}')
        backup(self.data, configured)
        report, code = run_drill(configured, self.destination, ROOT, mode="synthetic")
        self.assertEqual(code, 1)
        self.assertFalse(self.destination.exists())

    def test_synthetic_rejects_schedule_and_no_output_of_payload(self):
        with closing(sqlite3.connect(self.data / "van-hanh.db")) as db:
            db.execute("INSERT INTO schedules VALUES('schedule','chu-quan','Synthetic','{}',900,1,0,'scheduled','',0)")
            db.commit()
        scheduled = self.root / "scheduled"
        backup(self.data, scheduled)
        report, code = run_drill(scheduled, self.destination, ROOT, mode="synthetic")
        self.assertEqual(code, 1)
        self.assertFalse(self.destination.exists())
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_corrupt_snapshot_denied_before_copy(self):
        with (self.bundle / "data/van-hanh.db").open("ab") as output:
            output.write(b"corruption")
        report, code = self.run_fixture()
        self.assertEqual(code, 1)
        self.assertFalse(self.destination.exists())

    def test_missing_owner_gives_failed_readiness_and_still_stops_worker(self):
        with closing(sqlite3.connect(self.data / "van-hanh.db")) as db:
            db.execute("DELETE FROM chu")
            db.commit()
        ownerless = self.root / "ownerless"
        backup(self.data, ownerless)
        report, code = run_drill(ownerless, self.destination, ROOT, mode="synthetic")
        self.assertEqual(code, 1)
        self.assertFalse(report["checks"]["ready"])
        self.assertTrue(report["checks"]["worker_stopped_cleanly"])

    def test_production_and_worker_paths_are_rejected(self):
        for target in ("/var/lib/bdsg-thanhhoa/new-drill", "/etc/bdsg-thanhhoa/new-drill", "/srv/bdsg-thanhhoa/open-bdsg/new-drill"):
            report, code = run_drill(self.bundle, target, ROOT, mode="synthetic")
            self.assertEqual(code, 1)
            self.assertFalse(report["checks"]["data_restore"])
            self.assertEqual(_worker(target, ROOT, "synthetic"), 1)

    def test_invalid_arguments_and_environment_do_not_echo_private_values(self):
        report, code = run_drill(self.bundle, self.destination, ROOT, mode="PRIVATE-INVALID-MODE")
        self.assertEqual(code, 1)
        self.assertEqual(report["mode"], "invalid")
        self.assertNotIn("PRIVATE-INVALID-MODE", json.dumps(report))
        with patch.dict(os.environ, {"BDSG_MODEL_API_KEY": "secret", "HTTPS_PROXY": "secret", "PYTHONPATH": "private"}):
            env = _environment()
        self.assertFalse(any(key.startswith("BDSG_") for key in env))
        self.assertNotIn("HTTPS_PROXY", env)
        self.assertNotIn("PYTHONPATH", env)

    def test_payload_grants_and_task_ownership_changes_are_detected_after_startup(self):
        stop = gateway_drill._stop
        def change_clone(process):
            result = stop(process)
            with closing(sqlite3.connect(self.destination / "data/van-hanh.db")) as db:
                db.execute("UPDATE office_versions SET content=?", (b"changed synthetic body",))
                db.execute("UPDATE du_an_members SET role='viewer'")
                db.execute("UPDATE cong_viec_tasks SET owner='operator-test'")
                db.commit()
            return result
        with patch("v28_khoi_phuc_dich_vu._stop", side_effect=change_clone):
            report, code = self.run_fixture()
        self.assertEqual(code, 1)
        self.assertTrue(report["checks"]["ready"])
        self.assertTrue(report["checks"]["counts_preserved"])
        self.assertFalse(report["checks"]["identity_preserved"])
        self.assertFalse(report["checks"]["saved_files_projects_preserved"])
        self.assertFalse(report["checks"]["task_ownership_preserved"])
        self.assertEqual(digest(self.bundle / "data/van-hanh.db"), self.original_hash)

    def test_network_guard_requires_no_privilege_and_only_loopback(self):
        def guard(status, interfaces):
            def read(path, **_):
                return status if path.as_posix() == "/proc/self/status" else interfaces
            with patch("v28_khoi_phuc_dich_vu.sys.platform", "linux"), \
                 patch("v28_khoi_phuc_dich_vu.os.geteuid", return_value=999, create=True), \
                 patch("v28_khoi_phuc_dich_vu.Path.read_text", read):
                return isolated_network()
        status = "CapEff:\t0000000000000000\nNoNewPrivs:\t1\n"
        self.assertTrue(guard(status, "lo: 0 0 0 0\n"))
        self.assertFalse(guard(status, "lo: 0\neth0: 0\n"))
        self.assertFalse(guard(status.replace("NoNewPrivs:\t1", "NoNewPrivs:\t0"), "lo: 0\n"))
        self.assertFalse(guard(status.replace("0000000000000000", "0000000000000001"), "lo: 0\n"))

    def test_worker_start_failure_keeps_private_exception_out_of_report(self):
        with patch("v28_khoi_phuc_dich_vu.subprocess.Popen", side_effect=OSError("PRIVATE-FAILURE-PATH")):
            report, code = self.run_fixture()
        self.assertEqual(code, 1)
        self.assertTrue(report["checks"]["data_restore"])
        self.assertNotIn("PRIVATE-FAILURE-PATH", json.dumps(report))

    @unittest.skipUnless(os.name == "posix", "Kiểm symlink cần POSIX")
    def test_symlink_ancestors_and_destination_refused(self):
        link = self.root / "alias"
        link.symlink_to(self.bundle, target_is_directory=True)
        report, code = run_drill(link, self.destination, ROOT, mode="synthetic")
        self.assertEqual(code, 1)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
