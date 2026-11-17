"""Kiểm interface ảnh chụp bằng metadata tổng hợp, không gọi máy chủ thật."""

import json
import unittest
from collections import namedtuple
from datetime import datetime, timezone

from thiet_bi_may_chu import ThietBiMayChu


Disk = namedtuple("Disk", "total used free")


class DocGia:
    def __init__(self):
        self.files = {
            "/etc/os-release": 'ID=ubuntu\nVERSION_ID="24.04"\nPRETTY_NAME="private-host"',
            "/proc/sys/kernel/osrelease": "6.8.0-31-generic\n",
            "/proc/cpuinfo": "processor : 0\nmodel name : Intel(R) Test CPU @ 2.00GHz\nprocessor : 1\nSerial : private-serial\n",
            "/proc/meminfo": "MemTotal: 1000 kB\nMemAvailable: 250 kB\n",
            "/proc/loadavg": "0.5 1.0 2.0 1/123 321",
            "/proc/uptime": "100.25 500.5",
            "/sys/class/dmi/id/sys_vendor": "VMware, Inc.",
            "/sys/class/dmi/id/product_name": "VMware Virtual Platform",
        }
        self.disk = Disk(10 * 1024 ** 3, 4 * 1024 ** 3, 6 * 1024 ** 3)
        self.calls = []
        self.disk_paths = []
        self.architecture = "x86_64"

    def read(self, path, limit):
        self.calls.append((path, limit))
        value = self.files.get(path, FileNotFoundError())
        if isinstance(value, Exception):
            raise value
        return value

    def machine(self):
        return self.architecture

    def disk_usage(self, path):
        self.disk_paths.append(path)
        if isinstance(self.disk, Exception):
            raise self.disk
        return self.disk


class ThuThietBiMayChu(unittest.TestCase):
    def setUp(self):
        self.reader = DocGia()
        self.tick = 10.0
        self.collector = ThietBiMayChu(
            "/private/application-data", reader=self.reader,
            clock=lambda: datetime(2026, 11, 17, tzinfo=timezone.utc),
            monotonic=lambda: self.tick,
        )

    def test_measured_snapshot_and_actual_filesystem(self):
        value = self.collector.snapshot()
        self.assertEqual(value["node"], {"id": "TH01", "attested": False})
        self.assertEqual(value["observed_at"], "2026-11-17T00:00:00+00:00")
        self.assertEqual(value["status"], "ok")
        self.assertEqual(value["host"]["os"], "ubuntu 24.04")
        self.assertEqual(value["host"]["virtualization"], {"provider": "vmware", "status": "detected"})
        self.assertEqual(value["host"]["uptime_seconds"], 100)
        self.assertEqual(value["cpu"]["logical_count"], 2)
        self.assertEqual(value["cpu"]["load_average"], {"one": 0.5, "five": 1.0, "fifteen": 2.0})
        self.assertEqual(value["memory"], {"total_bytes": 1024000, "available_bytes": 256000, "used_percent": 75.0})
        self.assertEqual(value["storage"]["used_percent"], 40)
        self.assertEqual(self.reader.disk_paths, ["/private/application-data"])
        self.assertEqual(value["alerts"], [])

    def test_cache_is_bounded_and_return_value_is_independent(self):
        first = self.collector.snapshot()
        count = len(self.reader.calls)
        first["node"]["id"] = "MUTATED"
        self.tick = 14.99
        self.assertEqual(self.collector.snapshot()["node"]["id"], "TH01")
        self.assertEqual(len(self.reader.calls), count)
        self.tick = 15
        self.collector.snapshot()
        self.assertEqual(len(self.reader.calls), count * 2)

    def test_monotonic_clock_rollback_refreshes(self):
        self.collector.snapshot()
        count = len(self.reader.calls)
        self.tick = 1
        self.collector.snapshot()
        self.assertEqual(len(self.reader.calls), count * 2)

    def test_missing_and_denied_reads_are_unknown_without_error_details(self):
        self.reader.files = {"/proc/cpuinfo": PermissionError("private-path-secret")}
        self.reader.architecture = "unrecognized"
        self.reader.disk = PermissionError("private-disk-secret")
        value = self.collector.snapshot()
        self.assertEqual(value["status"], "unknown")
        self.assertIsNone(value["host"]["os"])
        self.assertEqual(value["host"]["virtualization"], {"provider": None, "status": "unknown"})
        self.assertIn("memory.available_bytes", value["unknown"])
        self.assertNotIn("private", json.dumps(value))

    def test_corrupt_nonfinite_negative_and_inconsistent_numbers(self):
        self.reader.files.update({
            "/proc/meminfo": "MemTotal: 0 kB\nMemAvailable: 20 kB",
            "/proc/loadavg": "nan inf -1",
            "/proc/uptime": "nan 1",
            "/proc/cpuinfo": "processor : bad\nmodel name : /private/secret",
            "/proc/sys/kernel/osrelease": "host-name /private/key",
        })
        self.reader.disk = Disk(10, 20, 3)
        value = self.collector.snapshot()
        self.assertTrue(all(item is None for item in value["cpu"]["load_average"].values()))
        self.assertIsNone(value["memory"]["total_bytes"])
        self.assertIsNone(value["memory"]["available_bytes"])
        self.assertIsNone(value["storage"]["used_percent"])
        self.assertIsNone(value["host"]["uptime_seconds"])
        self.assertIsNone(value["cpu"]["logical_count"])
        json.dumps(value, allow_nan=False)

    def test_available_memory_over_total_and_bad_disk_values(self):
        self.reader.files["/proc/meminfo"] = "MemTotal: 10 kB\nMemAvailable: 11 kB"
        self.reader.disk = Disk(float("nan"), 0, 0)
        value = self.collector.snapshot()
        self.assertEqual(value["memory"]["total_bytes"], 10240)
        self.assertIsNone(value["memory"]["available_bytes"])
        self.assertIsNone(value["memory"]["used_percent"])
        self.assertIsNone(value["storage"]["total_bytes"])

    def test_alert_thresholds_are_explicit_and_inclusive(self):
        self.reader.files["/proc/meminfo"] = "MemTotal: 1000 kB\nMemAvailable: 100 kB"
        self.reader.disk = Disk(1000, 900, 100)
        value = self.collector.snapshot()
        self.assertEqual([item["code"] for item in value["alerts"]], ["high_memory", "high_disk_usage", "low_disk"])
        self.assertEqual(value["thresholds"]["memory_used_percent"], 90)
        self.assertEqual(value["thresholds"]["storage_free_bytes"], 1024 ** 3)
        self.reader.disk = Disk(10 * 1024 ** 3, 9 * 1024 ** 3, 1024 ** 3)
        self.tick += 5
        self.assertNotIn("low_disk", [item["code"] for item in self.collector.snapshot()["alerts"]])

    def test_no_virtualization_detection_does_not_attest_physical_host(self):
        for path in list(self.reader.files):
            if path.startswith("/sys/"):
                self.reader.files[path] = "generic hardware private-serial"
        value = self.collector.snapshot()
        self.assertEqual(value["host"]["virtualization"]["status"], "unknown")
        self.assertIsNone(value["host"]["virtualization"]["provider"])
        self.assertFalse(value["node"]["attested"])
        self.assertNotIn("gpu", json.dumps(value).lower())

    def test_node_identity_validation(self):
        for value in (None, "", "bad/private", "192.168.1.1", "A" * 33, 123, "bad\nNODE"):
            collector = ThietBiMayChu("private", value, reader=self.reader)
            self.assertEqual(collector.snapshot()["node"]["id"], "TH01")
        self.assertEqual(ThietBiMayChu("private", "TH02_TEST", reader=self.reader).snapshot()["node"]["id"], "TH02_TEST")

    def test_whitelisted_bounded_reads_and_privacy(self):
        self.reader.files["/etc/os-release"] += '\nSECRET="private-token"\nHOSTNAME="private-host"'
        self.reader.files["/proc/cpuinfo"] += "\naddress: 192.168.1.99\npassword: private-token"
        value = self.collector.snapshot()
        output = json.dumps(value)
        for private in ("private-", "192.168.1.99", "/private/", "Serial", "HOSTNAME", "SECRET"):
            self.assertNotIn(private, output)
        self.assertEqual(len(self.reader.calls), 9)
        self.assertTrue(all(0 < limit <= 262144 for _, limit in self.reader.calls))
        self.assertFalse(any("serial" in path or "hostname" in path or "environ" in path for path, _ in self.reader.calls))

    def test_oversized_or_wrong_type_source_is_unknown(self):
        self.reader.files["/proc/cpuinfo"] = "a" * 262145
        self.reader.files["/proc/uptime"] = 123
        value = self.collector.snapshot()
        self.assertIsNone(value["cpu"]["logical_count"])
        self.assertIsNone(value["host"]["uptime_seconds"])


if __name__ == "__main__":
    unittest.main()
