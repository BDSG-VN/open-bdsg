"""Tác vụ bền vững theo quy trình; không giả lập mô hình AI hoặc kết nối nghiệp vụ."""

import json
import secrets
import threading
import time
import unicodedata
import re
import contextvars
from concurrent.futures import ThreadPoolExecutor
from mo_hinh_bdsg import MoHinhBDSG, LoiMoHinhBDSG
from nhan_su import NhanSu
from doi_ngu import DoiNgu
from don_vi import assert_unscoped_store
from quyen_tac_vu import task_reference


TEMPLATES = {"de-xuat-giai-phap", "kiem-tra-ket-noi", "tong-quan", "nhan-su-chuyen-mon"}
FINAL = {"completed", "cancelled", "failed", "interrupted"}


class _StaleRun(RuntimeError):
    """Worker cũ thoát mà không sửa hoặc dừng lượt mới."""


def _text(value, minimum=1, maximum=4000):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValueError("Nội dung không hợp lệ hoặc vượt giới hạn")
    return value.strip()


def _clean(value):
    return "".join(
        c
        for c in unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
        if not unicodedata.combining(c)
    )


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def kiem_han_ket_qua(hien_co, bo_sung):
    # Cùng một hạn mức cho báo cáo agent và cả lô tệp Python khi giữ khóa tác vụ.
    if (
        len(hien_co) + len(bo_sung) > 80
        or sum(len(a.get("content", "").encode()) for a in [*hien_co, *bo_sung])
        > 8 * 1024 * 1024
    ):
        raise ValueError("Kết quả vượt hạn 80 tệp hoặc 8 MiB; giữ nguyên các tệp đã có")


class CongViec:
    """Hai worker, hàng đợi có giới hạn; chỉ gọi các công cụ đọc đã định trước."""

    def __init__(self, kho, core, *, units=None, scoped_ai=None):
        self.kho, self.core = kho, core
        self.units = units
        self.scoped_ai = scoped_ai
        self.lock = threading.RLock()
        self.closed = False
        self.context_override = contextvars.ContextVar(
            "bdsg_delegated_context", default=None
        )
        self.execution = contextvars.ContextVar('bdsg_task_execution',default=None)
        self.model = MoHinhBDSG()
        self.staff = NhanSu()
        self.workforce = DoiNgu(self.staff)
        with kho.ket_noi() as db:
            if units is None:
                assert_unscoped_store(db)
            db.execute(
                "CREATE TABLE IF NOT EXISTS model_calls(owner TEXT,created REAL)"
            )
            columns = {r[1] for r in db.execute("PRAGMA table_info(model_calls)")}
            if "project_id" not in columns:
                db.execute(
                    "ALTER TABLE model_calls ADD COLUMN project_id TEXT DEFAULT ''"
                )
            if "output_reserved" not in columns:
                db.execute(
                    "ALTER TABLE model_calls ADD COLUMN output_reserved INTEGER DEFAULT 4096"
                )
            db.execute(
                "CREATE INDEX IF NOT EXISTS model_calls_time ON model_calls(created)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS cong_viec_tasks(id TEXT PRIMARY KEY, owner TEXT, created REAL, updated REAL, status TEXT, document TEXT)"
            )
            if units is not None:
                db.execute("""CREATE TABLE IF NOT EXISTS cong_viec_units(
                    task_id TEXT PRIMARY KEY REFERENCES cong_viec_tasks(id),
                    unit_id TEXT NOT NULL REFERENCES don_vi(id),epoch INTEGER NOT NULL,
                    revision INTEGER NOT NULL)""")
            db.execute(
                "CREATE INDEX IF NOT EXISTS cong_viec_owner ON cong_viec_tasks(owner,created)"
            )
            # Không tự chạy lại tác vụ sau khởi động: công cụ ngoài có thể đã chạy.
            condition = "(status IN ('queued','running','cancelling') OR json_extract(document,'$.runtime_running')=1)"
            if units is not None:
                condition += ' AND id IN (SELECT task_id FROM cong_viec_units)'
            for row in db.execute('SELECT document FROM cong_viec_tasks WHERE '+condition).fetchall():
                task = json.loads(row[0])
                if units is not None:
                    self._binding(db,task)
                task["status"] = "interrupted"
                task["runtime_running"] = False
                if task.get("team"):
                    task["team"]["state"] = "interrupted"
                    task["team"]["finished"] = time.time()
                    for specialist in task["team"].get("agents", []):
                        if specialist["state"] in ("queued", "running"):
                            specialist.update(state="interrupted", finished=time.time())
                task["updated"] = time.time()
                for step in task["steps"]:
                    if step["status"] == "running":
                        step.update(status="interrupted", finished=time.time())
                self._event(
                    task,
                    "interrupted",
                    "Tiến trình đã khởi động lại; cần yêu cầu tiếp tục rõ ràng.",
                )
                db.execute(
                    "UPDATE cong_viec_tasks SET status=?,updated=?,document=? WHERE id=?",
                    (
                        task["status"],
                        task["updated"],
                        json.dumps(task, ensure_ascii=False),
                        task["id"],
                    ),
                )
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bdsg-task")

    def reserve_model(self, actor, project_id=""):
        self._auth(actor, True)
        if self.units is not None:
            raise PermissionError('Ngân sách mô hình theo đơn vị chưa sẵn sàng')
        now = time.time()
        day = ((now + 25200) // 86400) * 86400 - 25200
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            own = db.execute(
                "SELECT count(*) FROM model_calls WHERE owner=? AND created>=?",
                (actor["id"], day),
            ).fetchone()[0]
            total = db.execute(
                "SELECT count(*) FROM model_calls WHERE created>=?", (day,)
            ).fetchone()[0]
            if own >= 100 or total >= 200:
                raise LoiMoHinhBDSG(
                    "Đã chạm giới hạn API trong ngày: 100 lượt/danh tính, 200 lượt/toàn hệ thống theo giờ Việt Nam."
                )
            own_budget = db.execute(
                "SELECT coalesce(sum(output_reserved),0) FROM model_calls WHERE owner=? AND created>=?",
                (actor["id"], day),
            ).fetchone()[0]
            total_budget = db.execute(
                "SELECT coalesce(sum(output_reserved),0) FROM model_calls WHERE created>=?",
                (day,),
            ).fetchone()[0]
            project_budget = (
                db.execute(
                    "SELECT coalesce(sum(output_reserved),0) FROM model_calls WHERE project_id=? AND created>=?",
                    (project_id, day),
                ).fetchone()[0]
                if project_id
                else 0
            )
            if (
                own_budget + 4096 > 65536
                or total_budget + 4096 > 524288
                or (project_id and project_budget + 4096 > 131072)
            ):
                raise LoiMoHinhBDSG(
                    "Đã chạm ngân sách token đầu ra ngày. Giữ trước 4096 token/request, kể cả khi API thiếu usage."
                )
            db.execute(
                "INSERT INTO model_calls(owner,created,project_id,output_reserved) VALUES (?,?,?,?)",
                (actor["id"], now, project_id, 4096),
            )

    def _auth(self, actor, write=False):
        verify = getattr(self.core, "verify_actor", None)
        if verify and not verify(actor):
            raise PermissionError("Danh tính đã bị thu hồi")
        if (
            not isinstance(actor, dict)
            or not isinstance(actor.get("id"), str)
            or actor.get("role") not in ("agent", "operator", "quan-tri")
        ):
            raise PermissionError("Cần danh tính đã xác thực")
        if write and actor["role"] not in ("operator", "quan-tri"):
            raise PermissionError("Danh tính này không có quyền điều phối tác vụ")
        if self.units is not None:
            with self.kho.ket_noi() as db:
                self.units.require(actor, db)

    def _load(self, task_id):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            row = db.execute(
                "SELECT document FROM cong_viec_tasks WHERE id=?", (task_id,)
            ).fetchone()
            if not row:
                raise ValueError("Không tìm thấy tác vụ trong phạm vi quyền")
            task = json.loads(row[0])
            self._check_generation(task)
            if self.units is not None:
                self._binding(db,task)
            return task

    def _binding(self, db, task):
        return task_reference(db,task)

    def _check_generation(self, task):
        execution = self.execution.get()
        if execution and execution['id']==task['id'] and execution['run']!=task['run']:
            raise _StaleRun()

    def _bind_execution(self, callback):
        execution = self.execution.get()
        def bound(*args, **kwargs):
            token = self.execution.set(execution)
            try: return callback(*args, **kwargs)
            finally: self.execution.reset(token)
        return bound

    def _save_generation(self, db, task, renew=False):
        row = db.execute('SELECT document FROM cong_viec_tasks WHERE id=?',(task['id'],)).fetchone()
        if not row: raise _StaleRun()
        previous = json.loads(row[0])
        self._check_generation(previous)
        self._check_generation(task)
        if renew:
            if previous['run']+1 != task['run'] or previous['status'] not in FINAL or previous.get('runtime_running'):
                raise _StaleRun()
        elif previous['run']!=task['run']:
            raise _StaleRun()

    def _worker_actor(self, task_id):
        task = self._load(task_id)
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            reference = self._binding(db,task)
            execution = self.execution.get()
            if execution and execution.get('reference') is not None:
                if reference != execution['reference']: raise _StaleRun()
                reference = execution['reference']
            actor = self.units.restore(reference,db)
            if task.get('project_id'):
                self.projects.authorize(actor,task['project_id'],db=db)
            return actor

    def _save(self, task, *, actor=None, renew=False):
        task["updated"] = time.time()
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            self._save_generation(db,task,renew)
            reference = None
            if self.units is not None:
                reference = self._binding(db,task)
                execution = self.execution.get()
                if execution and execution['id']==task['id'] and execution.get('reference') != reference:
                    raise _StaleRun()
                current = actor or self.units.restore(reference,db)
                scope = self.units.require(current,db)
                if scope.identity != task['owner'] or scope.unit_id != reference['unit_id']:
                    raise PermissionError('Phạm vi tác vụ không khớp')
                if (actor is None or renew) and task.get('project_id'):
                    self.projects.authorize(current,task['project_id'],db=db)
                if renew:
                    db.execute('UPDATE cong_viec_units SET epoch=?,revision=? WHERE task_id=?',
                               (scope.epoch,scope.revision,task['id']))
                    reference = self.units.reference(current,db)
            db.execute(
                "UPDATE cong_viec_tasks SET updated=?,status=?,document=? WHERE id=?",
                (
                    task["updated"],
                    task["status"],
                    json.dumps(task, ensure_ascii=False),
                    task["id"],
                ),
            )
        return reference

    def _stop_unit_task(self, task_id, cancel=False):
        # Chỉ ghi chuyển trạng thái từ bản đang lưu; không nhận kết quả đến
        # muộn của worker đã mất quyền và không cần hồi sinh quyền để dừng.
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT document FROM cong_viec_tasks WHERE id=?',(task_id,)).fetchone()
            if not row: return
            task = json.loads(row[0])
            try: self._check_generation(task)
            except _StaleRun: return
            self._binding(db,task)
            task['status'] = 'cancelled' if cancel or task.get('cancel_requested') else 'failed'
            task['runtime_running'] = False
            task['updated'] = time.time()
            if cancel: task['cancel_requested'] = True
            for step in task['steps']:
                if step['status']=='running': step.update(status=task['status'],finished=time.time())
            self._event(task,task['status'],'Đã dừng lượt chạy; kiểm quyền đơn vị và cấu hình trước khi tiếp tục.')
            db.execute('UPDATE cong_viec_tasks SET updated=?,status=?,document=? WHERE id=?',
                       (task['updated'],task['status'],json.dumps(task,ensure_ascii=False),task_id))

    def _event(self, task, kind, text, **extra):
        task["events"].append(
            {
                "id": secrets.token_hex(6),
                "kind": kind,
                "message": text,
                "created": time.time(),
                "run": task["run"],
                **extra,
            }
        )
        task["events"] = task["events"][-200:]

    @staticmethod
    def _keep_team_outputs(task, snapshot):
        # Bàn giao xong phải đọc được ngay, kể cả khi chuyên môn khác thất bại.
        names = {artifact["name"] for artifact in task["artifacts"]}
        additions = []
        for specialist in snapshot.get("agents", []):
            name = specialist["skill_id"] + "-luot-" + str(task["run"]) + ".md"
            if (
                specialist["state"] == "completed"
                and specialist.get("output")
                and name not in names
            ):
                additions.append(
                    {
                        "id": secrets.token_hex(8),
                        "name": name,
                        "title": specialist["name"],
                        "mime_type": "text/markdown",
                        "content": specialist["output"],
                        "created": time.time(),
                        "run": task["run"],
                    }
                )
        kiem_han_ket_qua(task["artifacts"], additions)
        task["artifacts"].extend(additions)

    def _visible(self, actor, task):
        self._auth(actor)
        if self.units is not None:
            with self.kho.ket_noi() as db:
                db.execute('BEGIN')
                scope = self.units.require(actor, db)
                row = db.execute('SELECT unit_id FROM cong_viec_units WHERE task_id=?',(task['id'],)).fetchone()
                if not row or row[0] != scope.unit_id or task.get('unit_id') != scope.unit_id or task['owner'] != scope.identity:
                    raise ValueError("Không tìm thấy tác vụ trong phạm vi quyền")
            return task
        if task["owner"] != actor["id"] and actor["role"] != "quan-tri":
            raise ValueError("Không tìm thấy tác vụ trong phạm vi quyền")
        return task

    def _capacity(self, actor, creating=False):
        if self.closed:
            raise RuntimeError("Bộ điều phối đang dừng")
        with self.kho.ket_noi() as db:
            active = db.execute(
                "SELECT count(*) FROM cong_viec_tasks WHERE status IN ('queued','running','cancelling')"
            ).fetchone()[0]
            own = db.execute(
                "SELECT count(*) FROM cong_viec_tasks WHERE owner=?", (actor["id"],)
            ).fetchone()[0]
            if self.units is not None:
                scope = self.units.require(actor,db)
                active = db.execute('''SELECT count(*) FROM cong_viec_tasks t JOIN cong_viec_units s ON s.task_id=t.id
                    WHERE t.status IN ('queued','running','cancelling')''').fetchone()[0]
                own = db.execute('''SELECT count(*) FROM cong_viec_tasks t JOIN cong_viec_units s ON s.task_id=t.id
                    WHERE t.owner=? AND s.unit_id=?''',(scope.identity,scope.unit_id)).fetchone()[0]
        if active >= 16:
            raise ValueError("Hàng đợi đã đầy; đợi tác vụ hiện tại hoàn tất")
        if creating and own >= 100:
            raise ValueError("Không gian đã đạt giới hạn 100 tác vụ cho danh tính này")

    def _model_for(self, actor):
        if self.units is not None and self.scoped_ai is not None:
            return self.scoped_ai.bind(actor)
        return self.model

    def _check_scoped_selection(self, model, selection):
        if self.units is not None and self.scoped_ai is not None and selection != 'auto':
            if not model.configured or selection not in {m['id'] for m in model.catalogue()['models']}:
                raise ValueError('Mô hình không nằm trong danh mục đang hoạt động')

    def create(self, actor, args):
        self._auth(actor, True)
        model = self._model_for(actor)
        if model.configuration_error:
            raise ValueError(model.configuration_error)
        if not isinstance(args, dict):
            raise ValueError("Thông tin tác vụ không hợp lệ")
        if self.units is not None and ((self.scoped_ai is None and model.configured) or any(args.get(key) for key in (
                'allow_python','allow_action_drafts','allow_delegation','allow_module_reads','browser_hosts'))):
            raise PermissionError('Chưa có cấu hình công cụ và mô hình riêng theo đơn vị')
        prompt = _text(args.get("prompt"), 10)
        project_id = args.get("project_id", "")
        if not isinstance(project_id, str):
            raise ValueError("Dự án không hợp lệ")
        project = self.projects.context_for(actor, project_id) if project_id else None
        documents = (
            self.documents.snapshot(actor, args.get("document_ids", []), project_id)
            if args.get("document_ids")
            else []
        )
        inherited = self.context_override.get()
        if inherited is not None:
            if inherited.get("project_id", "") != project_id or [
                d["id"] for d in documents
            ] != [d["id"] for d in inherited.get("documents", [])]:
                raise ValueError("Phạm vi tác vụ con không khớp tác vụ cha")
            project = json.loads(json.dumps(inherited.get("project")))
            documents = json.loads(json.dumps(inherited.get("documents", [])))
        allow_python = args.get("allow_python", False)
        allow_drafts = args.get("allow_action_drafts", False)
        allow_delegation = args.get("allow_delegation", False)
        if type(allow_delegation) is not bool or (
            allow_delegation and actor["role"] != "quan-tri"
        ):
            raise PermissionError("Chỉ chủ quản được cấp điều phối agent")
        hosts = args.get("browser_hosts", [])
        if type(allow_python) is not bool or type(allow_drafts) is not bool:
            raise ValueError("Quyền thực thi không hợp lệ")
        if (
            not isinstance(hosts, list)
            or len(hosts) > 5
            or any(
                not isinstance(h, str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,252}", h)
                for h in hosts
            )
        ):
            raise ValueError("Phạm vi trình duyệt cần tối đa 5 tên miền chính xác")
        template = args.get("template", "nhan-su-chuyen-mon")
        if template not in TEMPLATES:
            raise ValueError("Quy trình chưa được hỗ trợ")
        model_selection = args.get("model_selection","auto")
        if not isinstance(model_selection,str):
            raise ValueError("Mô hình được chọn chưa hợp lệ")
        self._check_scoped_selection(model,model_selection)
        hub = model if self.units is not None and self.scoped_ai is not None else getattr(self,"ai",None)
        if model_selection != "auto" and (model is not hub or model_selection not in {m["id"] for m in hub.catalogue()["models"]}):
            raise ValueError("Mô hình không nằm trong danh mục đang hoạt động")
        ids = args.get("module_ids", [])
        valid = {p["id"] for p in self.core.catalogue}
        if (
            not isinstance(ids, list)
            or len(ids) > len(valid)
            or any(not isinstance(x, str) or x not in valid for x in ids)
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Mô-đun không tồn tại hoặc bị lặp")
        allow_reads = args.get("allow_module_reads", False)
        if not isinstance(allow_reads, bool):
            raise ValueError("Quyền đọc mô-đun phải là giá trị bật hoặc tắt")
        allowed_tools = {}
        if allow_reads:
            if actor["role"] != "quan-tri":
                raise PermissionError(
                    "Chỉ chủ quản được cấp quyền đọc dữ liệu mô-đun cho tác vụ"
                )
            if not ids or not model.configured:
                raise ValueError(
                    "Cần chọn mô-đun cụ thể và cấu hình mô hình trước khi cho đọc dữ liệu"
                )
            allowed_tools = MoHinhBDSG.module_read_tools(self.core, actor, ids)
            if not allowed_tools:
                raise ValueError(
                    "Mô-đun đã chọn chưa có công cụ đọc được xác minh và cấp quyền"
                )
        now = time.time()
        task = {
            "id": secrets.token_hex(12),
            "owner": actor["id"],
            "title": prompt[:100],
            "prompt": prompt,
            "status": "queued",
            "created": now,
            "updated": now,
            "mode": model.public_status()["mode"],
            "template": template,
            "model_selection": model_selection,
            "module_ids": ids,
            "project": project,
            "project_id": project_id,
            "documents": documents,
            "allow_python": allow_python,
            "browser_hosts": hosts,
            "allow_action_drafts": allow_drafts,
            "allow_delegation": allow_delegation,
            "allow_module_reads": allow_reads,
            "allowed_module_tools": allowed_tools,
            "run": 1,
            "steps": [],
            "events": [],
            "artifacts": [],
            "messages": [{"role": "user", "content": prompt, "created": now}],
            "cancel_requested": False,
        }
        self._event(
            task,
            "queued",
            "Đã nhận tác vụ. "
            + (
                "Dùng API mô hình đã cấu hình."
                if model.configured
                else "Chạy quy trình có kịch bản, không phải mô hình AI tự suy luận."
            ),
        )
        with self.lock:
            self._capacity(actor, True)
            reference = None
            task["mode"] = model.public_status()["mode"]
            with self.kho.ket_noi() as db:
                db.execute("BEGIN IMMEDIATE")
                if self.units is not None:
                    scope = self.units.require(actor,db)
                    reference = self.units.reference(actor,db)
                    task['unit_id'] = scope.unit_id
                    if project_id:
                        self.projects.authorize(actor,project_id,db=db)
                if model is hub and hub.configured:
                    if self.units is not None:
                        hub.admit(db,actor,task["id"],task["run"],model_selection,project_id=project_id)
                    else:
                        hub.admit(db,actor,task["id"],task["run"],model_selection)
                db.execute(
                    "INSERT INTO cong_viec_tasks VALUES (?,?,?,?,?,?)",
                    (
                        task["id"],
                        task["owner"],
                        now,
                        now,
                        task["status"],
                        json.dumps(task, ensure_ascii=False),
                    ),
                )
                if self.units is not None:
                    db.execute('INSERT INTO cong_viec_units VALUES(?,?,?,?)',
                               (task['id'],scope.unit_id,scope.epoch,scope.revision))
            self.pool.submit(self._run, dict(actor), task["id"], model, task['run'], reference)
        return {"id": task["id"], "status": "queued"}

    def list(self, actor):
        self._auth(actor)
        with self.kho.ket_noi() as db:
            query = "SELECT document FROM cong_viec_tasks"
            params = ()
            if self.units is not None:
                db.execute('BEGIN')
                scope = self.units.require(actor,db)
                query = '''SELECT t.document FROM cong_viec_tasks t JOIN cong_viec_units s ON s.task_id=t.id
                    WHERE t.owner=? AND s.unit_id=?'''
                params = (scope.identity,scope.unit_id)
            elif actor["role"] != "quan-tri":
                query += " WHERE owner=?"
                params = (actor["id"],)
            rows = db.execute(
                query + " ORDER BY created DESC LIMIT 100", params
            ).fetchall()
            if self.units is not None:
                for row in rows: self._binding(db,json.loads(row[0]))
        keys = (
            "id",
            "owner",
            "title",
            "prompt",
            "status",
            "created",
            "updated",
            "mode",
            "template",
            "module_ids",
            "run",
        )
        return {
            "tasks": [
                {
                    **{k: t[k] for k in keys},
                    "project_id": t.get("project_id", ""),
                    "project_name": (t.get("project") or {}).get("name", ""),
                    "allow_module_reads": t.get("allow_module_reads", False),
                    "allow_python": t.get("allow_python", False),
                    "allow_delegation": t.get("allow_delegation", False),
                    "browser_hosts": t.get("browser_hosts", []),
                    "usage": t.get("usage"),
                    "artifact_count": len(t["artifacts"]),
                    **({'unit_id':t['unit_id']} if self.units is not None else {}),
                }
                for t in (json.loads(r[0]) for r in rows)
            ]
        }

    def detail(self, actor, task_id):
        task_id = _text(task_id, 1, 80)
        return self._visible(actor, self._load(task_id))

    def followup(self, actor, task_id, text):
        self._auth(actor, True)
        model = self._model_for(actor)
        if self.units is not None and self.scoped_ai is None and model.configured:
            raise PermissionError('Chưa có mô hình riêng theo đơn vị')
        if model.configuration_error:
            raise ValueError(model.configuration_error)
        text = _text(text, 10)
        with self.lock:
            task = self.detail(actor, task_id)
            if task["status"] not in FINAL or task.get("runtime_running"):
                raise ValueError("Đợi tác vụ kết thúc trước khi bổ sung yêu cầu")
            if task["run"] >= 10:
                raise ValueError("Tác vụ đã đạt giới hạn 10 lượt")
            self._capacity(actor)
            self._check_scoped_selection(model,task.get('model_selection','auto'))
            hub = getattr(self,"ai",None)
            if task.get("team"):
                task.setdefault("team_history", []).append(task.pop("team"))
                task["team_history"] = task["team_history"][-9:]
            task["run"] += 1
            task["mode"] = model.public_status()["mode"]
            task["messages"].append(
                {"role": "user", "content": text, "created": time.time()}
            )
            task["status"], task["cancel_requested"] = "queued", False
            self._event(
                task, "queued", "Đã nhận yêu cầu bổ sung; giữ lại các kết quả trước."
            )
            hub = getattr(self,"ai",None)
            reference = None
            if self.units is not None and self.scoped_ai is not None and model.configured:
                reference = self._renew_scoped_ai(actor,task,model)
            elif model is hub and hub.configured:
                task["updated"] = time.time()
                with self.kho.ket_noi() as db:
                    db.execute("BEGIN IMMEDIATE")
                    self._save_generation(db,task,renew=True)
                    hub.admit(db,actor,task_id,task["run"],task.get("model_selection","auto"))
                    db.execute("UPDATE cong_viec_tasks SET updated=?,status=?,document=? WHERE id=?",
                               (task["updated"],task["status"],json.dumps(task,ensure_ascii=False),task_id))
            else:
                reference = self._save(task,actor=actor,renew=True)
            self.pool.submit(self._run, dict(actor), task_id, model, task['run'], reference)
            return task

    def _renew_scoped_ai(self, actor, task, model):
        # Nhận lượt và gia hạn tư cách cùng giao dịch; lỗi hạn mức không để lại lượt nửa chừng.
        task['updated'] = time.time()
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            self._save_generation(db,task,renew=True)
            self._binding(db,task)
            scope = self.units.require(actor,db)
            if scope.identity != task['owner'] or scope.unit_id != task['unit_id']:
                raise PermissionError('Phạm vi tác vụ không khớp')
            if task.get('project_id'):
                self.projects.authorize(actor,task['project_id'],db=db)
            model.admit(db,actor,task['id'],task['run'],task.get('model_selection','auto'),
                        project_id=task.get('project_id',''))
            db.execute('UPDATE cong_viec_units SET epoch=?,revision=? WHERE task_id=?',
                       (scope.epoch,scope.revision,task['id']))
            db.execute('UPDATE cong_viec_tasks SET updated=?,status=?,document=? WHERE id=?',
                       (task['updated'],task['status'],json.dumps(task,ensure_ascii=False),task['id']))
            return self.units.reference(actor,db)

    def cancel(self, actor, task_id):
        self._auth(actor, True)
        with self.lock:
            task = self.detail(actor, task_id)
            if task["status"] not in FINAL or task.get("runtime_running"):
                task["cancel_requested"] = True
                task["status"] = (
                    "cancelled" if task["status"] == "queued" else "cancelling"
                )
                self._event(
                    task,
                    "cancel_requested",
                    "Đã yêu cầu dừng. Lời gọi đang chạy chỉ kết thúc theo giới hạn của công cụ.",
                )
                self._save(task,actor=actor)
        callback = getattr(self, "on_cancel", None)
        if callback:
            callback(task["owner"], task["id"] + ":" + str(task["run"]))
        return task

    def cancel_owner(self, identity):
        with self.lock:
            with self.kho.ket_noi() as db:
                query = "SELECT document FROM cong_viec_tasks WHERE owner=? AND (status IN ('queued','running','cancelling') OR json_extract(document,'$.runtime_running')=1)"
                if self.units is not None: query += ' AND id IN (SELECT task_id FROM cong_viec_units)'
                rows = db.execute(query,(identity,)).fetchall()
            for row in rows:
                task = json.loads(row[0])
                if self.units is not None:
                    self._stop_unit_task(task['id'],cancel=True)
                    continue
                task["cancel_requested"] = True
                task["status"] = (
                    "cancelled" if task["status"] == "queued" else "cancelling"
                )
                self._event(
                    task,
                    "identity-revoked",
                    "Đã dừng quyền tác vụ do danh tính bị thu hồi.",
                )
                self._save(task)

    def _read(self, actor, name):
        self._auth(actor)
        if self.units is not None and name != 'nen_tang.danh_sach':
            raise PermissionError('Đầu nối theo đơn vị chưa sẵn sàng')
        response = self.core.goi(actor, name, {})
        if not response.get("ok"):
            raise RuntimeError("Công cụ đọc không sẵn sàng trong phạm vi quyền")
        return response["ket_qua"]

    def modules(self, actor):
        if actor is None:
            return {
                "modules": [
                    {
                        **p,
                        "kind": "web",
                        "mcp": {
                            "state": "can-xac-thuc",
                            "read_tools": [],
                            "write_tools": [],
                        },
                    }
                    for p in self.core.catalogue
                ]
            }
        self._auth(actor)
        products = self._read(actor, "nen_tang.danh_sach")["products"]
        connections = {
            c["platform_id"]: c
            for c in self._read(actor, "nen_tang.ket_noi")["connections"]
        }
        return {
            "modules": [
                {
                    **p,
                    "kind": "mcp-declared" if p["id"] in connections else "web",
                    "mcp": connections.get(
                        p["id"],
                        {"state": "chua-cau-hinh", "read_tools": [], "write_tools": []},
                    ),
                }
                for p in products
            ]
        }

    def _begin_step(self, task_id, name, tool=None):
        with self.lock:
            task = self._load(task_id)
            if self.closed or task["cancel_requested"]:
                task["status"] = "cancelled"
                self._event(task, "cancelled", "Đã dừng trước bước tiếp theo.")
                self._save(task)
                return None
            task["status"] = "running"
            step = {
                "id": secrets.token_hex(6),
                "name": name,
                "status": "running",
                "started": time.time(),
                "finished": None,
                "tool": tool,
                "run": task["run"],
            }
            task["steps"].append(step)
            self._event(task, "step_started", name, step_id=step["id"])
            self._save(task)
            return step["id"]

    def _finish_step(self, task_id, step_id, summary):
        with self.lock:
            task = self._load(task_id)
            step = next(s for s in task["steps"] if s["id"] == step_id)
            step.update(status="completed", finished=time.time(), summary=summary)
            self._event(task, "step_completed", summary, step_id=step_id)
            self._save(task)

    def _choose(self, task, products):
        if task["module_ids"]:
            return [p for p in products if p["id"] in task["module_ids"]]
        query = _clean(
            " ".join(m["content"] for m in task["messages"] if m["role"] == "user")
        )
        groups = {
            "bat dong san": ["Bất động sản"],
            "thuong mai": ["Thương mại số"],
            "ban hang": ["Thương mại số", "Vận hành"],
            "nong nghiep": ["Nông nghiệp"],
            "trang trai": ["Nông nghiệp"],
            "du lich": ["Thương mại số"],
            "tri thuc": ["Tri thức", "Cộng đồng"],
            "dao tao": ["Tri thức"],
            "van hanh": ["Vận hành"],
            "cong nghe": ["AI", "AI & công nghệ", "Không gian số", "Hạ tầng dịch vụ"],
        }
        picked = {g for term, values in groups.items() if term in query for g in values}
        exact = [
            p
            for p in products
            if (_clean(p["name"]) != "bdsg" and _clean(p["name"]) in query)
            or p["group"] in picked
        ]
        return exact or products

    def _report(self, task, products, connections):
        selected = self._choose(task, products)
        mapping = {c["platform_id"]: c for c in connections}
        heading = {
            "de-xuat-giai-phap": "Đề xuất triển khai",
            "kiem-tra-ket-noi": "Đối chiếu cấu hình kết nối",
            "tong-quan": "Tổng quan hệ sinh thái",
        }[task["template"]]
        lines = [
            "# " + heading + " BDSG Thanh Hoá",
            "",
            "## Nhu cầu",
            task["prompt"],
            "",
        ]
        if task.get("project"):
            p = task["project"]
            lines += [
                "## Dự án: " + p["name"],
                "### Chỉ dẫn của dự án",
                p["instructions"],
                "### Ngữ cảnh đã chụp khi giao việc",
                p["context"],
                "",
            ]
        for document in task.get("documents", []):
            lines += [
                "## Tài liệu: " + document["name"],
                f"Nguồn [{document['id']}] phiên bản {document['version']}, SHA-256 {document['sha256']}",
                document["text"],
                "(Văn bản đã rút gọn)" if document["truncated"] else "",
                "",
            ]
        if task["run"] > 1:
            lines += ["## Yêu cầu bổ sung", task["messages"][-1]["content"], ""]
        lines += [
            "## Phạm vi thực hiện",
            "Đây là kết quả của quy trình có kịch bản, dựa trên danh mục và cấu hình hiện tại. Không phải phản hồi từ mô hình AI. Không thực hiện thay đổi trên nền tảng bên ngoài.",
            "",
            "## Mô-đun phù hợp",
            "| Nền tảng | Vai trò | Liên kết | Kết nối MCP |",
            "|---|---|---|---|",
        ]
        for p in selected:
            connection = mapping.get(p["id"])
            state = (
                'Chưa sẵn sàng theo đơn vị' if task.get('unit_id') else
                "Đã khai báo, chưa được tác vụ kiểm tra"
                if connection
                else "Chưa cấu hình"
            )
            lines.append(
                "| "
                + " | ".join(
                    _cell(x) for x in (p["name"], p["purpose"], p["url"], state)
                )
                + " |"
            )
        lines += [
            "",
            "## Lộ trình đề xuất",
            "1. Tư vấn: xác định nhu cầu, người phụ trách và tiêu chí hoàn tất.",
            "2. Triển khai: mở các nền tảng đã chọn; quản trị nền tảng cấp endpoint MCP và quyền công cụ cần dùng.",
            "3. Vận hành: kiểm chứng bằng dữ liệu thử; theo dõi quyền, lỗi và nhật ký trước khi dùng dữ liệu thật.",
            "4. Kinh doanh: thống nhất cách bàn giao giữa các mô-đun và đo kết quả theo yêu cầu thực tế.",
            "",
            "## Bằng chứng và giới hạn",
            f"- Đọc danh mục qua nhân BDSG: {len(products)} mục.",
            '- Không đọc cấu hình đầu nối toàn cổng; đầu nối theo đơn vị chưa sẵn sàng.' if task.get('unit_id') else
            f"- Đọc cấu hình đầu nối: {len(connections)} đã khai báo; số này không chứng minh kết nối thành công.",
            f"- Đề xuất {len(selected)} mô-đun dựa trên lựa chọn rõ ràng hoặc đối sánh từ khoá; chưa có tối ưu bằng AI.",
            "- Các liên kết web không tạo đăng nhập dùng chung hoặc đồng bộ dữ liệu.",
            "- Tác vụ chỉ đọc danh mục/cấu hình. Không gọi công cụ ghi, không gửi dữ liệu khách hàng ra ngoài.",
        ]
        return "\n".join(lines)

    def _run(self, actor, task_id, model=None, run=None, reference=None):
        if run is None: run = self._load(task_id)['run']
        token = self.execution.set({'id':task_id,'run':run,'reference':reference})
        try:
            self._execute(actor,task_id,model)
        except _StaleRun:
            return
        finally:
            self.execution.reset(token)

    def _execute(self, actor, task_id, model=None):
        # Giữ nguyên nhà cung cấp/chứng thư của lượt chạy khi chủ quản đổi cấu hình.
        model = model or self.model
        try:
            if self.units is not None:
                actor = self._worker_actor(task_id)
            step = self._begin_step(
                task_id, "Đọc danh mục nền tảng", "nen_tang.danh_sach"
            )
            if not step:
                return
            products = self._read(actor, "nen_tang.danh_sach")["products"]
            self._finish_step(
                task_id, step, f"Đã đọc {len(products)} mục từ danh mục BDSG."
            )
            step = self._begin_step(
                task_id, "Đối chiếu đầu nối MCP đã khai báo", "nen_tang.ket_noi"
            ) if self.units is None else self._begin_step(task_id,'Đầu nối theo đơn vị chưa sẵn sàng')
            if not step:
                return
            connections = [] if self.units is not None else self._read(actor, "nen_tang.ket_noi")["connections"]
            self._finish_step(
                task_id,
                step,
                'Đầu nối theo đơn vị chưa sẵn sàng; không đọc cấu hình toàn cổng.' if self.units is not None
                else f"Có {len(connections)} đầu nối khai báo; chưa gọi nghiệp vụ bên ngoài.",
            )
            step = self._begin_step(
                task_id,
                "Mô hình AI xử lý yêu cầu"
                if model.configured
                else "Tổng hợp đề xuất và kết quả",
            )
            if not step:
                return
            with self.lock:
                task = self._load(task_id)
            if model.configured:
                prompt = "\n\n".join(
                    m["content"] for m in task["messages"] if m["role"] == "user"
                )
                context = {
                    "products": self._choose(task, products),
                    "connections": connections,
                    "project": task.get("project"),
                    "documents": task.get("documents", []),
                    "task_id": task["id"],
                    "run": task["run"],
                    "project_id": task.get("project_id",""),
                    "execution_scope": {
                        "python": task.get("allow_python", False),
                        "browser": bool(task.get("browser_hosts")),
                        "drafts": task.get("allow_action_drafts", False),
                        "delegation": task.get("allow_delegation", False),
                    },
                    "previous_artifacts": [
                        a["content"] for a in task["artifacts"][-2:]
                    ],
                    "template": task["template"],
                    "model_selection": task.get("model_selection","auto"),
                }
                if model is getattr(self,"ai",None) or (self.units is not None and self.scoped_ai is not None):
                    context["available_models"] = model.catalogue()["models"]
                context["module_scope"] = {
                    "allow_reads": task.get("allow_module_reads", False),
                    "selected_ids": task["module_ids"],
                    "read_tools": task.get("allowed_module_tools", {}),
                }

                def on_event(kind, message, **extra):
                    with self.lock:
                        current = self._load(task_id)
                        if self.closed or current['cancel_requested']:
                            raise RuntimeError('Tác vụ đã được yêu cầu dừng')
                        if kind == "model-reserve" and self.units is None and model is not getattr(self,"ai",None):
                            self.reserve_model(actor, task.get("project_id", ""))
                        if kind == "team-state":
                            snapshot = extra.pop("team")
                            self._keep_team_outputs(current, snapshot)
                            current["team"] = {**snapshot, "run": current["run"]}
                        if kind == "model-usage":
                            usage = current.setdefault(
                                "usage",
                                {
                                    "requests": 0,
                                    "input_tokens": 0,
                                    "output_tokens": 0,
                                    "complete": True,
                                },
                            )
                            usage["requests"] += 1
                            for key in ("input_tokens", "output_tokens"):
                                if type(extra.get(key)) is int:
                                    usage[key] += extra[key]
                                else:
                                    usage["complete"] = False
                        self._event(current, kind, message, **extra)
                        self._save(current)

                def cancelled_check():
                    with self.lock:
                        verify = getattr(self.core, "verify_actor", None)
                        return (
                            self.closed
                            or self._load(task_id)["cancel_requested"]
                            or bool(verify and not verify(actor))
                        )

                def cancelled():
                    try: return cancelled_check()
                    except (_StaleRun, PermissionError, ValueError): return True

                # Provider/đội chuyên môn có thể gọi callback trên thread khác;
                # ContextVar của worker không tự lan sang các thread đó.
                on_event = self._bind_execution(on_event)
                cancelled = self._bind_execution(cancelled)

                if task["template"] == "nhan-su-chuyen-mon":
                    content = self.workforce.run(
                        prompt,
                        context,
                        lambda p, c, event, stop: model.run(
                            p, {**c,"task_id":task["id"],"run":task["run"],
                                "project_id":task.get("project_id", "")}, self.core, actor, event, stop
                        ),
                        on_event,
                        cancelled,
                    )
                else:
                    content = model.run(
                        prompt, context, self.core, actor, on_event, cancelled
                    )
                if cancelled():
                    raise RuntimeError("Tác vụ đã được yêu cầu dừng")
            else:
                if task["template"] == "nhan-su-chuyen-mon":
                    with self.lock:
                        current = self._load(task_id)
                        current["team"] = {
                            "state": "awaiting_model",
                            "agents": [],
                            "run": current["run"],
                            "version": self.staff.version,
                            "execution_kind": "not_executed",
                        }
                        self._save(current)
                    raise LoiMoHinhBDSG(
                        "Cần cấu hình mô hình AI trước khi Agent tổng phân công và thực thi chuyên môn."
                    )
                content = self._report(task, products, connections)
            with self.lock:
                task = self._load(task_id)
                # Chốt cùng khóa với cancel: kết quả đến muộn không được xuất bản.
                if self.closed or task["cancel_requested"]:
                    raise RuntimeError("Tác vụ đã được yêu cầu dừng")
                self._auth(actor, True)
                additions = [
                    {
                        "id": secrets.token_hex(8),
                        "name": "de-xuat-thanhhoa-luot-" + str(task["run"]) + ".md",
                        "title": "Báo cáo tác vụ",
                        "mime_type": "text/markdown",
                        "content": content,
                        "created": time.time(),
                        "run": task["run"],
                    }
                ]
                kiem_han_ket_qua(task["artifacts"], additions)
                task["artifacts"].extend(additions)
                current_step = next(s for s in task["steps"] if s["id"] == step)
                current_step.update(
                    status="completed", finished=time.time(),
                    summary="Đã lưu báo cáo riêng tư cho tác vụ.",
                )
                self._event(task, "step_completed", current_step["summary"], step_id=step)
                task["status"] = "completed"
                message = (
                    "Đã lưu kết quả do API mô hình đã cấu hình tạo; các công cụ đọc vẫn đi qua nhân và quyền hiện tại."
                    if model.configured
                    else "Đã tạo báo cáo từ danh mục và cấu hình thực tế. Chưa chạy mô hình AI hoặc thao tác nghiệp vụ bên ngoài."
                )
                task["messages"].append(
                    {"role": "assistant", "content": message, "created": time.time()}
                )
                self._event(task, task["status"], message)
                self._save(task)
        except _StaleRun:
            return
        except Exception as error:
            # Không ghi exception công cụ vào thông điệp công khai: có thể chứa endpoint/chứng thư.
            with self.lock:
                if self.units is not None:
                    self._stop_unit_task(task_id,cancel=self.closed)
                    return
                task = self._load(task_id)
                task["status"] = "cancelled" if self.closed or task["cancel_requested"] else "failed"
                for s in task["steps"]:
                    if s["status"] == "running":
                        s.update(status=task["status"], finished=time.time())
                self._event(
                    task,
                    task["status"],
                    str(error)
                    if isinstance(error, LoiMoHinhBDSG)
                    else "Không hoàn tất bước hiện tại. Kiểm quyền và cấu hình rồi bổ sung yêu cầu để thử lại.",
                )
                self._save(task)

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=True, cancel_futures=False)
