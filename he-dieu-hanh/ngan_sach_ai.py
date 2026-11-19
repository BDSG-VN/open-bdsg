"""Hạn mức tài trợ AI tính nguyên tử theo ngày Việt Nam, độc lập LiteLLM.

Giữ trước chi phí bảo thủ thay vì hứa quota miễn phí từ nhà cung cấp. Lượt
đã gửi có thể bị tính phí dù lỗi, nên không tự hoàn hạn mức khi thiếu usage.
"""

import time
from types import MappingProxyType
from decimal import ROUND_CEILING, Decimal, InvalidOperation

from mo_hinh_bdsg import LoiMoHinhBDSG
from don_vi import assert_unscoped_store
from quyen_tac_vu import authorize_claim, authorize_run

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
    def __init__(self, kho, clock=time.time, *, units=None, projects=None, host_policy=None):
        self.kho, self.clock = kho, clock
        self.units, self.projects = units, projects
        self.run_authorizer = None
        # Chính sách máy chủ chỉ đến từ cấu hình tin cậy, không từ cấu hình đơn vị.
        self.host_policy = MappingProxyType(validate_policy(
            dict(DEFAULT_POLICY if host_policy is None else host_policy)))
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
                CREATE TABLE IF NOT EXISTS ai_task_credit_units(
                    task_id TEXT NOT NULL, run INTEGER NOT NULL, unit_id TEXT NOT NULL,
                    PRIMARY KEY(task_id,run));
                CREATE TABLE IF NOT EXISTS ai_reservation_units(
                    reservation_id INTEGER PRIMARY KEY, unit_id TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS ai_reservation_unit ON ai_reservation_units(unit_id,reservation_id);
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

    def claim_task(self, db, actor, task_id, run, policy, project_id=""):
        """Gọi bên trong transaction BEGIN IMMEDIATE của thao tác tạo/tiếp tục."""
        owner, day = self._owner(actor), self.day()
        scope = self.units.require(actor, db) if self.units is not None else None
        if scope is None:
            assert_unscoped_store(db)
        elif not db.in_transaction:
            raise RuntimeError("Cấp hạn mức cần giao dịch ghi của tác vụ")
        if scope:
            scope, project_id = authorize_claim(
                db,actor,task_id,self.units,self.projects,project_id)
        existing = db.execute("""SELECT c.owner,s.unit_id FROM ai_task_credits c
            LEFT JOIN ai_task_credit_units s ON s.task_id=c.task_id AND s.run=c.run
            WHERE c.task_id=? AND c.run=?""", (task_id,run)).fetchone()
        if existing:
            if existing[0] != owner or existing[1] != (scope.unit_id if scope else None):
                raise PermissionError("Hạn mức tác vụ không thuộc phạm vi này")
            return
        used = db.execute(
            """SELECT count(*) FROM ai_task_credits c
            JOIN ai_task_credit_units s ON s.task_id=c.task_id AND s.run=c.run
            WHERE c.owner=? AND c.day=? AND s.unit_id=?""" if scope else
            "SELECT count(*) FROM ai_task_credits WHERE owner=? AND day=?",
            (owner,day,scope.unit_id) if scope else (owner,day)
        ).fetchone()[0]
        if used >= policy["tasks_per_user"]:
            raise LoiMoHinhBDSG(
                "Đã dùng hết tác vụ AI được BDSG tài trợ hôm nay; hạn mức đặt lại lúc 00:00 giờ Việt Nam."
            )
        db.execute(
            "INSERT INTO ai_task_credits VALUES (?,?,?,?)", (owner, task_id, run, day)
        )
        if scope:
            db.execute("INSERT INTO ai_task_credit_units VALUES(?,?,?)",(task_id,run,scope.unit_id))

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
        run=None,
        guard=None,
    ):
        """Giữ chi phí trước lời gọi; luồng đơn vị phải truyền đúng lượt chạy.

        Ràng buộc epoch/revision của lượt đã lưu ngăn scope vừa cấp lại dùng
        quyền mới để gửi lời gọi còn sót từ lượt cũ. Callback guard(db) của
        máy chủ chỉ chạy sau kiểm quyền trong cùng khóa ghi, trước giữ chi phí.
        """
        owner = self._owner(actor)
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
            # Chờ writer có thể đi qua nửa đêm; ngày hạn mức phải lấy sau khóa.
            day = self.day()
            if self.units is not None:
                return self._reserve_scoped(db,actor,task_id,model_id,input_tokens,
                    output_tokens,cost,policy,project_id,run,day,guard)
            assert_unscoped_store(db)
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

    def _reserve_scoped(self,db,actor,task_id,model_id,input_tokens,output_tokens,
                        cost,policy,project_id,run,day,guard):
        scope, project_id = authorize_run(
            db,actor,task_id,run,self.units,self.projects,project_id,authorizer=self.run_authorizer)
        credit = db.execute("""SELECT 1 FROM ai_task_credits c
            JOIN ai_task_credit_units s ON s.task_id=c.task_id AND s.run=c.run
            WHERE c.task_id=? AND c.run=? AND c.owner=? AND s.unit_id=?""",
            (task_id,run,scope.identity,scope.unit_id)).fetchone()
        if not credit:
            raise PermissionError("Lượt chạy chưa được cấp hạn mức trong đơn vị")
        if guard is not None:
            guard(db)
        own = db.execute("""SELECT count(*),coalesce(sum(r.input_tokens),0),
            coalesce(sum(r.output_tokens),0),coalesce(sum(r.micro_usd),0)
            FROM ai_reservations r JOIN ai_reservation_units s ON s.reservation_id=r.id
            WHERE r.day=? AND r.owner=? AND s.unit_id=?""",
            (day,scope.identity,scope.unit_id)).fetchone()
        total = db.execute("""SELECT count(*),coalesce(sum(r.micro_usd),0),
            coalesce(sum(r.output_tokens),0) FROM ai_reservations r
            JOIN ai_reservation_units s ON s.reservation_id=r.id
            WHERE r.day=? AND s.unit_id=?""",(day,scope.unit_id)).fetchone()
        project = db.execute("""SELECT coalesce(sum(r.output_tokens),0)
            FROM ai_reservations r JOIN ai_reservation_units s ON s.reservation_id=r.id
            WHERE r.day=? AND s.unit_id=? AND r.project_id=?""",
            (day,scope.unit_id,project_id)).fetchone()[0] if project_id else 0
        host = db.execute("""SELECT count(*),coalesce(sum(micro_usd),0),
            coalesce(sum(output_tokens),0) FROM ai_reservations WHERE day=?""",(day,)).fetchone()
        legacy = self._legacy(db,scope.identity,day)
        # model_calls cũ không có USD: chỉ cộng lượt/token vào trần máy chủ,
        # không đoán đơn vị sở hữu hoặc tự bịa chi phí lịch sử.
        limits = self.host_policy
        if (own[0] >= policy['calls_per_user'] or total[0] >= policy['calls_global']
                or own[1]+input_tokens > policy['input_tokens_per_user']
                or own[2]+output_tokens > policy['output_tokens_per_user']
                or total[2]+output_tokens > policy['output_tokens_global']
                or (project_id and project+output_tokens > policy['output_tokens_per_project'])
                or own[3]+cost > money(policy['usd_per_user'])*1000000
                or total[1]+cost > money(policy['usd_global'])*1000000
                or host[0]+legacy[2] >= limits['calls_global']
                or host[2]+legacy[3]+output_tokens > limits['output_tokens_global']
                or host[1]+cost > money(limits['usd_global'])*1000000):
            raise LoiMoHinhBDSG("Đã chạm trần lượt, token hoặc chi phí AI trong ngày; chưa gửi yêu cầu tới nhà cung cấp.")
        cursor = db.execute("""INSERT INTO ai_reservations
            (owner,day,task_id,model_id,input_tokens,output_tokens,micro_usd,created,project_id)
            VALUES(?,?,?,?,?,?,?,?,?)""",(scope.identity,day,task_id,model_id,input_tokens,
                output_tokens,cost,self.clock(),project_id))
        db.execute("INSERT INTO ai_reservation_units VALUES(?,?)",(cursor.lastrowid,scope.unit_id))
        return cursor.lastrowid

    def _status_scoped(self,db,actor,scope,policy,day):
        tasks = db.execute("""SELECT count(*) FROM ai_task_credits c
            JOIN ai_task_credit_units s ON s.task_id=c.task_id AND s.run=c.run
            WHERE c.owner=? AND c.day=? AND s.unit_id=?""",
            (scope.identity,day,scope.unit_id)).fetchone()[0]
        row = db.execute("""SELECT count(*),coalesce(sum(r.input_tokens),0),
            coalesce(sum(r.output_tokens),0),coalesce(sum(r.micro_usd),0)
            FROM ai_reservations r JOIN ai_reservation_units s ON s.reservation_id=r.id
            WHERE r.owner=? AND r.day=? AND s.unit_id=?""",
            (scope.identity,day,scope.unit_id)).fetchone()
        return {'timezone':'Asia/Ho_Chi_Minh','resets_at_unix':(day+1)*86400-25200,
            'tasks_used':tasks,'tasks_remaining':max(0,policy['tasks_per_user']-tasks),
            'calls_used':row[0],'input_tokens_reserved':row[1],
            'output_tokens_reserved':row[2],'usd_reserved':str(Decimal(row[3])/1000000),
            'policy':dict(policy),'accounting':'Giữ trước bảo thủ theo giá chủ quản khai báo; chưa phải hóa đơn nhà cung cấp.'}

    def status(self, actor, policy):
        owner = self._owner(actor)
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            day = self.day()
            scope = self.units.require(actor,db) if self.units is not None else None
            if scope:
                return self._status_scoped(db,actor,scope,policy,day)
            assert_unscoped_store(db)
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
