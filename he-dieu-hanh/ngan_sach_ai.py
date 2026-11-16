"""Hạn mức tài trợ AI tính nguyên tử theo ngày Việt Nam, độc lập LiteLLM.

Giữ trước chi phí bảo thủ thay vì hứa quota miễn phí từ nhà cung cấp. Lượt
đã gửi có thể bị tính phí dù lỗi, nên không tự hoàn hạn mức khi thiếu usage.
"""

import time
from decimal import ROUND_CEILING, Decimal, InvalidOperation

from mo_hinh_bdsg import LoiMoHinhBDSG

DEFAULT_POLICY = {
    "tasks_per_user": 5,
    "calls_per_user": 64,
    "calls_global": 500,
    "input_tokens_per_user": 500000,
    "output_tokens_per_user": 100000,
    "output_tokens_per_project": 131072,
    "output_tokens_global": 524288,
    "usd_per_user": "0.50",
    "usd_global": "5.00",
}


def money(value, maximum=10000):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or not 0 <= number <= maximum:
            raise ValueError()
        return number
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(
            "Chi phí phải là số hữu hạn, không âm và trong giới hạn"
        ) from None


def validate_policy(data):
    if not isinstance(data, dict) or set(data) != set(DEFAULT_POLICY):
        raise ValueError("Cấu hình hạn mức AI chưa đủ hoặc có trường lạ")
    result = {}
    for key in DEFAULT_POLICY:
        if key.startswith("usd_"):
            result[key] = str(money(data[key]))
        else:
            value = data[key]
            if type(value) is not int or not 1 <= value <= 10000000:
                raise ValueError("Hạn mức lượt/token phải là số nguyên dương")
            result[key] = value
    return result


class NganSachAI:
    def __init__(self, kho, clock=time.time):
        self.kho, self.clock = kho, clock
        with kho.ket_noi() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS ai_task_credits(
                    owner TEXT, task_id TEXT, run INTEGER, day INTEGER,
                    PRIMARY KEY(task_id,run)
                );
                CREATE INDEX IF NOT EXISTS ai_task_day ON ai_task_credits(day,owner);
                CREATE TABLE IF NOT EXISTS ai_reservations(
                    id INTEGER PRIMARY KEY, owner TEXT, day INTEGER, task_id TEXT,
                    model_id TEXT, input_tokens INTEGER, output_tokens INTEGER,
                    micro_usd INTEGER, created REAL
                );
                CREATE INDEX IF NOT EXISTS ai_reservation_day ON ai_reservations(day,owner);
            """)
            if "project_id" not in {
                row[1] for row in db.execute("PRAGMA table_info(ai_reservations)")
            }:
                db.execute(
                    "ALTER TABLE ai_reservations ADD COLUMN project_id TEXT NOT NULL DEFAULT ''"
                )
            db.execute(
                "CREATE INDEX IF NOT EXISTS ai_reservation_project ON ai_reservations(day,project_id)"
            )

    def day(self):
        return int((self.clock() + 25200) // 86400)

    @staticmethod
    def _owner(actor):
        if (
            not isinstance(actor, dict)
            or not isinstance(actor.get("id"), str)
            or not actor["id"]
            or actor.get("role") not in ("operator", "quan-tri")
        ):
            raise PermissionError("Cần tài khoản được cấp quyền sử dụng AI")
        return actor["id"]

    def claim_task(self, db, actor, task_id, run, policy):
        """Gọi bên trong transaction BEGIN IMMEDIATE của thao tác tạo/tiếp tục."""
        owner, day = self._owner(actor), self.day()
        if db.execute(
            "SELECT 1 FROM ai_task_credits WHERE task_id=? AND run=?", (task_id, run)
        ).fetchone():
            return
        used = db.execute(
            "SELECT count(*) FROM ai_task_credits WHERE owner=? AND day=?", (owner, day)
        ).fetchone()[0]
        if used >= policy["tasks_per_user"]:
            raise LoiMoHinhBDSG(
                "Đã dùng hết tác vụ AI được BDSG tài trợ hôm nay; hạn mức đặt lại lúc 00:00 giờ Việt Nam."
            )
        db.execute(
            "INSERT INTO ai_task_credits VALUES (?,?,?,?)", (owner, task_id, run, day)
        )

    @staticmethod
    def _legacy(db, owner, day, project_id=""):
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='model_calls'"
        ).fetchone():
            return (0, 0, 0, 0, 0)
        return db.execute(
            "SELECT coalesce(sum(owner=?),0),coalesce(sum(CASE WHEN owner=? THEN output_reserved ELSE 0 END),0),count(*),coalesce(sum(output_reserved),0),coalesce(sum(CASE WHEN project_id=? THEN output_reserved ELSE 0 END),0) FROM model_calls WHERE created>=?",
            (owner, owner, project_id, day * 86400 - 25200),
        ).fetchone()

    def reserve(
        self,
        actor,
        task_id,
        model_id,
        input_tokens,
        output_tokens,
        prices,
        policy,
        project_id="",
    ):
        owner, day = self._owner(actor), self.day()
        if any(
            type(value) is not int or not 0 <= value <= 2000000
            for value in (input_tokens, output_tokens)
        ):
            raise ValueError("Số token giữ trước không hợp lệ")
        cost = int(
            (
                money(prices["input_per_million"]) * input_tokens
                + money(prices["output_per_million"]) * output_tokens
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            legacy = self._legacy(db, owner, day, project_id)
            own = db.execute(
                "SELECT count(*),coalesce(sum(input_tokens),0),coalesce(sum(output_tokens),0),coalesce(sum(micro_usd),0) FROM ai_reservations WHERE day=? AND owner=?",
                (day, owner),
            ).fetchone()
            total = db.execute(
                "SELECT count(*),coalesce(sum(micro_usd),0),coalesce(sum(output_tokens),0) FROM ai_reservations WHERE day=?",
                (day,),
            ).fetchone()
            project = (
                db.execute(
                    "SELECT coalesce(sum(output_tokens),0) FROM ai_reservations WHERE day=? AND project_id=?",
                    (day, project_id),
                ).fetchone()[0]
                if project_id
                else 0
            )
            if (
                own[0] + legacy[0] >= policy["calls_per_user"]
                or total[0] + legacy[2] >= policy["calls_global"]
                or own[1] + input_tokens > policy["input_tokens_per_user"]
                or own[2] + legacy[1] + output_tokens > policy["output_tokens_per_user"]
                or total[2] + legacy[3] + output_tokens > policy["output_tokens_global"]
                or (
                    project_id
                    and project + legacy[4] + output_tokens
                    > policy["output_tokens_per_project"]
                )
                or own[3] + cost > money(policy["usd_per_user"]) * 1000000
                or total[1] + cost > money(policy["usd_global"]) * 1000000
            ):
                raise LoiMoHinhBDSG(
                    "Đã chạm trần lượt, token hoặc chi phí AI được tài trợ trong ngày; chưa gửi yêu cầu tới nhà cung cấp."
                )
            cursor = db.execute(
                "INSERT INTO ai_reservations(owner,day,task_id,model_id,input_tokens,output_tokens,micro_usd,created,project_id) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    owner,
                    day,
                    task_id,
                    model_id,
                    input_tokens,
                    output_tokens,
                    cost,
                    self.clock(),
                    project_id,
                ),
            )
            return cursor.lastrowid

    def status(self, actor, policy):
        owner, day = self._owner(actor), self.day()
        with self.kho.ket_noi() as db:
            legacy = self._legacy(db, owner, day)
            tasks = db.execute(
                "SELECT count(*) FROM ai_task_credits WHERE owner=? AND day=?",
                (owner, day),
            ).fetchone()[0]
            row = db.execute(
                "SELECT count(*),coalesce(sum(input_tokens),0),coalesce(sum(output_tokens),0),coalesce(sum(micro_usd),0) FROM ai_reservations WHERE owner=? AND day=?",
                (owner, day),
            ).fetchone()
        return {
            "timezone": "Asia/Ho_Chi_Minh",
            "resets_at_unix": (day + 1) * 86400 - 25200,
            "tasks_used": tasks,
            "tasks_remaining": max(0, policy["tasks_per_user"] - tasks),
            "calls_used": row[0] + legacy[0],
            "input_tokens_reserved": row[1],
            "output_tokens_reserved": row[2] + legacy[1],
            "usd_reserved": str(Decimal(row[3]) / 1000000),
            "policy": dict(policy),
            "accounting": "Giữ trước bảo thủ theo giá chủ quản khai báo; chưa phải hóa đơn nhà cung cấp.",
        }
