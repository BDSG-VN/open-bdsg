"""Lịch tác vụ nội bộ có claim bền vững; bỏ lượt lỡ, không chạy bù hàng loạt."""

import json
import secrets
import threading
import time
from hanh_dong import active_actor


class LichCongViec:
    def __init__(self, kho, core, tasks):
        self.kho, self.core, self.tasks = kho, core, tasks
        self.stop = threading.Event()
        self.thread = None
        with kho.ket_noi() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY,owner TEXT,name TEXT,args TEXT,interval INTEGER,enabled INTEGER,next_run REAL,last_status TEXT,last_task TEXT,created REAL)"
            )

    def list(self, actor):
        self.tasks._auth(actor, True)
        with self.kho.ket_noi() as db:
            rows = db.execute(
                "SELECT * FROM schedules"
                + ("" if actor["role"] == "quan-tri" else " WHERE owner=?")
                + " ORDER BY created DESC LIMIT 50",
                () if actor["role"] == "quan-tri" else (actor["id"],),
            ).fetchall()
        return {
            "schedules": [
                {
                    **dict(r),
                    "args": json.loads(r["args"]),
                    "enabled": bool(r["enabled"]),
                }
                for r in rows
            ]
        }

    def create(self, actor, data):
        self.tasks._auth(actor, True)
        name, interval, args = (
            data.get("name"),
            data.get("interval_seconds"),
            data.get("task"),
        )
        if (
            not isinstance(name, str)
            or not 3 <= len(name) <= 100
            or type(interval) is not int
            or not 900 <= interval <= 604800
            or not isinstance(args, dict)
        ):
            raise ValueError("Tên, chu kỳ (15 phút–7 ngày) hoặc tác vụ không hợp lệ")
        if (
            args.get("allow_module_reads")
            or args.get("allow_python")
            or set(args)
            - {"prompt", "template", "module_ids", "project_id", "document_ids"}
        ):
            raise ValueError(
                "Lịch đợt đầu chỉ đọc danh mục/ngữ cảnh, không đọc MCP ngoài hoặc chạy mã"
            )
        if (
            not isinstance(args.get("prompt"), str)
            or not 10 <= len(args["prompt"].strip()) <= 4000
        ):
            raise ValueError("Mô tả cần 10–4000 ký tự")
        # Resolve permission now and again on every occurrence.
        if args.get("project_id"):
            self.tasks.projects.context_for(actor, args["project_id"])
        if args.get("document_ids"):
            self.tasks.documents.snapshot(
                actor, args["document_ids"], args.get("project_id")
            )
        encoded = json.dumps(args, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode()) > 16000:
            raise ValueError("Cấu hình lịch quá lớn")
        identifier, now = secrets.token_hex(12), time.time()
        with self.kho.ket_noi() as db:
            if (
                db.execute(
                    "SELECT count(*) FROM schedules WHERE owner=?", (actor["id"],)
                ).fetchone()[0]
                >= 20
            ):
                raise ValueError("Tối đa 20 lịch cho mỗi danh tính")
            db.execute(
                "INSERT INTO schedules VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    actor["id"],
                    name,
                    encoded,
                    interval,
                    1,
                    now + interval,
                    "scheduled",
                    "",
                    now,
                ),
            )
        self.kho.su_kien(actor["id"], "tao-lich", identifier)
        return {"id": identifier, "next_run": now + interval}

    def toggle(self, actor, data):
        with self.core.lock:
            return self._toggle(actor, data)

    def _toggle(self, actor, data):
        self.tasks._auth(actor, True)
        if type(data.get("enabled")) is not bool:
            raise ValueError("Trạng thái bật/tắt không hợp lệ")
        with self.kho.ket_noi() as db:
            r = db.execute(
                "SELECT * FROM schedules WHERE id=?", (data.get("id"),)
            ).fetchone()
            if not r or (r["owner"] != actor["id"] and actor["role"] != "quan-tri"):
                raise ValueError("Lịch ngoài phạm vi quyền")
            db.execute(
                "UPDATE schedules SET enabled=?,next_run=? WHERE id=?",
                (int(data["enabled"]), time.time() + r["interval"], r["id"]),
            )
        self.kho.su_kien(actor["id"], "doi-lich", r["id"])
        return {"id": r["id"], "enabled": data["enabled"]}

    def tick(self, now=None):
        now = time.time() if now is None else now
        with self.kho.ket_noi() as db:
            rows = db.execute(
                "SELECT * FROM schedules WHERE enabled=1 AND next_run<=? ORDER BY next_run LIMIT 10",
                (now,),
            ).fetchall()
        for r in rows:
            with self.kho.ket_noi() as db:
                if not db.execute(
                    "UPDATE schedules SET next_run=?,last_status='claimed' WHERE id=? AND enabled=1 AND next_run=?",
                    (now + r["interval"], r["id"], r["next_run"]),
                ).rowcount:
                    continue
            status, task_id = "failed", ""
            try:
                actor = active_actor(self.kho, r["owner"])
                # Hold the core lock to keep a pause from racing the dispatch boundary.
                with self.core.lock:
                    with self.kho.ket_noi() as db:
                        enabled = db.execute(
                            "SELECT enabled FROM schedules WHERE id=?", (r["id"],)
                        ).fetchone()[0]
                    if not enabled:
                        continue
                    result = self.core.goi(
                        actor, "cong_viec.tao", json.loads(r["args"])
                    )
                if result.get("ok"):
                    status, task_id = "queued", result["ket_qua"]["id"]
            except Exception:
                pass
            with self.kho.ket_noi() as db:
                db.execute(
                    "UPDATE schedules SET last_status=?,last_task=? WHERE id=?",
                    (status, task_id, r["id"]),
                )
            self.kho.su_kien(r["owner"], "luot-lich-" + status, r["id"])

    def start(self):
        def loop():
            while not self.stop.wait(15):
                try:
                    self.tick()
                except Exception:
                    pass

        if not self.thread:
            self.thread = threading.Thread(
                target=loop, daemon=True, name="bdsg-schedules"
            )
            self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=20)
