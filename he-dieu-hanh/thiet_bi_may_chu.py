"""Ảnh chụp máy chạy ứng dụng; chỉ đọc metadata trong danh sách cho phép."""

import copy
import math
import platform
import re
import shutil
import threading
import time
from datetime import datetime, timezone


_FILES = {
    "/etc/os-release": 8192,
    "/proc/sys/kernel/osrelease": 256,
    "/proc/cpuinfo": 262144,
    "/proc/meminfo": 16384,
    "/proc/loadavg": 256,
    "/proc/uptime": 256,
    "/sys/class/dmi/id/sys_vendor": 256,
    "/sys/class/dmi/id/product_name": 256,
    "/sys/hypervisor/type": 256,
}
_THRESHOLDS = {
    "memory_used_percent": 90,
    "storage_used_percent": 90,
    "storage_free_bytes": 1024 ** 3,
}


class _DocHeThong:
    def read(self, path, limit):
        # Đọc dư một byte để từ chối dữ liệu bị cắt, thay vì đoán số còn thiếu.
        with open(path, "rb") as source:
            value = source.read(limit + 1)
        if len(value) > limit:
            raise ValueError("metadata_too_large")
        return value.decode("utf-8", errors="strict")

    def machine(self):
        return platform.machine()

    def disk_usage(self, path):
        return shutil.disk_usage(path)


def _so(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and 0 <= result <= 10 ** 18 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _nguyen(value):
    result = _so(value)
    return int(result) if result is not None and result == int(result) else None


class ThietBiMayChu:
    """snapshot() trả bản sao JSON an toàn; cache tối đa năm giây, không lấy mẫu nền.

    reader có read(path, limit), machine(), disk_usage(data_dir). Hai adapter
    thật/giả cùng interface giúp kiểm lỗi quyền và proc mà không đụng máy chủ.
    node_id là nhãn vận hành, không phải chứng thực thiết bị.
    """

    def __init__(self, data_dir, node_id=None, reader=None, clock=None, monotonic=None):
        self.data_dir = data_dir
        self.node_id = node_id if isinstance(node_id, str) and re.fullmatch(
            r"[A-Z][A-Z0-9_-]{0,31}", node_id
        ) else "TH01"
        self.reader = reader or _DocHeThong()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic or time.monotonic
        self._lock = threading.Lock()
        self._cached = None
        self._cached_at = None
        self._expires = 0

    def snapshot(self):
        with self._lock:
            now = self.monotonic()
            if self._cached is None or now >= self._expires or now < self._cached_at:
                self._cached = self._collect()
                self._cached_at = now
                self._expires = now + 5
            return copy.deepcopy(self._cached)

    def _read(self, path):
        try:
            value = self.reader.read(path, _FILES[path])
            if not isinstance(value, str) or len(value.encode("utf-8")) > _FILES[path]:
                return ""
            return value
        except (OSError, ValueError, UnicodeError):
            return ""

    def _collect(self):
        release = {}
        for line in self._read("/etc/os-release").splitlines():
            key, sep, value = line.partition("=")
            if sep and key in ("ID", "VERSION_ID"):
                release[key] = value.strip('"\'')
        distro = release.get("ID")
        version = release.get("VERSION_ID", "")
        os_name = None
        if distro in ("ubuntu", "debian", "fedora", "rhel", "centos", "rocky", "almalinux", "alpine", "arch", "opensuse-leap"):
            os_name = distro + (" " + version if re.fullmatch(r"\d+(?:\.\d+){0,3}", version) else "")
        kernel = self._read("/proc/sys/kernel/osrelease").strip()
        if not re.fullmatch(r"\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9_.+-]{1,64})?", kernel):
            kernel = None
        try:
            architecture = self.reader.machine()
        except OSError:
            architecture = None
        if architecture not in ("x86_64", "aarch64", "arm64", "i386", "i686", "armv7l", "ppc64le", "s390x", "riscv64", "AMD64"):
            architecture = None
        dmi = " ".join(self._read(path).lower() for path in (
            "/sys/class/dmi/id/sys_vendor", "/sys/class/dmi/id/product_name", "/sys/hypervisor/type"
        ))
        provider = next((name for pattern, name in (
            ("vmware", "vmware"), ("virtualbox", "virtualbox"),
            ("kvm", "kvm"), ("qemu", "qemu"), ("xen", "xen"),
            ("microsoft corporation virtual machine", "microsoft"),
        ) if pattern in dmi), None)
        cpu_info = self._read("/proc/cpuinfo")
        processors = re.findall(r"^processor\s*:\s*(\d+)\s*$", cpu_info, re.M)
        logical_count = len(set(processors)) or None
        model = None
        for line in cpu_info.splitlines():
            key, _, value = line.partition(":")
            if key.strip() in ("model name", "Hardware"):
                candidate = value.strip()
                # Chỉ nhận mẫu nhãn CPU phổ biến; không đưa toàn bộ cpuinfo/DMI ra ngoài.
                if re.fullmatch(r"(?:Intel|AMD|ARM|Ampere|IBM|Qualcomm|Apple)[A-Za-z0-9 ()@.+_-]{0,140}", candidate) and not re.search(r"\d+\.\d+\.\d+\.\d+", candidate):
                    model = candidate
                break
        loads = self._read("/proc/loadavg").split()
        load_values = [_so(value) for value in loads[:3]] if len(loads) >= 3 else [None] * 3
        uptime_parts = self._read("/proc/uptime").split()
        uptime = _so(uptime_parts[0]) if uptime_parts else None
        mem = {}
        for line in self._read("/proc/meminfo").splitlines():
            match = re.fullmatch(r"(MemTotal|MemAvailable):\s+(\d+)\s+kB", line)
            if match:
                value = _nguyen(match[2])
                mem[match[1]] = value * 1024 if value is not None else None
        total, available = mem.get("MemTotal"), mem.get("MemAvailable")
        if total is not None and total <= 0:
            total = None
        if available is not None and (total is None or available > total):
            available = None
        memory_percent = round((total - available) / total * 100, 2) if total is not None and available is not None else None
        disk_total = disk_used = disk_free = disk_percent = None
        try:
            disk = self.reader.disk_usage(self.data_dir)
            values = [_nguyen(value) for value in (disk.total, disk.used, disk.free)]
            if all(value is not None for value in values):
                dt, du, df = values
                if dt > 0 and du <= dt and df <= dt and du + df <= dt:
                    disk_total, disk_used, disk_free = values
                    disk_percent = round(du / dt * 100, 2)
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        result = {
            "node": {"id": self.node_id, "attested": False},
            "observed_at": self.clock().astimezone(timezone.utc).isoformat(),
            "host": {"os": os_name, "kernel": kernel, "architecture": architecture,
                     "virtualization": {"provider": provider, "status": "detected" if provider else "unknown"},
                     "uptime_seconds": int(uptime) if uptime is not None else None},
            "cpu": {"model": model, "logical_count": logical_count,
                    "load_average": dict(zip(("one", "five", "fifteen"), load_values))},
            "memory": {"total_bytes": total, "available_bytes": available, "used_percent": memory_percent},
            "storage": {"scope": "application-data-filesystem", "total_bytes": disk_total,
                        "used_bytes": disk_used, "free_bytes": disk_free, "used_percent": disk_percent},
            "alerts": [], "thresholds": dict(_THRESHOLDS),
        }
        for value, threshold, code in (
            (memory_percent, _THRESHOLDS["memory_used_percent"], "high_memory"),
            (disk_percent, _THRESHOLDS["storage_used_percent"], "high_disk_usage")
        ):
            if value is not None and value >= threshold:
                result["alerts"].append({"code": code, "severity": "warning"})
        if disk_free is not None and disk_free < _THRESHOLDS["storage_free_bytes"]:
            result["alerts"].append({"code": "low_disk", "severity": "warning"})
        unknown = []

        def find_unknown(value, prefix):
            for key, item in value.items():
                path = prefix + "." + key if prefix else key
                if isinstance(item, dict):
                    find_unknown(item, path)
                elif item is None:
                    unknown.append(path)

        for key in ("host", "cpu", "memory", "storage"):
            find_unknown(result[key], key)
        measured = [os_name, kernel, architecture, uptime, model, logical_count,
                    total, available, disk_total, provider] + load_values
        result["unknown"] = unknown
        result["status"] = "unknown" if all(value is None for value in measured) else "partial" if unknown else "ok"
        return result
