"""Phiên Docs có lưu bền: khóa soạn thảo, callback ký, quét và CAS phiên bản.

Người cùng quyền dự án dùng chung phiên. Snapshot force-save chỉ báo
thành công sau commit, callback phiên cũ không được ghi đè phiên mới.
"""

import hashlib
import http.client
import json
import os
import re
import secrets
import time
from urllib.parse import unquote, urlencode, urlsplit

from chu_ky_office import sign, verify
from kiem_tep_office import kiem_tep
from van_phong import LoiXungDotVanPhong
from phien_office_don_vi import PhienOfficeDonVi
from duong_engine_office import phan_loai


class SoanThaoOffice:
    def __init__(self, office, origin):
        self.office, self.kho, self.origin = office, office.kho, origin
        self.secret = os.environ.get("BDSG_OFFICE_JWT_SECRET", "")
        port = os.environ.get('BDSG_OFFICE_INTERNAL_PORT','8088')
        if (not port.isascii() or not port.isdecimal() or len(port)>5
                or not 1<=int(port)<=65535):
            raise ValueError('Cổng engine Office nội bộ không hợp lệ')
        # Cấu hình vận hành được chụp khi khởi tạo; client không chọn host/cổng.
        self.engine_port = int(port)
        self.prefix = "/office-docs/"
        self.scopes = PhienOfficeDonVi(office)
        with self.kho.ket_noi() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS office_editors(
                    key TEXT PRIMARY KEY,file_id TEXT NOT NULL,actor TEXT NOT NULL,
                    role TEXT NOT NULL,revision INTEGER NOT NULL,cap TEXT NOT NULL,
                    expires REAL NOT NULL,state TEXT NOT NULL,pending TEXT,
                    pending_at REAL,last_saved REAL,sha256 TEXT);
                CREATE INDEX IF NOT EXISTS office_editor_file ON office_editors(file_id,state);
                CREATE TABLE IF NOT EXISTS office_editor_members(
                    key TEXT NOT NULL,actor TEXT NOT NULL,role TEXT NOT NULL,
                    PRIMARY KEY(key,actor));
                CREATE TABLE IF NOT EXISTS office_editor_requests(
                    id TEXT PRIMARY KEY,key TEXT NOT NULL,actor TEXT NOT NULL,role TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS office_editor_callbacks(
                    key TEXT NOT NULL,status INTEGER NOT NULL,request TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,created REAL NOT NULL,
                    PRIMARY KEY(key,status,request));
                CREATE TABLE IF NOT EXISTS office_editor_failures(
                    key TEXT PRIMARY KEY,request TEXT NOT NULL,created REAL NOT NULL);
            """)
            if self.scopes.units is not None:
                db.execute('''CREATE TABLE IF NOT EXISTS office_editor_commands(
                    id TEXT PRIMARY KEY REFERENCES office_editor_requests(id),
                    state TEXT NOT NULL,updated REAL NOT NULL)''')
                db.execute('''CREATE TABLE IF NOT EXISTS office_editor_intents(
                    key TEXT NOT NULL,actor TEXT NOT NULL,intent TEXT NOT NULL,
                    request TEXT NOT NULL REFERENCES office_editor_requests(id),
                    PRIMARY KEY(key,actor,intent))''')
                db.execute('''CREATE TABLE IF NOT EXISTS office_editor_abandons(
                    actor TEXT NOT NULL,unit_id TEXT NOT NULL,intent TEXT NOT NULL,
                    file_id TEXT NOT NULL,expected_key TEXT NOT NULL,
                    unit_ref TEXT NOT NULL,project_ref TEXT NOT NULL,issuer_epoch TEXT NOT NULL,
                    revoked_sessions INTEGER NOT NULL,
                    PRIMARY KEY(actor,unit_id,intent))''')

    def status(self):
        return {
            "state": "da-cau-hinh" if len(self.secret) >= 32 else "chua-cau-hinh",
            "edition": "ONLYOFFICE Docs Community",
            "mobile_editing": False,
        }

    def create(self, actor, args):
        from mau_office import create

        name = self.office._name(args.get("name"))
        raw = create(name.rsplit(".", 1)[-1].lower())
        return self.office.create_bytes(
            actor, args.get("project_id"), name, raw, args.get("request_key")
        )

    def _row(self, db, key):
        row = db.execute("SELECT * FROM office_editors WHERE key=?", (key,)).fetchone()
        if not row or row["expires"] < time.time() or row["state"] != "active":
            raise PermissionError("Phiên soạn thảo đã hết hiệu lực")
        if self.scopes.units is not None:
            self.scopes.actors(key,db)
        return dict(row)

    def _actor(self, session, db):
        if self.scopes.units is not None:
            return self.scopes.actor(session['key'],session['actor'],db)
        return {"id": session["actor"], "role": session["role"]}

    def open(self, actor, args):
        if self.status()["state"] != "da-cau-hinh":
            raise ValueError("Chưa cấu hình bộ soạn thảo")
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            file = self.office._file(actor, args.get("id"), db, True)
            reference = self.scopes.reference(actor,file['project_id'],db)
            if file["trashed"]:
                raise ValueError("Tệp đang trong thùng rác")
            extension = file["name"].rsplit(".", 1)[-1].lower()
            kind = {"docx": "word", "xlsx": "cell", "pptx": "slide"}.get(extension)
            if not kind:
                raise ValueError("Định dạng chưa có bộ soạn thảo")
            raw = db.execute(
                "SELECT content FROM office_versions WHERE file_id=? AND version=?",
                (file["id"], file["version"]),
            ).fetchone()[0]
        kiem_tep(file["name"], raw)
        checked = self.office.scanner.scan(raw)
        if checked["virus_state"] != "khong-phat-hien":
            raise ValueError("Cần quét virus trước khi mở bộ soạn thảo")
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self.office._file(actor, file["id"], db, True)
            self.office._check_revision(current, file["revision"])
            if self.scopes.reference(actor,file['project_id'],db)!=reference:
                raise PermissionError('Quyền thay đổi trong lúc kiểm tệp Office')
            sql="SELECT * FROM office_editors e WHERE file_id=? AND state='active' AND expires>?"
            params=[file['id'],time.time()]
            if reference is not None:
                sql+=" AND EXISTS(SELECT 1 FROM office_editor_scopes s WHERE s.key=e.key AND json_extract(s.unit_ref,'$.unit_id')=?)"
                params.append(reference['unit']['unit_id'])
            old=db.execute(sql,params).fetchone()
            if old and reference is not None:
                try:self._row(db,old['key'])
                except (PermissionError,ValueError):
                    db.execute("UPDATE office_editors SET state='revoked',pending=NULL WHERE key=?",(old['key'],))
                    old=None
            if old:
                session = dict(old)
                if old["revision"] != file["revision"]:
                    raise LoiXungDotVanPhong("Tệp đang có phiên chỉnh sửa khác")
            else:
                session = {
                    "key": "bdsg-" + secrets.token_hex(16),
                    "file_id": file["id"],
                    "actor": actor["id"],
                    "role": actor["role"],
                    "revision": file["revision"],
                    "cap": secrets.token_urlsafe(32),
                    "expires": time.time() + 12 * 3600,
                    "state": "active",
                    "pending": None,
                    "pending_at": None,
                    "last_saved": None,
                    "sha256": checked["sha256"],
                }
                db.execute(
                    "INSERT INTO office_editors VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    tuple(session.values()),
                )
            db.execute(
                "INSERT INTO office_editor_members VALUES (?,?,?) ON CONFLICT(key,actor) DO UPDATE SET role=excluded.role",
                (session["key"], actor["id"], actor["role"]),
            )
            if reference is not None and not db.execute('SELECT 1 FROM office_editor_scopes WHERE key=? AND actor=?',(session['key'],actor['id'])).fetchone():
                self.scopes.remember(session['key'],actor,file['project_id'],db)
            pending_save=None
            if reference is not None and session['pending']:
                intent=db.execute('SELECT intent FROM office_editor_intents WHERE key=? AND actor=? AND request=?',
                                  (session['key'],actor['id'],session['pending'])).fetchone()
                if intent is not None:
                    pending_save={'request_key':intent['intent'],'request_id':session['pending']}
        url = (
            self.origin
            + "/api/office-source?"
            + urlencode({"key": session["key"], "cap": session["cap"]})
        )
        config = {
            "documentType": kind,
            "type": "desktop",
            "width": "100%",
            "height": "100%",
            "document": {
                "fileType": extension,
                "key": session["key"],
                "title": file["name"],
                "url": url,
                "permissions": {"edit": True, "download": False, "print": False},
            },
            "editorConfig": {
                "mode": "edit",
                "lang": "vi",
                "callbackUrl": self.origin + "/api/office-callback",
                "user": {"id": actor["id"], "name": actor.get("name", actor["id"])},
                "coEditing": {"mode": "fast", "change": False},
            },
        }
        config["token"] = sign(
            {**config, "exp": int(session["expires"]), "iat": int(time.time())},
            self.secret,
        )
        return {
            "key": session["key"],
            "config": config,
            "api_url": self.prefix + "web-apps/apps/api/documents/api.js",
            "save_protocol": "request-ledger-v1" if self.scopes.units is not None else "legacy",
            "save_intents": self.scopes.units is not None,
            "pending_save": pending_save,
        }

    def source(self, query, authorization):
        if self.scopes.units is not None and (
                not isinstance(query,dict) or set(query)!={'key','cap'}
                or any(not isinstance(values,list) or len(values)!=1
                       or not isinstance(values[0],str) or not values[0]
                       for values in query.values())):
            raise ValueError('Tham số nguồn Office không hợp lệ')
        key, cap = query.get("key", [""])[0], query.get("cap", [""])[0]
        url = self.origin + "/api/office-source?" + urlencode({"key": key, "cap": cap})
        signed = verify(authorization.removeprefix("Bearer "), self.secret, "download")
        if signed.get("url") != url:
            raise PermissionError("Nguồn Office không khớp chữ ký")
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            session = self._row(db, key)
            if not secrets.compare_digest(cap, session["cap"]):
                raise PermissionError("Không có quyền tải nguồn")
            file = self.office._file(self._actor(session,db), session["file_id"], db, True)
            self.office._check_revision(file, session["revision"])
            raw = db.execute(
                "SELECT content FROM office_versions WHERE file_id=? AND version=?",
                (file["id"], file["version"]),
            ).fetchone()[0]
            return raw

    def engine_access(self, actor, path):
        if self.scopes.units is not None:
            return self._scoped_engine_access(actor,path)
        if not actor:
            return False
        if len(path) > 8192:
            return False
        # Cache và WebSocket mang key; tài nguyên tĩnh vẫn yêu cầu phiên BDSG.
        path = unquote(urlsplit(path).path)
        if "%" in path or ".." in path:
            return False
        matches = re.findall(
            r"(?:^|/)(bdsg-[a-f0-9]{32})(?:_[A-Za-z0-9.-]+)?(?:/|$)", path
        )
        if ("/cache/" in path or "/doc/" in path) and not matches:
            return False
        for key in matches:
            try:
                with self.kho.ket_noi() as db:
                    db.execute('BEGIN')
                    session = self._row(db, key)
                    if self.scopes.units is not None:
                        self.scopes.actor(key,actor['id'],db,current=actor)
                    self.office._file(actor, session["file_id"], db)
            except (ValueError, PermissionError):
                return False
        return True

    def _scoped_engine_access(self,actor,path):
        if not isinstance(actor,dict) or 'mcp_delegation' in actor:
            return False
        try:
            kind,key=phan_loai(path)
            with self.kho.ket_noi() as db:
                db.execute('BEGIN')
                # Mã giao diện là tài nguyên chung, không phải quyền tài liệu.
                # Dùng đúng kiểm danh tính còn hiệu lực của đơn vị, không tự
                # suy quyền nội dung từ vai root hoặc từ cookie toàn cổng.
                self.scopes.units._identity(db,actor)
                if kind=='static':return True
                session=self._row(db,key)
                current=actor if 'unit_scope' in actor else None
                scoped=self.scopes.actor(key,actor['id'],db,current=current)
                self.office._file(scoped,session['file_id'],db,True)
                return True
        except (ValueError,PermissionError,OSError):
            return False

    def save(self, actor, args):
        if self.scopes.units is not None:
            return self._save_scoped(actor,args)
        if 'request_key' in args:
            raise ValueError('Ý định lưu cần phạm vi đơn vị')
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            session = self._row(db, args.get("key"))
            if self.scopes.units is not None:
                self.scopes.actor(session['key'],actor['id'],db,current=actor)
            file = self.office._file(actor, session["file_id"], db, True)
            if not db.execute(
                "SELECT 1 FROM office_editor_members WHERE key=? AND actor=?",
                (session["key"], actor["id"]),
            ).fetchone():
                raise PermissionError("Phiên thuộc người khác")
            self.office._check_revision(file, session["revision"])
            if session["pending"] and session["pending_at"] > time.time() - 120:
                return {"state": "dang-luu", "request_id": session["pending"]}
            request = secrets.token_hex(16)
            db.execute(
                "DELETE FROM office_editor_failures WHERE key=?", (session["key"],)
            )
            db.execute(
                "UPDATE office_editors SET pending=?,pending_at=? WHERE key=?",
                (request, time.time(), session["key"]),
            )
            db.execute(
                "INSERT INTO office_editor_requests VALUES (?,?,?,?)",
                (request, session["key"], actor["id"], actor["role"]),
            )
        payload = {
            "c": "forcesave",
            "key": session["key"],
            "userdata": request,
            "operation": "command",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        }
        if self._command(payload)==4:
            with self.kho.ket_noi() as db:
                db.execute("UPDATE office_editors SET pending=NULL WHERE key=? AND pending=?",
                           (session['key'],request))
            return {'state':'khong-co-thay-doi'}
        return {'state':'dang-luu','request_id':request}

    def _command(self,payload):
        connection=http.client.HTTPConnection('127.0.0.1',self.engine_port,timeout=10)
        try:
            connection.request('POST','/command',json.dumps({'token':sign(payload,self.secret)}),
                               {'Content-Type':'application/json'})
            response=connection.getresponse()
            value=json.loads(response.read(8192))
            if response.status!=200 or value.get('error') not in (0,4):
                raise ValueError('Bộ soạn thảo chưa nhận lệnh lưu')
            return value['error']
        finally:
            connection.close()

    def _save_session(self,db,actor,key):
        session=self._row(db,key)
        if self.scopes.units is not None:
            self.scopes.actor(key,actor['id'],db,current=actor)
        file=self.office._file(actor,session['file_id'],db,True)
        self.office._check_revision(file,session['revision'])
        return session

    def _command_record(self,db,key,request=None):
        sql='''SELECT r.id,r.actor,COALESCE(c.state,'unknown') AS state,c.updated
            FROM office_editor_requests r LEFT JOIN office_editor_commands c
            ON r.id=c.id WHERE r.key=?'''
        values=[key]
        if request is not None:
            if not isinstance(request,str) or not 1<=len(request)<=128:
                raise ValueError('Mã lệnh lưu không hợp lệ')
            sql+=' AND r.id=?';values.append(request)
        row=db.execute(sql+' ORDER BY c.updated DESC,r.id DESC LIMIT 1',values).fetchone()
        if request is not None and row is None:
            raise PermissionError('Lệnh lưu không thuộc phiên này')
        return row

    def _intent_key(self,args):
        if 'request_key' not in args:return None
        intent=args['request_key']
        if (self.scopes.units is None or not isinstance(intent,str)
                or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}',intent)):
            raise ValueError('Mã ý định lưu không hợp lệ')
        return intent

    def _intent_command(self,db,actor,key,intent):
        mapping=db.execute('SELECT request FROM office_editor_intents WHERE key=? AND actor=? AND intent=?',
                           (key,actor['id'],intent)).fetchone()
        if mapping is None:return None
        command=self._command_record(db,key,mapping['request'])
        if command['actor']!=actor['id']:
            raise PermissionError('Ý định lưu không thuộc người gọi')
        return command

    def _settle_command(self,db,session,state):
        if self.scopes.units is None or not session['pending']:return
        db.execute('''INSERT INTO office_editor_commands(id,state,updated)
            SELECT id,?,? FROM office_editor_requests WHERE id=? AND key=?
            ON CONFLICT(id) DO UPDATE SET state=excluded.state,updated=excluded.updated
            WHERE office_editor_commands.state NOT IN ('committed','unchanged','superseded','abandoned')''',
            (state,time.time(),session['pending'],session['key']))

    def _save_receipt(self,db,key,request):
        if db.execute('SELECT 1 FROM office_editor_callbacks WHERE key=? AND status=6 AND request=?',(key,request)).fetchone():
            return {'state':'da-luu','request_id':request}
        command=self._command_record(db,key,request)
        if command['state']=='committed':
            return {'state':'da-luu','request_id':request}
        if command['state']=='failed':
            return {'state':'loi-luu','request_id':request}
        return None

    def _result_session(self,db,actor,key):
        # Receipt vẫn đọc được sau callback đóng key, nhưng không được dùng
        # receipt để bỏ kiểm quyền của participant hoặc phạm vi hiện tại.
        session=db.execute('SELECT * FROM office_editors WHERE key=?',(key,)).fetchone()
        if session is None:raise PermissionError('Không có quyền xem kết quả lưu')
        self.scopes.actor(key,actor['id'],db,current=actor)
        self.office._file(actor,session['file_id'],db,True)
        return session

    def _save_scoped(self,actor,args):
        key=args.get('key')
        intent=self._intent_key(args)
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            if intent is not None:
                self._result_session(db,actor,key)
                known=self._intent_command(db,actor,key,intent)
                if known is not None:
                    states={'committed':'da-luu','unchanged':'khong-co-thay-doi',
                            'failed':'loi-luu','abandoned':'da-bo-phien',
                            'superseded':'da-thay-the','accepted':'dang-luu'}
                    return {'state':states.get(known['state'],'chua-ro-ket-qua'),'request_id':known['id']}
            session=self._save_session(db,actor,key)
            if session['pending']:
                if intent is not None:
                    raise LoiXungDotVanPhong('Phiên còn lệnh khác đang chờ; cần kiểm tra trước khi lưu tiếp')
                command=db.execute('SELECT state FROM office_editor_commands WHERE id=?',(session['pending'],)).fetchone()
                state='dang-luu' if command and command['state']=='accepted' else 'chua-ro-ket-qua'
                return {'state':state,'request_id':session['pending']}
            request=secrets.token_hex(16)
            db.execute('DELETE FROM office_editor_failures WHERE key=?',(key,))
            db.execute('UPDATE office_editors SET pending=?,pending_at=? WHERE key=?',(request,time.time(),key))
            db.execute('INSERT INTO office_editor_requests VALUES(?,?,?,?)',(request,key,actor['id'],actor['role']))
            db.execute('INSERT INTO office_editor_commands VALUES(?,?,?)',(request,'prepared',time.time()))
            if intent is not None:
                db.execute('INSERT INTO office_editor_intents VALUES(?,?,?,?)',(key,actor['id'],intent,request))
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            latest=self._save_session(db,actor,key)
            if latest['pending']!=request:
                raise LoiXungDotVanPhong('Lệnh lưu đã bị thay thế trước khi gửi')
            if db.execute("UPDATE office_editor_commands SET state='dispatched',updated=? WHERE id=? AND state='prepared'",(time.time(),request)).rowcount!=1:
                raise LoiXungDotVanPhong('Trạng thái lệnh lưu đã thay đổi trước khi gửi')
        payload={'c':'forcesave','key':key,'userdata':request,'operation':'command',
                 'iat':int(time.time()),'exp':int(time.time())+60}
        try:
            code=self._command(payload)
            if type(code) is not int or code not in (0,4):
                raise ValueError('Phản hồi lệnh lưu không hợp lệ')
        except Exception:
            # Kể cả engine đã nhận lệnh, callback có thể tới sau timeout.
            # Không bỏ pending hoặc phát lại khi chưa có biên nhận xác định.
            with self.kho.ket_noi() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute("UPDATE office_editor_commands SET state='unknown',updated=? WHERE id=? AND state='dispatched'",(time.time(),request))
                self._result_session(db,actor,key)
                receipt=self._save_receipt(db,key,request)
                if receipt:return receipt
            return {'state':'chua-ro-ket-qua','request_id':request}
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            self._result_session(db,actor,key)
            receipt=self._save_receipt(db,key,request)
            if receipt:return receipt
            latest=self._save_session(db,actor,key)
            if latest['pending']!=request:
                raise LoiXungDotVanPhong('Lệnh lưu đã có kết quả khác; cần đọc tiến trình')
            if code==4:
                db.execute('UPDATE office_editors SET pending=NULL WHERE key=? AND pending=?',(key,request))
            db.execute('UPDATE office_editor_commands SET state=?,updated=? WHERE id=?',
                       ('unchanged' if code==4 else 'accepted',time.time(),request))
        return {'state':'khong-co-thay-doi' if code==4 else 'dang-luu','request_id':request}

    def reconcile_save(self,actor,args):
        if self.scopes.units is None:
            raise PermissionError('Đối soát này cần phạm vi đơn vị')
        if (not isinstance(args,dict) or set(args)-{'key','request_id','acknowledge_unsaved_changes'}
                or args.get('acknowledge_unsaved_changes') is not True):
            raise ValueError('Cần xác nhận có thể mất thay đổi chưa lưu trước khi bỏ phiên')
        key,request=args.get('key'),args.get('request_id')
        if not isinstance(request,str) or not request:
            raise ValueError('Cần mã lệnh lưu cụ thể')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            session=db.execute('SELECT * FROM office_editors WHERE key=?',(key,)).fetchone()
            if session is None:raise PermissionError('Không có quyền đối soát phiên')
            self.scopes.actor(key,actor['id'],db,current=actor)
            self.office._file(actor,session['file_id'],db,True)
            command=self._command_record(db,key,request)
            if session['state']=='revoked' and command['state']=='abandoned':
                return {'state':'da-bo-phien','request_id':request}
            if session['state']!='active' or session['pending']!=request:
                raise LoiXungDotVanPhong('Lệnh lưu không còn là lệnh đang chờ của phiên')
            self._settle_command(db,session,'abandoned')
            db.execute("UPDATE office_editors SET state='revoked',pending=NULL WHERE key=?",(key,))
            self.office._audit(db,actor,'office-editor-abandon',key)
        return {'state':'da-bo-phien','request_id':request}

    def abandon_sessions(self,actor,args):
        if self.scopes.units is None:
            raise PermissionError('Bỏ phiên phục hồi cần phạm vi đơn vị')
        required={'file_id','key','request_key','acknowledge_unsaved_changes','acknowledge_shared_session'}
        if (not isinstance(args,dict) or set(args)!=required
                or args['acknowledge_unsaved_changes'] is not True
                or args['acknowledge_shared_session'] is not True):
            raise ValueError('Cần xác nhận mất thay đổi và ảnh hưởng phiên cùng sửa')
        file_id,key=args['file_id'],args['key']
        if (not isinstance(file_id,str) or not re.fullmatch(r'[a-f0-9]{24}',file_id)
                or not isinstance(key,str) or not re.fullmatch(r'bdsg-[a-f0-9]{32}',key)):
            raise ValueError('Cần đúng tài liệu và phiên từng tham gia')
        intent=self._intent_key(args)
        def result(count):
            return {'state':'da-bo-phien','file_id':file_id,'key':key,
                    'request_key':intent,'revoked_sessions':count}
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            file=self.office._file(actor,file_id,db,True)
            ref=self.scopes.reference(actor,file['project_id'],db)
            unit_id=ref['unit']['unit_id']
            previous=db.execute('''SELECT * FROM office_editor_abandons
                WHERE actor=? AND unit_id=? AND intent=?''',(actor['id'],unit_id,intent)).fetchone()
            if previous is not None:
                if previous['file_id']!=file_id or previous['expected_key']!=key:
                    raise LoiXungDotVanPhong('Mã bỏ phiên đã dùng cho yêu cầu khác')
                if (previous['issuer_epoch']!=self.scopes._epoch
                        or json.loads(previous['unit_ref'])!=ref['unit']
                        or json.loads(previous['project_ref'])!=ref['project']):
                    raise PermissionError('Quyền hoặc thế hệ của biên nhận bỏ phiên đã thay đổi')
                return result(previous['revoked_sessions'])
            # Thu hồi là thao tác giảm quyền: kiểm quyền file hiện tại và lịch
            # sử tham gia cùng đơn vị, không khôi phục quyền dùng lease cũ.
            rows=db.execute('''SELECT e.* FROM office_editors e
                JOIN office_editor_members m ON m.key=e.key AND m.actor=?
                JOIN office_editor_scopes s ON s.key=e.key AND s.actor=m.actor
                WHERE e.file_id=? AND json_extract(s.unit_ref,'$.unit_id')=?''',
                (actor['id'],file_id,unit_id)).fetchall()
            if not any(row['key']==key for row in rows):
                raise PermissionError('Phiên không thuộc tài liệu và đơn vị từng tham gia')
            for row in rows:
                if row['pending']:
                    command=db.execute('SELECT actor FROM office_editor_requests WHERE id=? AND key=?',
                                       (row['pending'],row['key'])).fetchone()
                    if command is None or command['actor']!=actor['id']:
                        raise LoiXungDotVanPhong('Có lần lưu của người cùng sửa; chưa thể bỏ phiên này')
            targets=[row for row in rows if row['state']!='revoked']
            for row in targets:
                self._settle_command(db,row,'abandoned')
                db.execute("UPDATE office_editors SET state='revoked',pending=NULL WHERE key=?",(row['key'],))
            db.execute('INSERT INTO office_editor_abandons VALUES(?,?,?,?,?,?,?,?,?)',
                (actor['id'],unit_id,intent,file_id,key,json.dumps(ref['unit']),
                 json.dumps(ref['project']),self.scopes._epoch,len(targets)))
            self.office._audit(db,actor,'office-editor-abandon-sessions',file_id)
            return result(len(targets))

    def progress(self, actor, args):
        intent=self._intent_key(args)
        if intent is not None and 'request_id' in args:
            raise ValueError('Chỉ chọn mã ý định hoặc mã lệnh để kiểm tra lưu')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            row = db.execute(
                "SELECT * FROM office_editors WHERE key=?", (args.get("key"),)
            ).fetchone()
            if (
                not row
                or not db.execute(
                    "SELECT 1 FROM office_editor_members WHERE key=? AND actor=?",
                    (args.get("key"), actor["id"]),
                ).fetchone()
            ):
                raise PermissionError("Không có quyền xem phiên")
            file = self.office._file(actor, row["file_id"], db)
            if self.scopes.units is not None:
                self.scopes.actor(row['key'],actor['id'],db,current=actor)
            result = {
                "state": row["state"],
                "pending": bool(row["pending"]),
                "pending_at": row["pending_at"],
                "last_saved": row["last_saved"],
                "revision": file["revision"],
                "save_error": bool(
                    db.execute(
                        "SELECT 1 FROM office_editor_failures WHERE key=?",
                        (args.get("key"),),
                    ).fetchone()
                ),
            }
            if self.scopes.units is not None:
                request=args['request_id'] if 'request_id' in args else row['pending']
                command=(self._intent_command(db,actor,row['key'],intent) if intent is not None
                         else self._command_record(db,row['key'],request))
                result.update(request_id=command['id'] if command else (None if intent is not None else row['pending']),
                    pending_request_id=row['pending'],
                    command_state=command['state'] if command else ('not-started' if intent is not None else 'unknown' if row['pending'] else None))
                if intent is not None:result['request_key']=intent
                result['save_error']=result['save_error'] or bool(command and command['state']=='failed')
            return result

    def _fetch(self, url, key):
        parsed = urlsplit(url)
        own = urlsplit(self.origin)
        if (
            parsed.scheme == "https"
            and parsed.netloc == own.netloc
            and parsed.path.startswith(self.prefix)
        ):
            path = parsed.path[len(self.prefix) - 1 :]
        elif parsed.scheme == "http" and parsed.netloc == f"127.0.0.1:{self.engine_port}":
            path = parsed.path
        else:
            raise ValueError("Nguồn kết quả không được phép")
        if (
            parsed.fragment
            or ".." in path
            or not re.fullmatch(
                r"/cache/files/(?:data/)?"
                + re.escape(key)
                + r"(?:_[A-Za-z0-9.-]+)?/[A-Za-z0-9_./-]+",
                path,
            )
        ):
            raise ValueError("Đường dẫn kết quả không hợp lệ")
        connection = http.client.HTTPConnection("127.0.0.1", self.engine_port, timeout=12)
        try:
            connection.request(
                "GET", path + ("?" + parsed.query if parsed.query else "")
            )
            response = connection.getresponse()
            raw = response.read(self.office.MAX_FILE_BYTES + 1)
            if response.status != 200 or len(raw) > self.office.MAX_FILE_BYTES:
                raise ValueError("Không tải được kết quả trong giới hạn")
            return raw
        finally:
            connection.close()

    def _callback_receipt(self,db,key,status,request,fingerprint):
        row=db.execute('SELECT fingerprint FROM office_editor_callbacks WHERE key=? AND status=? AND request=?',
                       (key,status,request)).fetchone()
        if row is None:return False
        if row['fingerprint']!=fingerprint:
            raise LoiXungDotVanPhong('Callback cùng mã nhưng khác dữ liệu')
        return True

    def callback(self, body, authorization):
        if not isinstance(body,dict):
            raise ValueError('Callback Office phải là đối tượng')
        token = body.get("token") or authorization.removeprefix("Bearer ")
        payload = verify(token, self.secret, "callback")
        key, status = payload.get("key"), payload.get("status")
        if type(status) is not int or status not in (1,2,3,4,6,7):
            raise ValueError("Trạng thái callback chưa hỗ trợ")
        # Chữ ký xác thực nguồn gửi, không thay kiểm kiểu trước SQL và IO.
        if not isinstance(key,str) or not key or len(key)>128:
            raise ValueError('Mã phiên callback không hợp lệ')
        if status==2:
            users=payload.get('users')
            if (not isinstance(users,list) or not users
                    or any(not isinstance(user,str) or not user or len(user)>128 for user in users)):
                raise ValueError('Người lưu callback không hợp lệ')
        if status in (2,6) and (not isinstance(payload.get('url'),str)
                or not payload['url'] or len(payload['url'])>8192):
            raise ValueError('Nguồn kết quả callback không hợp lệ')
        request = payload.get("userdata", "") if status in (6,7) else ""
        if not isinstance(request, str) or len(request) > 128:
            raise ValueError("Mã callback không hợp lệ")
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    k: payload.get(k)
                    for k in ("key", "status", "userdata", "url", "users")
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            if self._callback_receipt(db,key,status,request,fingerprint):return {'error':0}
            session = self._row(db, key)
            if status == 6:
                member = db.execute(
                    "SELECT actor,role FROM office_editor_requests WHERE id=? AND key=?",
                    (payload.get("userdata"), key),
                ).fetchone()
            elif status == 2:
                users = payload.get("users", [])
                member = db.execute(
                    "SELECT actor,role FROM office_editor_members WHERE key=? AND actor=?",
                    (key, users[0] if isinstance(users, list) and users else ""),
                ).fetchone()
            else:
                member = {"actor": session["actor"], "role": session["role"]}
            if not member:
                raise PermissionError("Không xác định được người lưu phiên")
            actor = (self.scopes.actor(key,member['actor'],db) if self.scopes.units is not None
                     else {"id": member["actor"], "role": member["role"]})
            file = self.office._file(actor, session["file_id"], db, True)
            self.office._check_revision(file, session["revision"])
            if status == 6 and (
                not session["pending"] or payload.get("userdata") != session["pending"]
            ):
                raise LoiXungDotVanPhong("Snapshot không thuộc lệnh lưu hiện tại")
        if status in (2, 6):
            raw = self._fetch(payload.get("url", ""), key)
            checks = kiem_tep(file["name"], raw)
            scan = self.office.scanner.scan(raw)
            if scan["virus_state"] != "khong-phat-hien":
                raise ValueError("Kết quả chưa được quét")
            with self.kho.ket_noi() as db:
                db.execute("BEGIN IMMEDIATE")
                if self._callback_receipt(db,key,status,request,fingerprint):return {'error':0}
                latest = self._row(db, key)
                current = self.office._file(actor, session["file_id"], db, True)
                self.office._check_revision(current, session["revision"])
                if (
                    latest["revision"] != session["revision"]
                    or latest["pending"] != session["pending"]
                ):
                    raise LoiXungDotVanPhong("Callback đã bị thay thế")
                if scan["sha256"] != session["sha256"]:
                    current["version"] += 1
                    self.office._version(db, current, actor, raw, scan)
                    current["revision"] += 1
                    db.execute(
                        "UPDATE office_files SET version=?,revision=?,updated=? WHERE id=?",
                        (
                            current["version"],
                            current["revision"],
                            time.time(),
                            current["id"],
                        ),
                    )
                    db.execute(
                        "UPDATE office_checks SET result=? WHERE file_id=? AND version=?",
                        (
                            json.dumps({**checks, **scan}),
                            current["id"],
                            current["version"],
                        ),
                    )
                db.execute(
                    "UPDATE office_editors SET revision=?,pending=NULL,last_saved=?,sha256=?,state=? WHERE key=?",
                    (
                        current["revision"],
                        time.time(),
                        hashlib.sha256(raw).hexdigest(),
                        "closed" if status == 2 else "active",
                        key,
                    ),
                )
                self._settle_command(db,latest,'committed')
                self.office._audit(db, actor, "office-editor-save", current["id"])
                db.execute(
                    "INSERT INTO office_editor_callbacks VALUES (?,?,?,?,?)",
                    (key, status, request, fingerprint, time.time()),
                )
        elif status == 7:
            with self.kho.ket_noi() as db:
                db.execute("BEGIN IMMEDIATE")
                if self._callback_receipt(db,key,status,request,fingerprint):return {'error':0}
                latest = self._save_session(db,actor,key)
                if latest["pending"] and payload.get("userdata") == latest["pending"]:
                    self._settle_command(db,latest,'failed')
                    db.execute(
                        "UPDATE office_editors SET pending=NULL WHERE key=? AND pending=?",
                        (key, latest["pending"]),
                    )
                    db.execute(
                        "INSERT INTO office_editor_failures VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET request=excluded.request,created=excluded.created",
                        (key, latest["pending"], time.time()),
                    )
                    db.execute('INSERT INTO office_editor_callbacks VALUES(?,?,?,?,?)',(key,status,request,fingerprint,time.time()))
        elif status == 3:
            with self.kho.ket_noi() as db:
                db.execute('BEGIN IMMEDIATE')
                if self._callback_receipt(db,key,status,request,fingerprint):return {'error':0}
                latest=self._save_session(db,actor,key)
                self._settle_command(db,latest,'failed')
                db.execute(
                    "UPDATE office_editors SET state='error',pending=NULL WHERE key=?",
                    (key,),
                )
                db.execute('INSERT INTO office_editor_callbacks VALUES(?,?,?,?,?)',(key,status,request,fingerprint,time.time()))
        elif status == 4:
            with self.kho.ket_noi() as db:
                db.execute('BEGIN IMMEDIATE')
                if self._callback_receipt(db,key,status,request,fingerprint):return {'error':0}
                latest=self._save_session(db,actor,key)
                self._settle_command(db,latest,'superseded')
                db.execute(
                    "UPDATE office_editors SET state='closed',pending=NULL WHERE key=?",
                    (key,),
                )
                db.execute('INSERT INTO office_editor_callbacks VALUES(?,?,?,?,?)',(key,status,request,fingerprint,time.time()))
        elif status != 1:
            raise ValueError("Trạng thái callback chưa hỗ trợ")
        return {"error": 0}
