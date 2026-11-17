"""Diễn tập cổng HTTP từ snapshot mới trong mạng cô lập, không khởi chạy lịch.

Chỉ metadata đã lọc đi ra stdout. Không đọc gateway.env hoặc đưa bí mật của
máy thật vào subprocess. Đo cổng HTTP không phải RTO toàn host hay dịch vụ ngoài.
"""

import argparse
import hashlib
import http.client
import json
import math
import os
import queue
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "he-dieu-hanh"))
from kiem_tra_khoi_phuc import drill as data_drill
from sao_luu_he_thong import verify


IDENTITY_TABLES = ("chu", "agents", "web_users", "phien", "phien_web", "google_login_identities", "du_an_members",
                   "don_vi", "don_vi_members", "don_vi_migrations", "du_an_units", "du_an_unit_grants", "cong_viec_units",
                   "office_request_units", "office_upload_units", "ai_task_credit_units", "ai_reservation_units",
                   "ai_unit_configs", "ai_unit_proxy", "unit_connectors", "unit_actions", "unit_action_cancelled_runs",
                   "unit_mcp_grants")
COUNTS = {"files": "office_files", "versions": "office_versions", "projects": "du_an", "tasks": "cong_viec_tasks"}
FORBIDDEN = tuple(Path(p) for p in ("/var/lib/bdsg-thanhhoa", "/etc/bdsg-thanhhoa", "/srv/bdsg-thanhhoa/open-bdsg"))


def _plain(value):
    path = Path(os.path.abspath(value))
    for component in (path, *path.parents):
        if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
            raise ValueError("Không nhận liên kết")
    return path


def _paths(bundle, destination, source_root):
    bundle, destination, source_root = map(_plain, (bundle, destination, source_root))
    if os.path.lexists(destination) or not destination.parent.is_dir():
        raise ValueError("Cần đích mới trong thư mục đã chuẩn bị")
    if any(destination == root or root in destination.parents for root in FORBIDDEN):
        raise ValueError("Không diễn tập tại vùng dữ liệu hoặc mã đang phục vụ")
    if any(destination == root or root in destination.parents or destination in root.parents
           for root in (bundle, source_root)):
        raise ValueError("Đích phải tách khỏi nguồn")
    for relative in ("he-dieu-hanh/may_chu.py", "nen-tang/danh-muc.json"):
        path = _plain(source_root / relative)
        if not path.is_file():
            raise ValueError("Nguồn ứng dụng không phù hợp")
    return bundle, destination, source_root


def isolated_network():
    """Chỉ chấp nhận tiến trình không đặc quyền, không giao diện ngoài loopback.

    systemd phải dựng PrivateNetwork trước khi gọi. Không tự thay firewall,
    namespace hoặc quyền host; trạng thái không đọc được được coi là chưa đạt.
    """
    if sys.platform != "linux" or os.geteuid() == 0:
        return False
    try:
        status = Path("/proc/self/status").read_text(encoding="ascii")
        caps = re.search(r"^CapEff:\s*([0-9a-fA-F]+)\s*$", status, re.M)
        nnp = re.search(r"^NoNewPrivs:\s*1\s*$", status, re.M)
        interfaces = {line.split(":", 1)[0].strip()
                      for line in Path("/proc/net/dev").read_text(encoding="ascii").splitlines()
                      if ":" in line}
        return bool(caps and int(caps.group(1), 16) == 0 and nnp and interfaces == {"lo"})
    except (OSError, ValueError):
        return False


def _state(database):
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("CSDL không toàn vẹn")
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {key: db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                  if table in tables else None for key, table in COUNTS.items()}
        identity = {}
        for table in IDENTITY_TABLES:
            identity[table] = _table_digest(db, table, tables)
        business = {table: _table_digest(db, table, tables) for table in ("office_files", "office_versions", "du_an")}
        tasks = sorted(db.execute("SELECT id,owner FROM cong_viec_tasks").fetchall()) if "cong_viec_tasks" in tables else []
        return {"counts": counts, "identity": identity, "tasks": tasks, "business": business}


def _table_digest(db, table, tables):
    value = hashlib.sha256()
    if table in tables:
        for row in db.execute(f'SELECT * FROM "{table}" ORDER BY rowid'):
            value.update(b"row:")
            for field in row:
                encoded = field if isinstance(field, bytes) else json.dumps(field, ensure_ascii=True).encode()
                value.update(b"blob:" if isinstance(field, bytes) else b"json:")
                value.update(str(len(encoded)).encode() + b":" + encoded)
    return value.digest()


def _synthetic(manifest, bundle):
    # Chế độ test không có cấu hình/bí mật và không được tự chạy tác vụ theo lịch.
    if set(manifest["files"]) != {"data/van-hanh.db"}:
        raise ValueError("Chế độ tổng hợp chỉ nhận CSDL không cấu hình")
    with closing(sqlite3.connect((bundle / "data/van-hanh.db").resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "schedules" in tables and db.execute("SELECT count(*) FROM schedules").fetchone()[0]:
            raise ValueError("Không chạy lịch trong fixture")


def _environment():
    # Danh sách mới hoàn toàn; không kế thừa BDSG_*, proxy, token hay PYTHONPATH.
    env = {"PATH": os.defpath, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if os.name == "nt" and "SystemRoot" in os.environ:
        env["SystemRoot"] = os.environ["SystemRoot"]
    return env


def _port(process, timeout):
    result = queue.Queue(maxsize=1)
    def read():
        try:
            result.put(process.stdout.readline(80))
        except OSError:
            result.put(b"")
    threading.Thread(target=read, daemon=True).start()
    try:
        value = result.get(timeout=timeout)
    except queue.Empty:
        raise TimeoutError("Cổng chưa sẵn sàng") from None
    match = re.fullmatch(rb"BDSG_DRILL_PORT=([0-9]{1,5})\r?\n", value)
    if not match or not 1 <= int(match.group(1)) <= 65535:
        raise ValueError("Worker không có thông báo sẵn sàng hợp lệ")
    return int(match.group(1))


def _request(port, path, timeout):
    with closing(http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)) as client:
        client.request("GET", path)
        response = client.getresponse()
        payload = response.read(1024 * 1024 + 1)
        if len(payload) > 1024 * 1024:
            raise ValueError("Phản hồi vượt giới hạn")
        return response.status, json.loads(payload)


def _stop(process):
    clean = process.poll() is not None and process.returncode == 0
    if process.poll() is None:
        try:
            process.stdin.write(b"STOP\n")
            process.stdin.flush()
            process.stdin.close()
            process.wait(timeout=10)
            clean = process.returncode == 0
        except (OSError, ValueError, subprocess.TimeoutExpired):
            process.kill()
            process.wait(timeout=10)
    if process.stdout is not None:
        process.stdout.close()
    if process.stdin is not None and not process.stdin.closed:
        process.stdin.close()
    return clean


def _blank(mode):
    return {"format": 1, "status": "failed", "observed_at": time.time(),
            "scope": "restored-http-gateway-only", "mode": mode if mode in ("isolated", "synthetic") else "invalid",
            "isolation_verified": False, "data_restore_seconds": None,
            "gateway_ready_seconds": None, "total_seconds": None,
            "checks": {"data_restore": False, "ready": False, "public_catalogue": False,
                       "unauthenticated_private_denied": False, "identity_preserved": False,
                       "task_ownership_preserved": False, "counts_preserved": False,
                       "saved_files_projects_preserved": False,
                       "integrity": False, "worker_stopped_cleanly": False},
            "counts": {key: None for key in COUNTS},
            "schedules_started": False, "external_services_tested": False,
            "whole_host_recovery_tested": False}


def run_drill(bundle, destination, source_root=ROOT, mode="isolated", timeout=30):
    """Khôi phục mới, thử cổng loopback, dừng đúng worker; giữ đích cho kiểm riêng."""
    started = time.perf_counter()
    report, process = _blank(mode), None
    try:
        if mode not in ("isolated", "synthetic") or not math.isfinite(timeout) or not 1 <= timeout <= 300:
            raise ValueError("Chế độ hoặc thời hạn không hợp lệ")
        bundle, destination, source_root = _paths(bundle, destination, source_root)
        manifest = verify(bundle)
        if mode == "isolated":
            if not isolated_network():
                raise ValueError("Chưa chứng minh mạng cô lập")
            report["isolation_verified"] = True
        else:
            _synthetic(manifest, bundle)
        before = _state(bundle / "data/van-hanh.db")
        data, code = data_drill(bundle, destination)
        if code:
            raise ValueError("Khôi phục dữ liệu chưa đạt")
        report["checks"]["data_restore"] = True
        report["data_restore_seconds"] = data["restore_duration_seconds"]
        gateway_started = time.perf_counter()
        deadline = time.monotonic() + timeout
        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise TimeoutError("Cổng vượt thời hạn kiểm")
            return value
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()),
            "--worker", "--destination", str(destination), "--source-root", str(source_root), "--mode", mode],
            env=_environment(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, cwd=destination, **options)
        port = _port(process, remaining())
        status, ready = _request(port, "/api/ready", remaining())
        report["checks"]["ready"] = status == 200 and ready == {"status": "ready"}
        report["gateway_ready_seconds"] = round(time.perf_counter() - gateway_started, 6)
        status, catalogue = _request(port, "/api/catalogue", remaining())
        report["checks"]["public_catalogue"] = status == 200 and isinstance(catalogue.get("products"), list) and bool(catalogue["products"])
        report["checks"]["unauthenticated_private_denied"] = all(
            _request(port, path, remaining())[0] == 401 for path in ("/api/node", "/api/system", "/api/requests"))
        report["checks"]["worker_stopped_cleanly"] = _stop(process)
        process = None
        after = _state(destination / "data/van-hanh.db")
        report["checks"].update(identity_preserved=before["identity"] == after["identity"],
            task_ownership_preserved=before["tasks"] == after["tasks"],
            saved_files_projects_preserved=before["business"] == after["business"],
            counts_preserved=before["counts"] == after["counts"], integrity=True)
        report["counts"] = after["counts"]
        if all(report["checks"].values()):
            report["status"] = "ok"
    except (OSError, ValueError, sqlite3.Error, TimeoutError, KeyError, TypeError,
            AttributeError, RecursionError, OverflowError, subprocess.SubprocessError):
        pass
    finally:
        if process is not None:
            report["checks"]["worker_stopped_cleanly"] = _stop(process)
        report["observed_at"] = time.time()
        report["total_seconds"] = round(time.perf_counter() - started, 6)
    return report, 0 if report["status"] == "ok" else 1


def _worker(destination, source_root, mode):
    if mode == "isolated" and not isolated_network():
        return 1
    destination = _plain(destination)
    if any(destination == root or root in destination.parents for root in FORBIDDEN):
        return 1
    data = _plain(destination / "data")
    database = _plain(data / "van-hanh.db")
    if not database.is_file():
        return 1
    if mode == "synthetic":
        if {p.relative_to(destination).as_posix() for p in destination.rglob("*")} != {"data", "data/van-hanh.db"}:
            return 1
        _synthetic({"files": {"data/van-hanh.db": {}}}, destination)
    source = _plain(source_root)
    sys.path.insert(0, str(source / "he-dieu-hanh"))
    from may_chu import UngDung, tao_may_chu
    app = UngDung(data, "https://recovery.invalid", False)
    server = tao_may_chu(app, 0)
    def stop(*_):
        app.operations.draining.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def command():
        if sys.stdin.buffer.readline(16) == b"STOP\n":
            stop()
    threading.Thread(target=command, daemon=True).start()
    print("BDSG_DRILL_PORT=" + str(server.server_port), flush=True)
    try:
        server.serve_forever()
    finally:
        app.operations.draining.set()
        server.server_close()
        app.schedules.close()
        app.tasks.close()
        app.core.audit.close()
    return 0


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--mode", choices=("isolated", "synthetic"), default="isolated")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        try:
            return _worker(args.destination, args.source_root, args.mode)
        except (OSError, ValueError, sqlite3.Error, KeyError, TypeError, ImportError):
            return 1
    if not args.bundle:
        parser.error("Cần --bundle")
    report, code = run_drill(args.bundle, args.destination, args.source_root, args.mode, args.timeout)
    print(json.dumps(report, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
