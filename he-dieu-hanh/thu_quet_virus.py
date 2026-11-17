"""Không có Unix socket vẫn chặn xuất bản, không giả kết quả quét sạch."""

import unittest
from unittest.mock import patch

import quet_virus
from quet_virus import LoiChuaQuetVirus, QuetVirus


class ThuQuetVirus(unittest.TestCase):
    def test_missing_unix_socket_reports_unavailable_and_never_marks_clean(self):
        scanner = QuetVirus("/test-only/clamd.socket")
        with patch.object(quet_virus.socket, "AF_UNIX", None, create=True):
            self.assertEqual(scanner.status()["state"], "tam-khong-san-sang")
            for _ in range(3):
                with self.assertRaises(LoiChuaQuetVirus):
                    scanner.scan(b"synthetic-test")


if __name__ == "__main__":
    unittest.main()
