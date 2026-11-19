"""Shared launch boundary: expose only /usr read-only and the new job directory."""

from pathlib import Path
import os


def command_for():
    if os.name != "posix" or os.geteuid() == 0:
        raise ValueError(
            "Vùng thực thi yêu cầu tài khoản dịch vụ Linux không phải root"
        )
    helper = Path(__file__).with_name("python_co_lap.py").resolve()
    return [
        "/usr/bin/bwrap",
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--ro-bind",
        "/usr",
        "/usr",
        "--symlink",
        "usr/lib",
        "/lib",
        "--symlink",
        "usr/lib64",
        "/lib64",
        "--symlink",
        "usr/bin",
        "/bin",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--size",
        "1048576",
        "--tmpfs",
        "/tmp",
        "--size",
        "4194304",
        "--tmpfs",
        "/work",
        "--ro-bind",
        str(helper),
        "/runtime.py",
        "--remount-ro",
        "/",
        "--remount-ro",
        "/dev",
        "--remount-ro",
        "/proc",
        "--chdir",
        "/work",
        "--clearenv",
        "--setenv",
        "PATH",
        "/usr/bin",
        "--setenv",
        "HOME",
        "/tmp",
        "/usr/bin/python3",
        "-I",
        "/runtime.py",
    ]
