"""Yêu cầu kinh doanh cá nhân hoặc nội dung dự án được cấp quyền."""
import secrets
import time


class KinhDoanh:
    def __init__(self, kho, units=None):
        self.kho, self.units = kho, units
        self.projects = None
        if units is not None:
            with kho.ket_noi() as db:
                db.execute('''CREATE TABLE IF NOT EXISTS unit_requests(
                    id TEXT PRIMARY KEY,unit_id TEXT NOT NULL REFERENCES don_vi(id),
                    owner TEXT NOT NULL,owner_epoch INTEGER NOT NULL,
                    project_id TEXT REFERENCES du_an(id),title TEXT NOT NULL,
                    sector TEXT NOT NULL,description TEXT NOT NULL,stage TEXT NOT NULL,
                    created REAL NOT NULL)''')
                db.execute('CREATE INDEX IF NOT EXISTS unit_request_owner ON unit_requests(unit_id,owner,owner_epoch,created)')
                db.execute('CREATE INDEX IF NOT EXISTS unit_request_project ON unit_requests(project_id,created)')

    def call(self, actor, operation, args):
        if self.units is None:
            if operation == 'danh_sach':
                return {'requests': self.kho.yeu_cau(actor['id'], actor['role'] == 'quan-tri')}
            if operation == 'tao_yeu_cau':
                if args.get('project_id') is not None:
                    raise ValueError('Yêu cầu gắn dự án cần chế độ đơn vị')
                return self.kho.tao_yeu_cau(actor['id'], args)
            return self.kho.doi_chang(actor['id'], args.get('id'), args.get('stage'), actor['role'] == 'quan-tri')
        allowed = {'danh_sach': set(), 'tao_yeu_cau': {'title','sector','description','project_id'},
                   'doi_chang': {'id','stage'}}
        if not isinstance(args, dict) or operation not in allowed or set(args)-allowed[operation]:
            raise ValueError('Tham số yêu cầu kinh doanh không hợp lệ')
        if actor.get('mcp_delegation') is not None:
            raise PermissionError('Credential MCP chưa được cấp quyền yêu cầu kinh doanh')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN' if operation == 'danh_sach' else 'BEGIN IMMEDIATE')
            scope = self.units.require(actor, db)
            if operation == 'danh_sach':
                # Chỉ lấy ứng viên trong đơn vị/đích chia sẻ; DuAn quyết định quyền
                # nội dung lần cuối. Không cắt LIMIT trước khi loại bản không có quyền.
                candidates = db.execute('''SELECT * FROM unit_requests r WHERE
                    (project_id IS NULL AND unit_id=? AND owner=? AND owner_epoch=?) OR
                    (project_id IS NOT NULL AND (unit_id=? OR EXISTS(
                        SELECT 1 FROM du_an_unit_grants g WHERE g.project_id=r.project_id
                        AND g.unit_id=? AND g.identity=? AND g.epoch=?)))
                    ORDER BY created DESC,id DESC''',
                    (scope.unit_id, scope.identity, scope.epoch, scope.unit_id,
                     scope.unit_id, scope.identity, scope.epoch))
                rows = []
                for row in candidates:
                    try:
                        self._authorize(actor, scope, row, db)
                    except ValueError:
                        continue
                    rows.append({key: row[key] for key in
                        ('id','owner','project_id','title','sector','description','stage','created')})
                    if len(rows) == 200:
                        break
                return {'requests': rows}
            if operation == 'tao_yeu_cau':
                title, sector, description = self._fields(args)
                project_id = args.get('project_id')
                source_unit = scope.unit_id
                if project_id is not None:
                    project = self._project(actor, project_id, db, write=True)
                    source_unit = project['unit_id']
                identifier, stage = secrets.token_hex(12), 'tu-van'
                db.execute('INSERT INTO unit_requests VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (identifier, source_unit, scope.identity, scope.epoch, project_id,
                     title, sector, description, stage, time.time()))
            else:
                identifier, stage = args.get('id'), args.get('stage')
                if not isinstance(identifier, str) or not 1 <= len(identifier) <= 80:
                    raise ValueError('Không tìm thấy yêu cầu trong phạm vi quyền')
                if stage not in ('tu-van','trien-khai','van-hanh','kinh-doanh'):
                    raise ValueError('Chặng không hợp lệ')
                row = db.execute('SELECT * FROM unit_requests WHERE id=?', (identifier,)).fetchone()
                if row is None:
                    raise ValueError('Không tìm thấy yêu cầu trong phạm vi quyền')
                self._authorize(actor, scope, row, db, write=True)
                db.execute('UPDATE unit_requests SET stage=? WHERE id=?', (stage, identifier))
            db.execute('INSERT INTO su_kien(actor,action,target,created) VALUES(?,?,?,?)',
                (scope.identity, 'kinh-doanh-'+operation, scope.unit_id+':'+identifier, time.time()))
        return {'id': identifier, 'stage': stage}

    def _project(self, actor, identifier, db, write=False):
        project = self.projects.authorize(actor, identifier, write=write, db=db)
        if write and project['archived']:
            raise ValueError('Dự án đã lưu trữ; không thể đổi yêu cầu kinh doanh')
        return project

    def _authorize(self, actor, scope, row, db, write=False):
        if row['project_id'] is not None:
            project = self._project(actor, row['project_id'], db, write=write)
            if project['unit_id'] != row['unit_id']:
                raise ValueError('Không tìm thấy yêu cầu trong phạm vi quyền')
        elif (row['unit_id'], row['owner'], row['owner_epoch']) != (scope.unit_id, scope.identity, scope.epoch):
            raise ValueError('Không tìm thấy yêu cầu trong phạm vi quyền')

    @staticmethod
    def _fields(args):
        title, sector, description = (args.get(key) for key in ('title','sector','description'))
        if not isinstance(title, str) or not 3 <= len(title.strip()) <= 160:
            raise ValueError('Tên yêu cầu cần từ 3 đến 160 ký tự')
        if not isinstance(description, str) or not 10 <= len(description.strip()) <= 4000:
            raise ValueError('Mô tả cần từ 10 đến 4000 ký tự')
        if sector not in ('bat-dong-san','thuong-mai','van-hanh','cong-nghe','nong-nghiep','tri-thuc'):
            raise ValueError('Lĩnh vực không hợp lệ')
        return title.strip(), sector, description.strip()
