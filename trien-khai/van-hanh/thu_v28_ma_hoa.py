"""Kiểm ranh giới đóng gói/publication với tiến trình age giả, không thử mật mã."""

import io
import json
import os
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import v28_ma_hoa
from sao_luu_he_thong import backup


class _Input(io.BytesIO):
    def close(self):
        # Tiến trình giả cần giữ buffer để xác minh tar nhận qua stdin.
        pass


class _FakeAge:
    def __init__(self, command, *, stdin, stdout, stderr, **kwargs):
        self.stdin, self.output, self.returncode = _Input(), stdout, None
        self.fail = False

    def wait(self, timeout=None):
        if self.returncode is None:
            self.output.write(b"age-encryption.org/v1\n" + self.stdin.getvalue())
            self.returncode = 1 if self.fail else 0
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = 1


class ThuMaHoa(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / "source"
        source.mkdir()
        with closing(sqlite3.connect(source / "van-hanh.db")) as db:
            db.executescript("CREATE TABLE demo(value TEXT); INSERT INTO demo VALUES('TONG-HOP');")
        self.bundle = self.root / "bundle"
        backup(source, self.bundle)
        self.output = self.root / "archive.tar.age"
        self.recipients = self.root / "recipients.txt"
        self.recipients.write_text("# chi khoa cong khai\nage1" + "q" * 58 + "\n", encoding="utf-8")
        self.processes = []

        def factory(*args, **kwargs):
            process = _FakeAge(*args, **kwargs)
            self.processes.append(process)
            return process

        self.run_patch = patch.object(v28_ma_hoa.subprocess, "run", return_value=
                                      subprocess.CompletedProcess([], 0, b"v1.3.2\n"))
        self.popen_patch = patch.object(v28_ma_hoa.subprocess, "Popen", side_effect=factory)
        self.run = self.run_patch.start()
        self.popen = self.popen_patch.start()
        self.addCleanup(self.run_patch.stop)
        self.addCleanup(self.popen_patch.stop)

    def encrypt(self):
        # sys.executable chỉ là tệp thường cho fake adapter; không thực thi Python.
        return v28_ma_hoa.encrypt_bundle(self.bundle, self.output, self.recipients, Path(sys.executable).resolve())

    def test_tar_stream_chi_co_goi_da_kiem_va_ten_tuong_doi(self):
        report = self.encrypt()
        self.assertEqual(report["status"], "encrypted")
        self.assertFalse(report["decryption_verified"])
        self.assertEqual(report["offsite"], {"configured": False})
        with tarfile.open(fileobj=io.BytesIO(self.processes[0].stdin.getvalue())) as archive:
            self.assertEqual(archive.getnames(), ["manifest.json", "data/van-hanh.db"])
            self.assertEqual(archive.extractfile("data/van-hanh.db").read(),
                             (self.bundle / "data/van-hanh.db").read_bytes())
            for member in archive.getmembers():
                self.assertTrue(member.isfile())
                self.assertEqual(member.uid, 0)
                self.assertEqual(member.uname, "")
        self.assertTrue(self.output.is_file())
        self.assertFalse(self.output.with_name(self.output.name + ".part").exists())
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_khong_ghi_de_dich_cu(self):
        self.output.write_bytes(b"KEEP-EXISTING")
        with self.assertRaises(FileExistsError):
            self.encrypt()
        self.assertEqual(self.output.read_bytes(), b"KEEP-EXISTING")
        self.popen.assert_not_called()

    def test_khong_xoa_partial_da_co(self):
        part = self.output.with_name(self.output.name + ".part")
        part.write_bytes(b"KEEP-OLD-PART")
        with self.assertRaises(FileExistsError):
            self.encrypt()
        self.assertEqual(part.read_bytes(), b"KEEP-OLD-PART")
        self.assertFalse(self.output.exists())

    def test_age_loi_chi_xoa_partial_cua_luot_nay(self):
        def factory(*args, **kwargs):
            process = _FakeAge(*args, **kwargs)
            process.fail = True
            return process
        self.popen.side_effect = factory
        with self.assertRaises(ValueError):
            self.encrypt()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_name(self.output.name + ".part").exists())
        self.assertTrue((self.bundle / "data/van-hanh.db").is_file())

    def test_dich_xuat_hien_trong_luc_ma_hoa_khong_bi_ghi_de(self):
        original = _FakeAge.wait
        def wait(process, timeout=None):
            self.output.write_bytes(b"NEW-OWNER-DATA")
            return original(process, timeout)
        with patch.object(_FakeAge, "wait", wait):
            with self.assertRaises(FileExistsError):
                self.encrypt()
        self.assertEqual(self.output.read_bytes(), b"NEW-OWNER-DATA")
        self.assertFalse(self.output.with_name(self.output.name + ".part").exists())

    def test_goi_hong_bi_chan_truoc_ma_hoa(self):
        with (self.bundle / "data/van-hanh.db").open("ab") as stream:
            stream.write(b"tamper")
        with self.assertRaises(ValueError):
            self.encrypt()
        self.popen.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_tu_choi_dich_trong_goi_va_recipient_plugin_private_key(self):
        self.output = self.bundle / "new.age"
        with self.assertRaises(ValueError):
            self.encrypt()
        self.output = self.root / "outside.age"
        for value in ("age1plugin1something", "AGE-SECRET-KEY-1PRIVATE", "ssh-ed25519 anything", ""):
            with self.subTest(value=value):
                self.recipients.write_text(value, encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.encrypt()
        self.popen.assert_not_called()

    def test_tu_choi_age_khac_phien_ban(self):
        self.run.return_value = subprocess.CompletedProcess([], 0, b"v0.0.0-unknown\n")
        with self.assertRaises(ValueError):
            self.encrypt()
        self.popen.assert_not_called()

    def test_goi_doi_sau_verify_bi_chan_va_don_partial(self):
        def factory(*args, **kwargs):
            with (self.bundle / "data/van-hanh.db").open("ab") as stream:
                stream.write(b"changed-during-encryption")
            return _FakeAge(*args, **kwargs)
        self.popen.side_effect = factory
        with self.assertRaises(ValueError):
            self.encrypt()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_name(self.output.name + ".part").exists())

    def test_tien_trinh_qua_han_bi_dung_va_don_partial(self):
        stopped = threading.Event()
        original_kill = _FakeAge.kill
        def kill(process):
            original_kill(process)
            stopped.set()
        def waiting_archive(*args):
            self.assertTrue(stopped.wait(timeout=2))
        with patch.object(_FakeAge, "kill", kill), patch.object(v28_ma_hoa, "_archive", waiting_archive):
            with self.assertRaises(ValueError):
                v28_ma_hoa.encrypt_bundle(self.bundle, self.output, self.recipients,
                                         Path(sys.executable).resolve(), timeout=0.01)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_name(self.output.name + ".part").exists())

    def test_cli_khong_lo_ngoai_le_va_duong_dan(self):
        self.output.write_bytes(b"KEEP")
        arguments = ["v28_ma_hoa.py", "--bundle", str(self.bundle), "--destination", str(self.output),
                     "--recipients-file", str(self.recipients), "--age-executable", str(Path(sys.executable).resolve())]
        stdout = io.StringIO()
        with patch.object(sys, "argv", arguments), redirect_stdout(stdout):
            self.assertEqual(v28_ma_hoa.main(), 1)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "failed")
        self.assertNotIn(str(self.root), stdout.getvalue())

    @unittest.skipIf(os.name == "nt", "Windows cần quyền tạo symlink riêng")
    def test_tu_choi_lien_ket(self):
        real = self.recipients
        self.recipients = self.root / "recipients-link.txt"
        self.recipients.symlink_to(real)
        with self.assertRaises(ValueError):
            self.encrypt()
        self.popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
