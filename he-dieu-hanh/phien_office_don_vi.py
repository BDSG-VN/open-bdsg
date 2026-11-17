"""Tham chiếu quyền của phiên Office, chỉ đọc/ghi trong giao dịch caller."""
import json


class PhienOfficeDonVi:
    def __init__(self, office):
        self.office=office
        self.units=office.projects.units
        if self.units is not None:
            with office.kho.ket_noi() as db:
                db.execute('''CREATE TABLE IF NOT EXISTS office_editor_scopes(
                    key TEXT NOT NULL,actor TEXT NOT NULL,unit_ref TEXT NOT NULL,
                    project_ref TEXT NOT NULL,PRIMARY KEY(key,actor))''')

    def reference(self, actor, project_id, db):
        if self.units is None:return None
        if actor.get('mcp_delegation') is not None:
            raise PermissionError('MCP chưa được cấp phiên soạn thảo')
        self.office.projects.authorize(actor,project_id,write=True,db=db)
        return {'unit':self.units.reference(actor,db),
                'project':self.office.projects.authorization_reference(actor,project_id,db)}

    def remember(self, key, actor, project_id, db):
        ref=self.reference(actor,project_id,db)
        if ref is None:return
        db.execute('INSERT INTO office_editor_scopes VALUES(?,?,?,?)',
                   (key,actor['id'],json.dumps(ref['unit']),json.dumps(ref['project'])))

    def actors(self, key, db):
        rows=db.execute('SELECT * FROM office_editor_scopes WHERE key=?',(key,)).fetchall()
        if not rows:raise PermissionError('Phiên không có tham chiếu đơn vị')
        actors={}
        # Một participant cũ còn trong engine không được mượn callback của
        # participant hợp lệ khác để lưu sửa đổi sau khi đã mất quyền.
        for row in rows:
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
