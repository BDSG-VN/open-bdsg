"""Entrypoint read-only inside bubblewrap; no network/process creation after setup."""

import ctypes
import errno
import json
import os
import resource
import stat
import sys
import base64
import io
import logging
import warnings


def main():
    resource.setrlimit(resource.RLIMIT_AS, (160 * 1024 * 1024, 160 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    # seccomp is irreversible with no_new_privs; reject the run if unavailable.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise RuntimeError("no_new_privs unavailable")
    sec = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    sec.seccomp_init.argtypes = [ctypes.c_uint32]
    sec.seccomp_init.restype = ctypes.c_void_p
    sec.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    sec.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    sec.seccomp_load.argtypes = [ctypes.c_void_p]
    sec.seccomp_release.argtypes = [ctypes.c_void_p]
    ctx = sec.seccomp_init(0x7FFF0000)
    if not ctx:
        raise RuntimeError("seccomp unavailable")
    try:
        for name in (
            "clone",
            "clone3",
            "fork",
            "vfork",
            "execve",
            "execveat",
            "socket",
            "socketpair",
            "unshare",
            "setns",
            "mount",
            "umount2",
            "ptrace",
            "process_vm_readv",
            "process_vm_writev",
            "bpf",
            "keyctl",
        ):
            number = sec.seccomp_syscall_resolve_name(name.encode())
            if (
                number >= 0
                and sec.seccomp_rule_add(ctx, 0x50000 | errno.EPERM, number, 0) != 0
            ):
                raise RuntimeError("seccomp rule failed")
        if sec.seccomp_load(ctx) != 0:
            raise RuntimeError("seccomp load failed")
    finally:
        sec.seccomp_release(ctx)
    data = json.load(sys.stdin)
    os.chdir("/work")
    if data.get("mode") == "pdf":
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
    # Arbitrary Python is intentional, inside the namespace/seccomp/resource limits.
    exec(compile(data["code"], "<bdsg-task>", "exec"), {"__name__": "__main__"})


if __name__ == "__main__":
    main()
