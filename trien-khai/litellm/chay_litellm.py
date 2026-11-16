"""Khởi chạy image đã xác minh, chỉ bind loopback và chỉ đọc một tệp cấu hình."""

import os
import pwd
from pathlib import Path

IMAGE = "ghcr.io/berriai/litellm@sha256:11175975a3093e05e92faee2fe2fe3412a3ae2fcaa849eb0fe25d5f0d8bcb2e9"


def command():
    configuration = Path("/var/lib/bdsg-thanhhoa/litellm-config.json")
    if not configuration.is_file() or configuration.is_symlink():
        raise RuntimeError("Chưa có cấu hình LiteLLM riêng hợp lệ")
    account = pwd.getpwnam("bdsg-thanhhoa")
    return [
        "/usr/bin/docker", "run", "--rm", "--name", "bdsg-thanhhoa-litellm",
        "--user", f"{account.pw_uid}:{account.pw_gid}",
        "--publish", "127.0.0.1:4000:4000", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--pids-limit", "256",
        "--memory", "2g", "--cpus", "2", "--log-driver", "none",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=268435456",
        "--mount", f"type=bind,src={configuration},dst=/etc/litellm/config.json,readonly",
        "--env", "HOME=/tmp", "--env", "LITELLM_TELEMETRY_DISABLED=true",
        "--env", "DEFAULT_MAX_RETRIES=0",
        IMAGE, "--config", "/etc/litellm/config.json", "--host", "0.0.0.0",
        "--port", "4000", "--num_workers", "1", "--request_timeout", "30",
    ]


if __name__ == "__main__":
    arguments = command()
    os.execv(arguments[0], arguments)
