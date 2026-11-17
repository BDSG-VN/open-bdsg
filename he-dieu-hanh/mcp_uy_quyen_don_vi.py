"""Grant MCP và nguồn tác vụ theo đơn vị; chưa bật HTTP hoặc OAuth."""
import hashlib
import json
import os
import re
import secrets
import stat
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit


READ_TOOLS = frozenset({'nen_tang.danh_sach', 'nen_tang.ket_noi', 'mo_dun.danh_sach',
                        'du_an.danh_sach', 'cong_viec.danh_sach', 'cong_viec.chi_tiet'})
RESOURCE_TOOLS = frozenset({'du_an.danh_sach', 'cong_viec.danh_sach', 'cong_viec.chi_tiet'})
TASK_TOOLS = frozenset({'cong_viec.tao', 'cong_viec.tiep_tuc', 'cong_viec.dung'})
EXECUTION_TOOLS = frozenset({'nen_tang.danh_sach', 'mo_dun.danh_sach'})


class LoiChungThuMCP(PermissionError):
    """Credential không còn dùng được; không trả lý do chứa tài nguyên riêng."""


@dataclass(frozen=True)
class _UyQuyen:
    id: str
    revision: str
    _issuer: object = field(repr=False, compare=False)
    task_id: str = ''
    run: int = 0


class UyQuyenMCPDonVi:
    def __init__(self, kho, units, core, projects, *, origin, clock=time.time, connectors=None):
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            raise ValueError('Cần origin HTTPS cố định cho MCP')
        self.resource = origin.rstrip('/')+'/mcp'
        self.kho, self.units, self.core, self.projects = kho, units, core, projects
        self.connectors = connectors
        self.clock, self._issuer = clock, object()
        with kho.ket_noi() as db:
            # Giao dịch cũng tuần tự hóa tạo epoch giữa các instance cùng kho.
            db.execute('BEGIN IMMEDIATE')
            self._epoch = self._load_epoch()
            db.execute('''CREATE TABLE IF NOT EXISTS unit_mcp_grants(
                id TEXT PRIMARY KEY,unit_id TEXT NOT NULL REFERENCES don_vi(id),owner TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,revision TEXT NOT NULL,document TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS unit_mcp_task_runs(
                task_id TEXT NOT NULL REFERENCES cong_viec_tasks(id),run INTEGER NOT NULL,
                reference TEXT NOT NULL,PRIMARY KEY(task_id,run))''')

    def _load_epoch(self):
        # Cố ý ngoài ALLOWED của data backup: restore không hồi sinh bearer cũ.
        path = self.kho.root/'mcp-inbound-epoch'
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(secrets.token_bytes(32))
                stream.flush()
                os.fsync(stream.fileno())
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or (os.name != 'nt' and stat.S_IMODE(info.st_mode) & 0o077)):
            raise PermissionError('Tệp epoch MCP phải là tệp riêng của kho')
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as stream:
            actual = os.fstat(stream.fileno())
            if (actual.st_dev, actual.st_ino) != (info.st_dev, info.st_ino):
                raise PermissionError('Tệp epoch MCP đã thay đổi')
            raw = stream.read(33)
        if len(raw) != 32:
            raise PermissionError('Epoch MCP không hợp lệ; không tự ghi đè')
        return hashlib.sha256(raw).hexdigest()

    def _web_scope(self, actor, db):
        if not isinstance(actor, dict) or 'mcp_delegation' in actor:
            raise PermissionError('Cần phiên web để quản lý credential MCP')
        return self.units.require(actor, db)

    def _project_scope(self, actor, project_ids, db):
        return {identifier: self.projects.authorization_reference(actor, identifier, db)
                if identifier else {'kind': 'standalone'} for identifier in project_ids}

    def _public(self, document, *, own):
        result = {key: document[key] for key in (
            'id', 'name', 'client_id', 'owner', 'unit_id', 'tools', 'revision', 'created', 'expires', 'enabled')}
        result.update(project_count=len(document['project_ids']), expired=document['expires'] <= self.clock(),
                      issuer_current=document['issuer_epoch'] == self._epoch, credential_type='manual_bearer')
        if own:
            result['project_ids'] = list(document['project_ids'])
            profile = document.get('task_profile')
            result['task_profile'] = ({key: value for key, value in profile.items()
                                       if key != 'connector_revisions'} if profile else None)
        return result

    def create(self, actor, data):
        required = {'name', 'client_id', 'tools', 'project_ids', 'expires_in'}
        if not isinstance(data, dict) or not required <= set(data) or set(data)-required-{'task_profile'}:
            raise ValueError('Cần nhãn, client, công cụ, dự án và hạn dùng cụ thể')
        name, client, tools, project_ids, duration = (data[key] for key in (
            'name', 'client_id', 'tools', 'project_ids', 'expires_in'))
        if (not isinstance(name, str) or not 3 <= len(name.strip()) <= 100 or not name.isprintable()
                or not isinstance(client, str) or not re.fullmatch(r'[A-Za-z0-9_-]{3,80}', client)):
            raise ValueError('Nhãn hoặc mã client không hợp lệ')
        if (not isinstance(tools, list) or not tools or len(tools) > len(READ_TOOLS | TASK_TOOLS)
                or any(not isinstance(tool, str) or tool not in READ_TOOLS | TASK_TOOLS for tool in tools)
                or len(set(tools)) != len(tools)):
            raise ValueError('Chỉ cấp công cụ đã chuyển theo đơn vị, không wildcard')
        profile = data.get('task_profile')
        if TASK_TOOLS.intersection(tools):
            if (not isinstance(profile, dict) or 'allow_ai' not in profile
                    or set(profile)-{'allow_ai', 'module_reads', 'module_drafts'}
                    or type(profile['allow_ai']) is not bool):
                raise ValueError('Tác vụ cần cấp rõ profile danh mục và quyền gọi AI')
        elif profile is not None:
            raise ValueError('Profile tác vụ cần công cụ tác vụ được cấp rõ')
        if (not isinstance(project_ids, list) or len(project_ids) > 100
                or any(not isinstance(identifier, str) or len(identifier) > 80 for identifier in project_ids)
                or len(set(project_ids)) != len(project_ids)
                or ((RESOURCE_TOOLS | TASK_TOOLS).intersection(tools) and not project_ids)):
            raise ValueError('Cần phạm vi dự án cụ thể; chuỗi rỗng chỉ cho việc độc lập')
        if type(duration) is not int or not 900 <= duration <= 86400:
            raise ValueError('Hạn credential cần từ 15 phút đến 24 giờ')
        identifier, revision = secrets.token_hex(12), secrets.token_hex(16)
        credential = 'bdsg_u_'+secrets.token_urlsafe(32)
        now = self.clock()
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            scope = self._web_scope(actor, db)
            project_refs = self._project_scope(actor, project_ids, db)
            if profile is not None:
                reads, drafts = profile.get('module_reads', {}), profile.get('module_drafts', {})
                if (reads or drafts) and (not profile['allow_ai'] or self.connectors is None):
                    raise PermissionError('Công cụ mô-đun cần AI và bộ kiểm đầu nối')
                revisions = (self.connectors.delegation_reference(actor, reads, drafts, db)
                             if self.connectors is not None else {})
                if not isinstance(reads, dict) or not isinstance(drafts, dict):
                    raise ValueError('Phạm vi công cụ mô-đun không hợp lệ')
                profile = {'allow_ai': profile['allow_ai'], 'module_reads': reads,
                           'module_drafts': drafts, 'connector_revisions': revisions}
            declarations = {item['ten'] for item in self.core.nhan.danh_sach_cong_cu(self.core.danh_tinh(actor))}
            if not set(tools) <= declarations:
                raise PermissionError('Không được ủy quyền công cụ mình chưa có')
            count = db.execute('''SELECT count(*) FROM unit_mcp_grants WHERE unit_id=? AND owner=?
                AND json_extract(document,'$.enabled')=1 AND json_extract(document,'$.expires')>?
                AND json_extract(document,'$.issuer_epoch')=?''',
                (scope.unit_id, scope.identity, now, self._epoch)).fetchone()[0]
            total = db.execute('SELECT count(*) FROM unit_mcp_grants WHERE unit_id=? AND owner=?',
                               (scope.unit_id, scope.identity)).fetchone()[0]
            if count >= 64 or total >= 512:
                raise ValueError('Đã đạt giới hạn credential; cần thu hồi hoặc xử lý lưu trữ theo chính sách')
            document = {'id': identifier, 'revision': revision, 'name': name.strip(), 'client_id': client,
                        'unit_id': scope.unit_id, 'owner': scope.identity,
                        'owner_scope': self.units.reference(actor, db), 'tools': list(tools),
                        'project_ids': list(project_ids), 'project_refs': project_refs, 'resource': self.resource,
                        'task_profile': dict(profile) if profile is not None else None,
                        'issuer_epoch': self._epoch, 'created': now, 'expires': now+duration, 'enabled': True}
            db.execute('INSERT INTO unit_mcp_grants VALUES(?,?,?,?,?,?)',
                       (identifier, scope.unit_id, scope.identity, hashlib.sha256(credential.encode()).hexdigest(),
                        revision, json.dumps(document, ensure_ascii=False)))
            self.units._audit(db, scope.identity, 'cap-uy-quyen-mcp-don-vi', identifier)
        return {**self._public(document, own=True), 'credential': credential}

    def list(self, actor):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            scope = self._web_scope(actor, db)
            rows = db.execute("SELECT document FROM unit_mcp_grants WHERE unit_id=? AND (?='admin' OR owner=?) ORDER BY id",
                              (scope.unit_id, scope.role, scope.identity)).fetchall()
            return {'grants': [self._public(json.loads(row[0]), own=json.loads(row[0])['owner'] == scope.identity)
                               for row in rows]}

    def revoke(self, actor, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-f0-9]{24}', identifier):
            raise ValueError('Mã ủy quyền không hợp lệ')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            scope = self._web_scope(actor, db)
            row = db.execute('SELECT document FROM unit_mcp_grants WHERE id=? AND unit_id=?',
                             (identifier, scope.unit_id)).fetchone()
            document = json.loads(row[0]) if row else None
            if not document or (document['owner'] != scope.identity and scope.role != 'admin'):
                raise PermissionError('Không có ủy quyền trong phạm vi quản lý')
            if document['enabled']:
                document.update(enabled=False, revision=secrets.token_hex(16))
                db.execute('UPDATE unit_mcp_grants SET revision=?,document=? WHERE id=?',
                           (document['revision'], json.dumps(document, ensure_ascii=False), identifier))
                self.units._audit(db, scope.identity, 'thu-hoi-uy-quyen-mcp-don-vi', identifier)
            return self._public(document, own=document['owner'] == scope.identity)

    def _require(self, actor, db):
        reference = actor.get('mcp_delegation') if isinstance(actor, dict) else None
        if not isinstance(reference, _UyQuyen) or reference._issuer is not self._issuer:
            raise LoiChungThuMCP('Cần credential MCP còn hiệu lực')
        try:
            row = db.execute('SELECT document FROM unit_mcp_grants WHERE id=?', (reference.id,)).fetchone()
            document = json.loads(row[0]) if row else None
            if (not document or not document['enabled'] or document['revision'] != reference.revision
                    or document['expires'] <= self.clock() or document['resource'] != self.resource
                    or document['issuer_epoch'] != self._epoch
                    or self.units.reference(actor, db) != document['owner_scope']):
                raise PermissionError()
            if self._project_scope(actor, document['project_ids'], db) != document.get('project_refs'):
                raise PermissionError('Thế hệ quyền dự án đã thay đổi')
            profile = document.get('task_profile') or {}
            if profile.get('module_reads') or profile.get('module_drafts'):
                if (self.connectors is None or self.connectors.delegation_reference(actor,
                        profile.get('module_reads', {}), profile.get('module_drafts', {}), db)
                        != profile.get('connector_revisions')):
                    raise PermissionError('Phạm vi đầu nối đã thay đổi')
            return document
        except (ValueError, PermissionError, KeyError):
            raise LoiChungThuMCP('Credential MCP đã hết hạn, bị thu hồi hoặc mất phạm vi') from None

    def authenticate(self, credential, *, resource=None, client_id=None):
        if (not isinstance(credential, str) or not re.fullmatch(r'bdsg_u_[A-Za-z0-9_-]{43}', credential)
                or (resource is not None and resource != self.resource)):
            raise LoiChungThuMCP('Credential MCP không hợp lệ')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            row = db.execute('SELECT document FROM unit_mcp_grants WHERE token_hash=?',
                             (hashlib.sha256(credential.encode()).hexdigest(),)).fetchone()
            document = json.loads(row[0]) if row else None
            if not document or (client_id is not None and client_id != document['client_id']):
                raise LoiChungThuMCP('Credential MCP không hợp lệ')
            try:
                actor = self.units.restore(document['owner_scope'], db)
            except (ValueError, PermissionError, KeyError):
                raise LoiChungThuMCP('Credential MCP không còn phạm vi') from None
            actor['mcp_delegation'] = _UyQuyen(document['id'], document['revision'], self._issuer)
            self._require(actor, db)
            return actor

    def reference(self, actor, db):
        document = self._require(actor, db)
        return {'id': document['id'], 'revision': document['revision'], 'issuer_epoch': self._epoch}

    def restore(self, reference, db):
        """Chỉ backend phục hồi tham chiếu đã lưu, không phải credential HTTP."""
        if (not isinstance(reference, dict) or set(reference) != {'id', 'revision', 'issuer_epoch'}
                or reference['issuer_epoch'] != self._epoch):
            raise LoiChungThuMCP('Nguồn ủy quyền không còn hiệu lực')
        row = db.execute('SELECT document FROM unit_mcp_grants WHERE id=?', (reference['id'],)).fetchone()
        document = json.loads(row[0]) if row else None
        if not document or document['revision'] != reference['revision']:
            raise LoiChungThuMCP('Nguồn ủy quyền không còn hiệu lực')
        actor = self.units.restore(document['owner_scope'], db)
        actor['mcp_delegation'] = _UyQuyen(document['id'], document['revision'], self._issuer)
        self._require(actor, db)
        return actor

    def bind_task(self, actor, task, db, *, renew=False):
        """Lưu nguồn cùng giao dịch tạo lượt; không nhận nguồn từ JSON client."""
        previous = db.execute('SELECT reference FROM unit_mcp_task_runs WHERE task_id=? AND run=?',
                              (task['id'], task['run']-1)).fetchone() if renew else None
        delegated = 'mcp_delegation' in actor
        if renew and (bool(previous) != delegated):
            raise PermissionError('Không tự đổi nguồn ủy quyền của tác vụ')
        if not delegated:
            task['mcp_delegated'] = False
            return
        document = self._require(actor, db)
        marker = actor['mcp_delegation']
        if marker.task_id or ('cong_viec.tiep_tuc' if renew else 'cong_viec.tao') not in document['tools']:
            raise PermissionError('Chưa cấp quyền tạo lượt từ client')
        reference = self.reference(actor, db)
        if previous and json.loads(previous[0]) != reference:
            raise PermissionError('Lượt mới cần cùng nguồn ủy quyền')
        profile = document.get('task_profile')
        if not profile or task.get('project_id', '') not in document['project_ids']:
            raise PermissionError('Tác vụ ngoài profile hoặc dự án được cấp')
        if any(task.get(key) for key in ('allow_python', 'allow_delegation', 'browser_hosts', 'documents')):
            raise PermissionError('Profile tác vụ chưa cấp công cụ ngoài danh mục')
        if task.get('mode') == 'mo-hinh-api' and not profile['allow_ai']:
            raise PermissionError('Profile tác vụ chưa cấp quyền gọi AI')
        selected = {}
        for flag, field, key in (('allow_module_reads', 'allowed_module_tools', 'module_reads'),
                                 ('allow_action_drafts', 'allowed_module_write_tools', 'module_drafts')):
            narrowed = {platform: [tool for tool in tools if tool in profile.get(key, {}).get(platform, [])]
                        for platform, tools in task.get(field, {}).items()}
            narrowed = {platform: tools for platform, tools in narrowed.items() if tools}
            if task.get(flag) and not narrowed:
                raise PermissionError('Profile chưa cấp công cụ mô-đun được chọn')
            task[field] = narrowed
            for platform in narrowed:
                revision = task.get('module_connector_revisions', {}).get(platform)
                if revision != profile.get('connector_revisions', {}).get(platform):
                    raise PermissionError('Đầu nối khác thế hệ đã cấp cho client')
                selected[platform] = revision
        task['module_connector_revisions'] = selected
        db.execute('INSERT INTO unit_mcp_task_runs VALUES(?,?,?)',
                   (task['id'], task['run'], json.dumps(reference)))
        task['mcp_delegated'] = True

    def restore_task(self, actor, task, db):
        row = db.execute('SELECT reference FROM unit_mcp_task_runs WHERE task_id=? AND run=?',
                         (task['id'], task['run'])).fetchone()
        if bool(row) != bool(task.get('mcp_delegated')):
            raise PermissionError('Tác vụ mất ràng buộc nguồn ủy quyền')
        if not row:
            if 'mcp_delegation' in actor:
                raise PermissionError('Không dùng token để nhận quyền của tác vụ web')
            return actor
        restored = self.restore(json.loads(row[0]), db)
        if self.units.reference(restored, db) != self.units.reference(actor, db):
            raise PermissionError('Nguồn ủy quyền không thuộc tác vụ này')
        if 'mcp_delegation' in actor and self.reference(actor, db) != json.loads(row[0]):
            raise PermissionError('Token khác nguồn của tác vụ')
        restored['mcp_delegation'] = _UyQuyen(restored['mcp_delegation'].id,
            restored['mcp_delegation'].revision, self._issuer, task['id'], task['run'])
        return restored

    def draft_source(self, actor, task, arguments, db):
        """Ràng buộc dự thảo với nguồn sống; dùng cả khi claim/sắp gửi."""
        restored = self.restore_task(actor, task, db)
        if not task.get('mcp_delegated'):
            return None
        document = self._require(restored, db)
        platform, tool = arguments['platform_id'], arguments['tool']
        if (not task.get('allow_action_drafts')
                or tool not in task.get('allowed_module_write_tools', {}).get(platform, [])
                or tool not in document['task_profile'].get('module_drafts', {}).get(platform, [])
                or task.get('module_connector_revisions', {}).get(platform)
                    != document['task_profile'].get('connector_revisions', {}).get(platform)):
            raise PermissionError('Dự thảo ngoài phạm vi nguồn tác vụ')
        return {key: document[key] for key in ('id', 'revision')}

    def tools(self, actor):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            document = self._require(actor, db)
        result = [item for item in self.core.nhan.danh_sach_cong_cu(self.core.danh_tinh(actor))
                  if item['ten'] in document['tools'] and item['ten'] in READ_TOOLS | TASK_TOOLS]
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            self._require(actor, db)
        return {'tools': [{'name': item['ten'], 'description': item['mo_ta'], 'inputSchema': item['luoc_do']}
                          for item in result]}

    def _arguments(self, db, actor, document, name, arguments):
        marker = actor['mcp_delegation']
        if marker.task_id:
            row = db.execute('SELECT document FROM cong_viec_tasks WHERE id=?', (marker.task_id,)).fetchone()
            task = json.loads(row[0]) if row else {}
            if task.get('run') != marker.run or task.get('status') != 'running' or task.get('cancel_requested'):
                raise PermissionError('Công cụ ngoài profile lượt chạy')
            self.restore_task(actor, task, db)
            if name in EXECUTION_TOOLS and arguments == {}:
                return
            if name == 'hanh_dong.de_xuat':
                if (not isinstance(arguments, dict) or set(arguments) != {'task_id', 'tool', 'arguments'}
                        or arguments['task_id'] != marker.task_id or arguments['tool'] != 'ket_noi.ghi'):
                    raise ValueError('Tham số dự thảo ngoài lượt chạy')
                call = arguments['arguments']
                if (not isinstance(call, dict) or set(call) != {'platform_id', 'tool', 'arguments'}
                        or not isinstance(call['platform_id'], str) or not isinstance(call['tool'], str)
                        or not isinstance(call['arguments'], dict)):
                    raise ValueError('Dự thảo cần công cụ cụ thể')
                self.draft_source(actor, task, call, db)
                return
            if name == 'ket_noi.doc':
                if (not isinstance(arguments, dict) or set(arguments) != {'platform_id', 'tool', 'arguments'}
                        or not isinstance(arguments['platform_id'], str) or not isinstance(arguments['tool'], str)
                        or not isinstance(arguments['arguments'], dict)):
                    raise ValueError('Tham số đọc mô-đun không hợp lệ')
                platform, tool = arguments['platform_id'], arguments['tool']
                if (task.get('allow_module_reads')
                        and tool in task.get('allowed_module_tools', {}).get(platform, [])
                        and tool in document['task_profile'].get('module_reads', {}).get(platform, [])):
                    return
            raise PermissionError('Công cụ ngoài profile lượt chạy')
        if name not in document['tools'] or name not in READ_TOOLS | TASK_TOOLS:
            raise PermissionError('Công cụ ngoài phạm vi ủy quyền')
        if name == 'cong_viec.tao':
            if not isinstance(arguments, dict) or set(arguments)-{'prompt', 'project_id', 'module_ids',
                    'template', 'model_selection', 'allow_module_reads', 'allow_action_drafts'}:
                raise ValueError('Tham số tạo tác vụ ngoài profile')
            if arguments.get('project_id', '') not in document['project_ids']:
                raise PermissionError('Dự án ngoài grant')
            profile = document.get('task_profile') or {}
            if any(arguments.get(flag) and not profile.get(key) for flag, key in (
                    ('allow_module_reads', 'module_reads'), ('allow_action_drafts', 'module_drafts'))):
                raise PermissionError('Chưa cấp công cụ mô-đun trong profile')
            return
        if name in ('cong_viec.tiep_tuc', 'cong_viec.dung'):
            expected = {'id', 'text'} if name == 'cong_viec.tiep_tuc' else {'id'}
            if not isinstance(arguments, dict) or set(arguments) != expected:
                raise ValueError('Tham số tác vụ không hợp lệ')
            if not isinstance(arguments['id'], str) or not re.fullmatch(r'[a-f0-9]{24}', arguments['id']):
                raise ValueError('Mã tác vụ không hợp lệ')
            row = db.execute('SELECT document FROM cong_viec_tasks WHERE id=?', (arguments['id'],)).fetchone()
            if not row:
                raise PermissionError('Không có tác vụ trong phạm vi')
            self.restore_task(actor, json.loads(row[0]), db)
            return
        if not isinstance(arguments, dict) or set(arguments) != ({'id'} if name == 'cong_viec.chi_tiet' else set()):
            raise ValueError('Tham số công cụ không hợp lệ')
        if name == 'cong_viec.chi_tiet':
            identifier = arguments['id']
            if not isinstance(identifier, str) or not re.fullmatch(r'[a-f0-9]{24}', identifier):
                raise ValueError('Mã tác vụ không hợp lệ')
            row = db.execute('''SELECT t.owner,t.document,s.unit_id FROM cong_viec_tasks t
                JOIN cong_viec_units s ON s.task_id=t.id WHERE t.id=?''', (identifier,)).fetchone()
            if (not row or row['owner'] != actor['id'] or row['unit_id'] != document['unit_id']
                    or json.loads(row['document']).get('project_id', '') not in document['project_ids']):
                raise PermissionError('Tác vụ ngoài phạm vi ủy quyền')

    def authorize_call(self, actor, name, arguments):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            document = self._require(actor, db)
            self._arguments(db, actor, document, name, arguments)

    def filter_result(self, actor, name, arguments, response):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            document = self._require(actor, db)
            self._arguments(db, actor, document, name, arguments)
        if response.get('ok'):
            value = response['ket_qua']
            if name == 'du_an.danh_sach':
                value = {**value, 'projects': [row for row in value['projects'] if row['id'] in document['project_ids']]}
            if name == 'cong_viec.danh_sach':
                value = {**value, 'tasks': [row for row in value['tasks'] if row.get('project_id', '') in document['project_ids']]}
            response = {**response, 'ket_qua': value}
        self.kho.su_kien(actor['id'], 'goi-mcp-uy-quyen-don-vi', document['id']+':'+name)
        return response

    def call(self, actor, name, arguments):
        self.authorize_call(actor, name, arguments)
        response = self.core.goi(actor, name, arguments)
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            self._require(actor, db)
        return response
