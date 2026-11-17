"""Tham chiếu quyền của phiên Office, chỉ đọc/ghi trong giao dịch caller."""
import json
import hashlib
import os
import secrets
import stat


class PhienOfficeDonVi:
    def __init__(self, office):
        self.office=office
        self.units=office.projects.units
        if self.units is not None:
            with office.kho.ket_noi() as db:
                # Các instance cùng kho tuần tự hóa tạo tệp và nâng schema.
                db.execute('BEGIN IMMEDIATE')
                self._epoch=self._load_epoch()
                db.execute('''CREATE TABLE IF NOT EXISTS office_editor_scopes(
                    key TEXT NOT NULL,actor TEXT NOT NULL,unit_ref TEXT NOT NULL,
                    project_ref TEXT NOT NULL,issuer_epoch TEXT NOT NULL,
                    PRIMARY KEY(key,actor))''')
                if 'issuer_epoch' not in {row[1] for row in db.execute('PRAGMA table_info(office_editor_scopes)')}:
                    # Không gán epoch mới cho phiên cũ thiếu bằng chứng nguồn.
                    db.execute("ALTER TABLE office_editor_scopes ADD COLUMN issuer_epoch TEXT NOT NULL DEFAULT ''")

    def _load_epoch(self,create=True):
        # Cố ý ngoài snapshot DATA_FILES/ALLOWED, như epoch MCP đầu vào.
        path=self.office.kho.root/'office-editor-epoch'
        if create:
            try:
                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd,'wb') as stream:
                    stream.write(secrets.token_bytes(32));stream.flush();os.fsync(stream.fileno())
        try:
            info=path.lstat()
        except OSError:
            raise PermissionError('Không đọc được thế hệ phiên Office') from None
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1
                or (os.name!='nt' and stat.S_IMODE(info.st_mode)&0o077)):
            raise PermissionError('Thế hệ phiên Office phải là tệp riêng của kho')
        try:
            fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
        except OSError:
            raise PermissionError('Không đọc được thế hệ phiên Office') from None
        with os.fdopen(fd,'rb') as stream:
            actual=os.fstat(stream.fileno())
            if (actual.st_dev,actual.st_ino)!=(info.st_dev,info.st_ino):
                raise PermissionError('Tệp thế hệ Office đã thay đổi')
            raw=stream.read(33)
        if len(raw)!=32:
            raise PermissionError('Thế hệ Office không hợp lệ; không tự ghi đè')
        return hashlib.sha256(raw).hexdigest()

    def reference(self, actor, project_id, db):
        if self.units is None:return None
        if self._load_epoch(create=False)!=self._epoch:
            raise PermissionError('Thế hệ phiên Office đã thay đổi')
        if actor.get('mcp_delegation') is not None:
            raise PermissionError('MCP chưa được cấp phiên soạn thảo')
        self.office.projects.authorize(actor,project_id,write=True,db=db)
        return {'unit':self.units.reference(actor,db),
                'project':self.office.projects.authorization_reference(actor,project_id,db)}

    def remember(self, key, actor, project_id, db):
        ref=self.reference(actor,project_id,db)
        if ref is None:return
        db.execute('''INSERT INTO office_editor_scopes
            (key,actor,unit_ref,project_ref,issuer_epoch) VALUES(?,?,?,?,?)''',
                   (key,actor['id'],json.dumps(ref['unit']),json.dumps(ref['project']),self._epoch))

    def actors(self, key, db):
        if self._load_epoch(create=False)!=self._epoch:
            raise PermissionError('Thế hệ phiên Office đã thay đổi')
        rows=db.execute('SELECT * FROM office_editor_scopes WHERE key=?',(key,)).fetchall()
        if not rows:raise PermissionError('Phiên không có tham chiếu đơn vị')
        actors={}
        # Một participant cũ còn trong engine không được mượn callback của
        # participant hợp lệ khác để lưu sửa đổi sau khi đã mất quyền.
        for row in rows:
            if row['issuer_epoch']!=self._epoch:
                raise PermissionError('Phiên Office thuộc thế hệ trước phục hồi')
            unit_ref,project_ref=json.loads(row['unit_ref']),json.loads(row['project_ref'])
            actor=self.units.restore(unit_ref,db)
            if actor['id']!=row['actor'] or self.reference(actor,project_ref['project_id'],db)!={'unit':unit_ref,'project':project_ref}:
                raise PermissionError('Quyền của phiên soạn thảo đã thay đổi')
            actors[actor['id']]=actor
        return actors

    def actor(self,key,identity,db,current=None):
        if current is not None and current.get('mcp_delegation') is not None:
            raise PermissionError('MCP chưa được cấp phiên soạn thảo')
        actor=self.actors(key,db).get(identity)
        if actor is None:raise PermissionError('Không thuộc phiên soạn thảo')
        if current is not None and self.units.reference(current,db)!=self.units.reference(actor,db):
            raise PermissionError('Phiên thuộc phạm vi đơn vị khác')
        return actor
