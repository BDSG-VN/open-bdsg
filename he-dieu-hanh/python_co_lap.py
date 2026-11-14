"""Namespace entrypoint: finite preallocated files, seccomp, memory/CPU/file limits."""

import base64
import builtins
import contextlib
import ctypes
import errno
import io
import json
import logging
import os
import resource
import stat
import sys
import warnings


def restrict():
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise RuntimeError("no_new_privs unavailable")
    sec = ctypes.CDLL("libseccomp.so.2", use_errno=True)

    class Compare(ctypes.Structure):
        _fields_ = [
            ("arg", ctypes.c_uint),
            ("op", ctypes.c_int),
            ("a", ctypes.c_uint64),
            ("b", ctypes.c_uint64),
        ]

    sec.seccomp_init.argtypes = [ctypes.c_uint32]
    sec.seccomp_init.restype = ctypes.c_void_p
    sec.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    sec.seccomp_rule_add_array.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.POINTER(Compare),
    ]
    sec.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    sec.seccomp_load.argtypes = [ctypes.c_void_p]
    sec.seccomp_release.argtypes = [ctypes.c_void_p]
    ctx = sec.seccomp_init(0x50000 | errno.EPERM)
    if not ctx:
        raise RuntimeError("seccomp unavailable")
    try:
        # Default deny: no process/network/IPC/io_uring or future syscall bypasses.
        allowed = (
            "read write readv writev pread64 pwrite64 preadv pwritev preadv2 pwritev2 lseek close close_range fstat newfstatat stat lstat statx access faccessat faccessat2 getdents64 readlink readlinkat mmap mprotect munmap mremap madvise brk rt_sigaction rt_sigprocmask rt_sigreturn sigaltstack futex futex_waitv set_robust_list rseq getrandom clock_gettime clock_nanosleep nanosleep gettimeofday time getpid getppid gettid getuid geteuid getgid getegid getresuid getresgid uname sysinfo sched_getaffinity sched_yield getcpu fcntl ioctl dup dup2 dup3 pipe pipe2 poll ppoll pselect6 select ftruncate fdatasync fsync getcwd chdir fchdir umask prlimit64 getrlimit getrusage times exit exit_group restart_syscall"
        ).split()
        for name in allowed:
            number = sec.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and sec.seccomp_rule_add(ctx, 0x7FFF0000, number, 0) != 0:
                raise RuntimeError("seccomp rule failed")
        # Prevent arbitrary inode creation, including unnamed O_TMPFILE files.
        for name, index in (("open", 1), ("openat", 2)):
            number = sec.seccomp_syscall_resolve_name(name.encode())
            if number < 0:
                continue
            mask = os.O_CREAT | (getattr(os, "O_TMPFILE", 0) & ~os.O_DIRECTORY)
            comparison = (Compare * 1)(Compare(index, 7, mask, 0))
            if sec.seccomp_rule_add_array(ctx, 0x7FFF0000, number, 1, comparison) != 0:
                raise RuntimeError("seccomp open rule failed")
        if sec.seccomp_load(ctx) != 0:
            raise RuntimeError("seccomp load failed")
    finally:
        sec.seccomp_release(ctx)


def main():
    resource.setrlimit(resource.RLIMIT_AS, (160 * 1024 * 1024, 160 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    data = json.load(sys.stdin)
    os.chdir("/work")
    if data.get("mode") == "pdf":
        restrict()
        logging.disable(logging.CRITICAL)
        warnings.filterwarnings("ignore")
        from pypdf import PdfReader

        pdf = PdfReader(
            io.BytesIO(base64.b64decode(data["data"], validate=True)), strict=True
        )
        if pdf.is_encrypted or len(pdf.pages) > 50:
            raise ValueError("PDF unsupported")
        text = ""
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
            if len(text) > 16000:
                break
        if not text.strip():
            raise ValueError("PDF has no text")
        print(
            json.dumps(
                {"text": text[:16000], "truncated": len(text) > 16000},
                ensure_ascii=False,
            )
        )
        return
    for index, doc in enumerate(data.get("documents", [])):
        with open("input-" + str(index + 1) + ".txt", "x", encoding="utf-8") as f:
            f.write(doc["text"])
    names = data.get("output_names", [])
    for name in names:
        with open(name, "x"):
            pass
    log = open("/work/.stdout", "w+", encoding="utf-8")
    original_open = builtins.open

    def bounded_open(file, mode="r", *args, **kwargs):
        if (
            isinstance(file, (str, bytes, os.PathLike))
            and os.path.abspath(file) in ["/work/" + n for n in names]
            and any(m in mode for m in ("w", "a"))
        ):
            flags = os.O_RDWR | (os.O_TRUNC if "w" in mode else os.O_APPEND)
            fd = os.open(file, flags)
            return original_open(fd, mode, *args, **kwargs)
        return original_open(file, mode, *args, **kwargs)

    # This wrapper is for usability; the kernel rejects bypasses that create inodes.
    restricted_builtins = {**vars(builtins), "open": bounded_open}
    restrict()
    ok = True
    try:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            exec(
                compile(data["code"], "<bdsg-task>", "exec"),
                {"__name__": "__main__", "__builtins__": restricted_builtins},
            )
    except BaseException:
        ok = False
    try:
        log.flush()
        log.seek(0)
        stdout = log.read(16000)
    except Exception:
        stdout = ""
    artifacts = []
    total = 0
    if ok:
        for name in names:
            fd = None
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                info = os.fstat(fd)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or not info.st_size
                    or info.st_size > 256000
                    or total + info.st_size > 512000
                ):
                    continue
                with os.fdopen(fd, "rb") as f:
                    fd = None
                    raw = f.read(256001)
                content = raw.decode("utf-8")
                if "\x00" in content:
                    continue
                total += len(raw)
                artifacts.append({"name": name, "content": content})
            except (OSError, UnicodeDecodeError):
                continue
            finally:
                if fd is not None:
                    os.close(fd)
    print(
        json.dumps(
            {"ok": ok, "stdout": stdout, "artifacts": artifacts}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
