"""Phê duyệt ghi MCP theo đơn vị; claim một lần, không replay khi không rõ kết quả."""
import hashlib
import json
import secrets
import time

from hanh_dong import active_actor


class HanhDongDonVi:
    def __init__(self, kho, core, tasks, units, connectors, *, clock=time.time, ai=None):
        self.kho, self.core, self.tasks = kho, core, tasks
        self.units, self.connectors, self.clock = units, connectors, clock
        self.ai = ai
        with kho.ket_noi() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS unit_actions(
                id TEXT PRIMARY KEY,unit_id TEXT NOT NULL REFERENCES don_vi(id),
                owner TEXT NOT NULL,task_id TEXT NOT NULL,payload TEXT NOT NULL,
                digest TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,
                expires REAL NOT NULL,result TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS unit_actions_scope ON unit_actions(unit_id,owner,created);
                CREATE TABLE IF NOT EXISTS unit_action_cancelled_runs(
                    task_id TEXT NOT NULL REFERENCES cong_viec_tasks(id),run INTEGER NOT NULL,
                    owner TEXT NOT NULL,PRIMARY KEY(task_id,run));
                UPDATE unit_actions SET status='unknown' WHERE status='executing';''')

    @staticmethod
    def _encode(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)

    @staticmethod
    def _reference(scope):
        return {'unit_id': scope.unit_id, 'identity': scope.identity,
                'epoch': scope.epoch, 'revision': scope.revision}

    def _visible(self, db, actor, row, *, admin=False):
        scope = self.units.require(actor, db)
        if (not row or row['unit_id'] != scope.unit_id or (admin and scope.role != 'admin')
                or (row['owner'] != scope.identity and scope.role != 'admin')):
            raise PermissionError('Không có hành động trong phạm vi quyền')
        payload = json.loads(row['payload'])
        if payload['project_id']:
            self.tasks.projects.authorize(actor, payload['project_id'], db=db)
        return scope

    def _get(self, db, actor, identifier, *, admin=False):
        if not isinstance(identifier, str) or len(identifier) > 80:
            raise ValueError('Mã hành động không hợp lệ')
        row = db.execute('SELECT * FROM unit_actions WHERE id=?', (identifier,)).fetchone()
        self._visible(db, actor, row, admin=admin)
        return row

    @staticmethod
    def _public(row):
        return {**dict(row), 'payload': json.loads(row['payload']), 'result': json.loads(row['result'])}

    def get(self, actor, identifier):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            return self._public(self._get(db, actor, identifier))

    def list(self, actor):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            scope = self.units.require(actor, db)
            rows = db.execute('''SELECT * FROM unit_actions WHERE unit_id=?
                AND (?='admin' OR owner=?) ORDER BY created DESC,id LIMIT 100''',
                (scope.unit_id, scope.role, scope.identity)).fetchall()
            visible = []
            for row in rows:
                try:
                    self._visible(db, actor, row)
                except (ValueError, PermissionError):
                    continue
                visible.append(self._public(row))
            return {'actions': visible}

    def _owner_task(self, payload):
        reference = payload['owner_scope']
        original = self.units.bind(active_actor(self.kho, reference['identity']), reference['unit_id'])
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            scope = self.units.require(original, db)
            if self._reference(scope) != reference:
                raise PermissionError('Tư cách người đề xuất đã thay đổi')
            self._not_cancelled(db, payload)
            self._check_source(db, payload)
        task = self.tasks.detail(original, payload['task_id'])
        if payload['project_id'] and self.tasks.projects.authorize(original, payload['project_id'])['archived']:
            raise PermissionError('Dự án đã lưu trữ')
        if (task['owner'] != original['id'] or task['run'] != payload['run']
                or task.get('project_id', '') != payload['project_id']
                or task.get('cancel_requested') or task['status'] in ('cancelled', 'cancelling', 'failed', 'interrupted')
                or payload['arguments']['platform_id'] not in task['module_ids']):
            raise PermissionError('Tác vụ hoặc lượt được đề xuất không còn hiệu lực')
        config = self.connectors.prepare_write(original, payload['arguments']['platform_id'],
                                               payload['arguments']['tool'])
        if config['revision'] != payload['connector_revision']:
            raise PermissionError('Cấu hình đầu nối khác bản được đề xuất')
        return original

    def _source(self, db, actor, task, arguments):
        authority = self.tasks.inbound_mcp
        if authority is None:
            if task.get('mcp_delegated'):
                raise PermissionError('Thiếu bộ kiểm nguồn dự thảo')
            return None
        return authority.draft_source(actor, task, arguments, db)

    def _check_source(self, db, payload):
        row = db.execute('SELECT document FROM cong_viec_tasks WHERE id=?', (payload['task_id'],)).fetchone()
        task = json.loads(row[0]) if row else {}
        if task.get('run') != payload['run']:
            raise PermissionError('Dự thảo không thuộc lượt hiện hành')
        owner = self.units.restore(payload['owner_scope'], db)
        if self._source(db, owner, task, payload['arguments']) != payload.get('mcp_source'):
            raise PermissionError('Nguồn dự thảo đã thay đổi')

    @staticmethod
    def _not_cancelled(db, payload):
        if db.execute('SELECT 1 FROM unit_action_cancelled_runs WHERE task_id=? AND run=?',
                      (payload['task_id'], payload['run'])).fetchone():
            raise PermissionError('Lượt tác vụ đã hủy quyền đề xuất ghi')

    @staticmethod
    def _settled(db, unit_id, arguments, exclude=''):
        # Chặn theo nền tảng/công cụ vì upstream không cấp idempotency chung;
        # đổi arguments/task không được dùng để lách yêu cầu đối soát.
        if db.execute("""SELECT 1 FROM unit_actions WHERE unit_id=? AND id<>?
                AND status IN ('executing','unknown')
                AND json_extract(payload,'$.arguments.platform_id')=?
                AND json_extract(payload,'$.arguments.tool')=? LIMIT 1""",
                (unit_id, exclude, arguments['platform_id'], arguments['tool'])).fetchone():
            raise PermissionError('Công cụ đang thực thi hoặc có kết quả cần quản trị đối soát')

    def propose(self, actor, args, *, task_context=None):
        if not isinstance(args, dict) or set(args) != {'task_id', 'tool', 'arguments'}:
            raise ValueError('Dự thảo không hợp lệ')
        arguments = args['arguments']
        if (args['tool'] != 'ket_noi.ghi' or not isinstance(arguments, dict)
                or set(arguments) != {'platform_id', 'tool', 'arguments'}
                or not isinstance(arguments['arguments'], dict)
                or not isinstance(arguments['tool'], str)):
            raise ValueError('Chỉ hỗ trợ dự thảo ghi MCP theo đơn vị')
        task = self.tasks.detail(actor, args['task_id'])
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            scope = self.units.require(actor, db)
            reference = self._reference(scope)
            source = self._source(db, actor, task, arguments)
            if source and task_context is None:
                raise PermissionError('Dự thảo có nguồn MCP cần ngữ cảnh worker tin cậy')
        if task['owner'] != actor['id'] or arguments['platform_id'] not in task['module_ids']:
            raise PermissionError('Ngoài mô-đun của tác vụ do mình giao')
        config = self.connectors.prepare_write(actor, arguments['platform_id'], arguments['tool'])
        now = self.clock()
        payload = {'tool': 'ket_noi.ghi', 'arguments': arguments, 'task_id': task['id'],
                   'run': task['run'], 'project_id': task.get('project_id', ''),
                   'owner_scope': reference, 'connector_revision': config['revision'], 'expires': now+900}
        if source is not None:
            payload['mcp_source'] = source
        # Đọc lại qua JSON để caller không đổi dict đã được chụp/duyệt.
        encoded = self._encode(payload)
        if len(encoded.encode()) > 16000:
            raise ValueError('Dự thảo vượt giới hạn 16 KiB')
        payload = json.loads(encoded)
        self._owner_task(payload)
        identifier = secrets.token_hex(12)
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            if self._reference(self.units.require(actor, db)) != reference:
                raise PermissionError('Phạm vi đã thay đổi')
            self._not_cancelled(db, payload)
            self._check_source(db, payload)
            self._settled(db, scope.unit_id, arguments)
            if task_context is not None:
                if not isinstance(task_context, tuple) or len(task_context) != 3 or self.ai is None:
                    raise PermissionError('Thiếu ngữ cảnh AI tin cậy cho dự thảo')
                self.ai.require_config_revision(actor, task_context[2], db)
                # Đọc generation/grant trong giao dịch INSERT, không giữ khóa worker
                # lúc đang nắm writer SQLite hoặc tin vào task_id do model gửi.
                row = db.execute('SELECT document FROM cong_viec_tasks WHERE id=?', (task['id'],)).fetchone()
                current = json.loads(row[0]) if row else {}
                if (task_context[:2] != (task['id'], payload['run']) or current.get('run') != payload['run']
                        or current.get('status') != 'running' or current.get('cancel_requested')
                        or not current.get('allow_action_drafts')
                        or arguments['tool'] not in current.get('allowed_module_write_tools', {}).get(arguments['platform_id'], [])
                        or current.get('module_connector_revisions', {}).get(arguments['platform_id']) != config['revision']):
                    raise PermissionError('Dự thảo của agent ngoài phạm vi hoặc lượt đã giao')
            db.execute("UPDATE unit_actions SET status='expired' WHERE unit_id=? AND owner=? AND status='awaiting' AND expires<=?",
                       (scope.unit_id, scope.identity, now))
            pending = db.execute("SELECT count(*) FROM unit_actions WHERE unit_id=? AND owner=? AND status='awaiting'",
                                 (scope.unit_id, scope.identity)).fetchone()[0]
            if pending >= 20:
                raise ValueError('Đã có 20 hành động chờ duyệt trong đơn vị')
            db.execute('INSERT INTO unit_actions VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (identifier, scope.unit_id, scope.identity, task['id'], encoded,
                        hashlib.sha256(encoded.encode()).hexdigest(), 'awaiting', now, now+900, '{}'))
            self.units._audit(db, scope.identity, 'de-xuat-ghi-don-vi', identifier)
        return self.get(actor, identifier)

    def decide(self, actor, args):
        if (not isinstance(args, dict) or set(args) != {'id', 'digest', 'approve'}
                or type(args['approve']) is not bool):
            raise ValueError('Nội dung duyệt không hợp lệ')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            row = self._get(db, actor, args['id'], admin=True)
            approver = self._reference(self.units.require(actor, db))
            action = self._public(row)
        if args['digest'] != action['digest']:
            raise ValueError('Nội dung duyệt không khớp')
        payload = action['payload']
        if args['approve']:
            self._owner_task(payload)
        state = 'executing' if args['approve'] else 'rejected'
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            self._get(db, actor, action['id'], admin=True)
            if self._reference(self.units.require(actor, db)) != approver:
                raise PermissionError('Tư cách người duyệt đã thay đổi')
            if args['approve']:
                self._not_cancelled(db, payload)
                self._check_source(db, payload)
                self._settled(db, action['unit_id'], payload['arguments'], action['id'])
            changed = db.execute("""UPDATE unit_actions SET status=? WHERE id=? AND digest=?
                AND status='awaiting' AND (?=0 OR expires>?)""",
                (state, action['id'], action['digest'], int(args['approve']), self.clock())).rowcount
            if not changed:
                raise ValueError('Hành động hết hạn hoặc đã được xử lý')
            self.units._audit(db, actor['id'], 'duyet-ghi-don-vi' if args['approve'] else 'tu-choi-ghi-don-vi', action['id'])
        if not args['approve']:
            return self.get(actor, action['id'])

        def guard():
            self._owner_task(payload)
            with self.kho.ket_noi() as db:
                db.execute('BEGIN')
                current = self._get(db, actor, action['id'], admin=True)
                if (self._reference(self.units.require(actor, db)) != approver
                        or current['status'] != 'executing' or current['digest'] != action['digest']
                        or current['expires'] <= self.clock()):
                    raise PermissionError('Phê duyệt không còn hiệu lực')
                self._check_source(db, payload)

        result = {'message': 'Cần đối soát nền tảng; không tự gọi lại công cụ ghi'}
        state = 'unknown'
        try:
            guard()
            call = payload['arguments']
            with self.connectors.authorization(actor, call['platform_id'], call['tool'], call['arguments'],
                                               payload['connector_revision'], guard):
                response = self.core.goi(actor, 'ket_noi.ghi', call, tool_guard=guard,
                                         expected_revision=payload['connector_revision'])
            guard()
            if response.get('ok') and not response.get('ket_qua', {}).get('isError'):
                state = 'completed'
                result = response if len(self._encode(response).encode()) <= 100000 else {
                    'ok': True, 'message': 'Kết quả lớn; xem trên nền tảng gốc'}
        except Exception:
            # Không lưu exception/response lỗi vì upstream có thể phản chiếu token.
            pass
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE unit_actions SET status=?,result=? WHERE id=? AND status='executing' AND digest=?",
                       (state, self._encode(result), action['id'], action['digest']))
            self.units._audit(db, actor['id'], 'ket-qua-ghi-don-vi-'+state, action['id'])
        return self.get(actor, action['id'])

    def preview(self, actor, identifier):
        raise PermissionError('Dự thảo trình duyệt chưa hỗ trợ phạm vi đơn vị')

    def cancel_task(self, owner, reference):
        """Callback tin cậy từ tác vụ, kể cả khi lượt đã hoàn thành trước lúc hủy."""
        task_id, run = reference.rsplit(':', 1)
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO unit_action_cancelled_runs VALUES(?,?,?)', (task_id, int(run), owner))
            db.execute('''UPDATE unit_actions SET
                result=?,status=CASE WHEN status='awaiting' THEN 'cancelled' ELSE 'unknown' END
                WHERE owner=? AND task_id=? AND json_extract(payload,'$.run')=?
                AND status IN ('awaiting','executing')''',
                (self._encode({'message': 'Đã hủy; cần đối soát nếu yêu cầu đã gửi'}), owner, task_id, int(run)))

    def reconcile(self, actor, args):
        if (not isinstance(args, dict) or set(args) != {'id', 'digest', 'outcome', 'note'}
                or args['outcome'] not in ('applied', 'not-applied')
                or not isinstance(args['note'], str) or not 10 <= len(args['note'].strip()) <= 1000):
            raise ValueError('Cần kết quả đối soát và ghi chú 10–1000 ký tự, không chứa chứng thư')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._get(db, actor, args['id'], admin=True)
            if row['digest'] != args['digest'] or row['status'] != 'unknown':
                raise ValueError('Chỉ đối soát đúng nội dung chưa rõ kết quả')
            result = {'reconciliation': {'outcome': args['outcome'], 'note': args['note'].strip(),
                                         'by': actor['id'], 'at': self.clock()},
                      'message': 'Xác nhận do quản trị nhập; hệ thống chưa tự kiểm upstream'}
            db.execute("UPDATE unit_actions SET status=?,result=? WHERE id=? AND status='unknown'",
                       ('reconciled-'+args['outcome'], self._encode(result), row['id']))
            self.units._audit(db, actor['id'], 'doi-soat-ghi-don-vi-'+args['outcome'], row['id'])
        return self.get(actor, args['id'])
