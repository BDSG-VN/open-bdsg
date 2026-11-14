"""Dự thảo → duyệt payload bất biến → thực thi một lần, không retry ghi mù."""

import hashlib
import json
import secrets
import time


def active_actor(kho, identifier):
    with kho.ket_noi() as db:
        if (
            identifier == "chu-quan"
            and db.execute("SELECT 1 FROM chu WHERE ma=?", (identifier,)).fetchone()
        ):
            return {"id": identifier, "name": "Chủ quản", "role": "quan-tri"}
        r = db.execute(
            "SELECT ma,ten,role FROM agents WHERE ma=? AND active=1", (identifier,)
        ).fetchone()
    if not r:
        raise PermissionError("Danh tính đã bị thu hồi")
    return {"id": r["ma"], "name": r["ten"], "role": r["role"]}


class HanhDong:
    def __init__(self, kho, core, tasks, browser=None):
        self.kho, self.core, self.tasks = kho, core, tasks
        self.browser = browser
        with kho.ket_noi() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY,owner TEXT,task_id TEXT,payload TEXT,digest TEXT,status TEXT,created REAL,expires REAL,result TEXT)"
            )
            db.execute("UPDATE actions SET status='unknown' WHERE status='executing'")

    def _check(self, actor, payload, task):
        if actor["role"] not in ("operator", "quan-tri"):
            raise PermissionError("Không có quyền đề xuất hành động")
        name, args = payload.get("tool"), payload.get("arguments")
        if not isinstance(args, dict):
            raise ValueError("Tham số phải là đối tượng JSON")
        if name not in (
            "kinh_doanh.tao_yeu_cau",
            "kinh_doanh.doi_chang",
            "ket_noi.ghi",
            "trinh_duyet.hanh_dong",
        ):
            raise ValueError("Công cụ ghi chưa hỗ trợ phê duyệt")
        if name == "trinh_duyet.hanh_dong":
            if (
                not self.browser
                or args.get("task_id") != task["id"]
                or not task.get("allow_action_drafts")
            ):
                raise PermissionError("Tác vụ chưa cấp quyền dự thảo trình duyệt")
            if payload.get("run", task["run"]) != task["run"]:
                raise ValueError("Đề xuất thuộc lượt công việc cũ")
            target = self.browser.inspect(actor, args)["target"]
            if "browser_target" in payload and payload["browser_target"] != target:
                raise ValueError("Biểu mẫu đã thay đổi; tạo đề xuất mới")
            payload["browser_target"] = target
            payload["run"] = task["run"]
        if name == "ket_noi.ghi":
            if (
                actor["role"] != "quan-tri"
                or args.get("platform_id") not in task["module_ids"]
            ):
                raise PermissionError("Ngoài mô-đun được giao")
            allowed = any(
                c.get("platform_id") == args.get("platform_id")
                and c.get("state") == "da-xac-minh"
                and c.get("enabled", True)
                and args.get("tool") in c.get("write_tools", [])
                and actor["role"] in c.get("roles", ["quan-tri"])
                for c in self.core.connections.config
            )
            if not allowed:
                raise PermissionError("Công cụ ghi chưa được xác minh và cấp quyền")

    def propose(self, actor, args):
        task = self.tasks.detail(actor, args.get("task_id", ""))
        if task["owner"] != actor["id"]:
            raise PermissionError("Chỉ người giao việc được đề xuất cho tác vụ")
        payload = {"tool": args.get("tool"), "arguments": args.get("arguments")}
        self._check(actor, payload, task)
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, allow_nan=False
        )
        if len(encoded.encode()) > 16000:
            raise ValueError("Dự thảo quá lớn")
        identifier = secrets.token_hex(12)
        now = time.time()
        with self.kho.ket_noi() as db:
            db.execute(
                "UPDATE actions SET status='expired' WHERE owner=? AND status='awaiting' AND expires<=?",
                (actor["id"], now),
            )
            if (
                db.execute(
                    "SELECT count(*) FROM actions WHERE owner=? AND status='awaiting'",
                    (actor["id"],),
                ).fetchone()[0]
                >= 20
            ):
                raise ValueError("Đã có 20 hành động chờ duyệt")
            db.execute(
                "INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    actor["id"],
                    task["id"],
                    encoded,
                    hashlib.sha256(encoded.encode()).hexdigest(),
                    "awaiting",
                    now,
                    now + 900,
                    "{}",
                ),
            )
        self.kho.su_kien(actor["id"], "de-xuat-hanh-dong", identifier)
        return self.get(actor, identifier)

    def get(self, actor, identifier):
        self.tasks._auth(actor)
        with self.kho.ket_noi() as db:
            r = db.execute("SELECT * FROM actions WHERE id=?", (identifier,)).fetchone()
        if not r or (r["owner"] != actor["id"] and actor["role"] != "quan-tri"):
            raise ValueError("Không tìm thấy hành động trong phạm vi quyền")
        return {
            **dict(r),
            "payload": json.loads(r["payload"]),
            "result": json.loads(r["result"]),
        }

    def list(self, actor):
        self.tasks._auth(actor)
        with self.kho.ket_noi() as db:
            rows = db.execute(
                "SELECT id FROM actions"
                + ("" if actor["role"] == "quan-tri" else " WHERE owner=?")
                + " ORDER BY created DESC LIMIT 100",
                () if actor["role"] == "quan-tri" else (actor["id"],),
            ).fetchall()
        return {"actions": [self.get(actor, r[0]) for r in rows]}

    def decide(self, actor, args):
        action = self.get(actor, args.get("id"))
        if actor["role"] != "quan-tri":
            raise PermissionError("Chủ quản duyệt hành động")
        if (
            args.get("digest") != action["digest"]
            or type(args.get("approve")) is not bool
        ):
            raise ValueError("Nội dung duyệt không khớp")
        if args["approve"]:
            original = active_actor(self.kho, action["owner"])
            task = self.tasks.detail(original, action["task_id"])
            self._check(original, action["payload"], task)
        status = "executing" if args["approve"] else "rejected"
        with self.kho.ket_noi() as db:
            changed = db.execute(
                "UPDATE actions SET status=? WHERE id=? AND digest=? AND status='awaiting' AND (?=0 OR expires>?)",
                (
                    status,
                    action["id"],
                    action["digest"],
                    int(args["approve"]),
                    time.time(),
                ),
            ).rowcount
            if not changed:
                raise ValueError("Hành động hết hạn hoặc đã được xử lý")
        if args["approve"]:
            try:
                self._check(
                    original,
                    action["payload"],
                    self.tasks.detail(original, action["task_id"]),
                )
                if action["payload"]["tool"] == "trinh_duyet.hanh_dong":
                    with self.browser.authorization(
                        original,
                        action["payload"]["arguments"],
                        action["payload"]["browser_target"]["signature"],
                    ):
                        response = self.core.goi(
                            original,
                            action["payload"]["tool"],
                            action["payload"]["arguments"],
                        )
                else:
                    response = self.core.goi(
                        original,
                        action["payload"]["tool"],
                        action["payload"]["arguments"],
                    )
                status = "completed" if response.get("ok") else "unknown"
                encoded = json.dumps(response, ensure_ascii=False)
                if len(encoded.encode()) > 100000:
                    encoded = json.dumps(
                        {
                            "ok": response.get("ok"),
                            "message": "Kết quả lớn; cần kiểm tra trên nền tảng gốc",
                        }
                    )
            except Exception:
                status, encoded = (
                    "unknown",
                    '{"message":"Cần đối chiếu nền tảng trước khi tạo đề xuất mới; không tự gọi lại"}',
                )
            with self.kho.ket_noi() as db:
                db.execute(
                    "UPDATE actions SET status=?,result=? WHERE id=?",
                    (status, encoded, action["id"]),
                )
        self.kho.su_kien(actor["id"], "xu-ly-hanh-dong", action["id"])
        return self.get(actor, action["id"])

    def preview(self, actor, identifier):
        action = self.get(actor, identifier)
        if (
            action["payload"]["tool"] != "trinh_duyet.hanh_dong"
            or action["status"] != "awaiting"
            or action["expires"] <= time.time()
        ):
            raise ValueError("Đề xuất không còn chờ duyệt")
        original = active_actor(self.kho, action["owner"])
        task = self.tasks.detail(original, action["task_id"])
        if task["run"] != action["payload"].get("run"):
            raise ValueError("Đề xuất thuộc lượt cũ")
        result = self.browser.inspect(
            original, action["payload"]["arguments"], image=True
        )
        return {
            **result,
            "matches": result["target"] == action["payload"]["browser_target"],
        }
