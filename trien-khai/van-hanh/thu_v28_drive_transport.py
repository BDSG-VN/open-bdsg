"""Kiểm tra transport bằng tiến trình giả, không gọi Google Drive."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from v28_drive_transport import TransportError, _BoundedOutput, _run, upload_age


class FakeDrive:
    def __init__(self, mode="ok"):
        self.mode, self.calls, self.data, self.name = mode, [], None, None

    def __call__(self, argv, output, timeout):
        self.calls.append(argv)
        if self.mode == "failure":
            raise TransportError("Tiến trình thất bại")
        if "listremotes" in argv:
            output.write(b"backup:drive" if self.mode == "wrong_backend" else b"backup:\n")
        elif "copyto" in argv:
            index = argv.index("copyto")
            self.data = Path(argv[index + 1]).read_bytes()
            self.name = argv[index + 2].split("/")[-1]
            self.assert_no_delete = not any(x in argv for x in ("delete", "sync", "purge"))
        elif "lsjson" in argv:
            entries = [] if self.data is None else [{"Name": self.name, "Size": len(self.data)}]
            if self.mode == "bad_metadata" and self.data is not None:
                entries[0]["Size"] += 1
            output.write(json.dumps(entries).encode())
        elif "cat" in argv:
            output.write(self.data + b"bad" if self.mode == "oversized" else
                         self.data.replace(b"cipher", b"broken") if self.mode == "corrupt" else self.data)


class DriveTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.config, self.executable = [self.root / name for name in
                                                   ("source.age", "private.conf", "rclone")]
        self.source.write_bytes(b"age-encryption.org/v1\ncipher")
        self.config.write_text("not read by transport")
        self.executable.write_bytes(b"fake")
        self.args = dict(config=self.config, executable=self.executable, remote="backup",
                         prefix="BDSGtotal/offsite", allowed_destination="backup:BDSGtotal/offsite")

    def test_readback_receipt_excludes_private_paths(self):
        fake = FakeDrive()
        report = upload_age(self.source, **self.args, runner=fake)
        self.assertEqual(report["encrypted_sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertFalse(report["decryption_verified"])
        self.assertEqual(report["status"], "verified")
        self.assertNotIn(str(self.root), json.dumps(report))
        self.assertNotIn("BDSGtotal", json.dumps(report))
        copy = next(call for call in fake.calls if "copyto" in call)
        self.assertIn("--immutable", copy)
        self.assertIn("--ignore-existing", copy)

    def test_metadata_or_receipt_claim_cannot_replace_readback(self):
        for mode in ("wrong_backend", "bad_metadata", "corrupt", "oversized", "failure"):
            with self.subTest(mode=mode), self.assertRaises(TransportError):
                upload_age(self.source, **self.args, runner=FakeDrive(mode))

    def test_malformed_paths_do_not_run_transport(self):
        for key, values in {"remote": [":drive", "-x", "backup,token=x"],
                            "prefix": ["", "../x", "x//y", "/x", "x\\y", "x:y"],
                            "allowed_destination": ["other:offsite"],
                            "timeout": [0, float("nan"), float("inf")]}.items():
            for value in values:
                fake = FakeDrive()
                args = self.args | {key: value}
                with self.subTest(key=key, value=value), self.assertRaises(TransportError):
                    upload_age(self.source, **args, runner=fake)
                self.assertFalse(fake.calls)

    def test_reject_plaintext_even_with_age_extension(self):
        self.source.write_bytes(b"cleartext" * 10)
        fake = FakeDrive()
        with self.assertRaises(TransportError):
            upload_age(self.source, **self.args, runner=fake)
        self.assertFalse(any("copyto" in call for call in fake.calls))

    def test_existing_object_refused(self):
        fake = FakeDrive()
        fixed = type("Id", (), {"hex": "a" * 32})()
        fake.name = hashlib.sha256(self.source.read_bytes()).hexdigest() + "-" + fixed.hex + ".age"
        fake.data = self.source.read_bytes()
        with patch("v28_drive_transport.uuid.uuid4", return_value=fixed), self.assertRaises(TransportError):
            upload_age(self.source, **self.args, runner=fake)
        self.assertFalse(any("copyto" in call for call in fake.calls))

    def test_real_adapter_nonzero_timeout_and_oversize_are_sanitized(self):
        scripts = [("import sys; print('SECRET',file=sys.stderr);sys.exit(2)", 2),
                   ("import time;time.sleep(3)", 0.1),
                   ("print('x'*100)", 2)]
        for script, timeout in scripts:
            with self.subTest(script=script), tempfile.TemporaryFile() as output:
                with self.assertRaises(TransportError) as error:
                    _run([sys.executable, "-c", script], _BoundedOutput(output, 10), timeout)
                self.assertNotIn("SECRET", str(error.exception))

    def test_strip_inherited_rclone_overrides(self):
        with tempfile.TemporaryFile() as output, patch.dict(os.environ, {"RCLONE_PASSWORD_COMMAND": "bad"}):
            _run([sys.executable, "-c", "import os;print(any(k.startswith('RCLONE_') for k in os.environ))"],
                 _BoundedOutput(output, 100), 5)
            output.seek(0)
            self.assertEqual(output.read().strip(), b"False")


if __name__ == "__main__":
    unittest.main()
