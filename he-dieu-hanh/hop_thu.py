"""Hộp thư cá nhân trong đơn vị; vai quản trị không cho quyền đọc thư khác."""
import secrets
import time


class HopThu:
    def __init__(self, kho, units=None):
        self.kho, self.units = kho, units
        if units is not None:
            with kho.ket_noi() as db:
                db.execute('''CREATE TABLE IF NOT EXISTS unit_messages(
                    id TEXT PRIMARY KEY,unit_id TEXT NOT NULL REFERENCES don_vi(id),
                    sender TEXT NOT NULL,recipient TEXT NOT NULL,
                    sender_epoch INTEGER NOT NULL,recipient_epoch INTEGER NOT NULL,
                    body TEXT NOT NULL,created REAL NOT NULL)''')
                db.execute('CREATE INDEX IF NOT EXISTS unit_mail_sender ON unit_messages(unit_id,sender,sender_epoch,created)')
                db.execute('CREATE INDEX IF NOT EXISTS unit_mail_recipient ON unit_messages(unit_id,recipient,recipient_epoch,created)')

    def call(self, actor, operation, arguments):
        allowed = {'danh_sach': set(), 'doc_hop_thu': {'peer'}, 'gui_tin': {'recipient','body'}}
        if (operation not in allowed or not isinstance(arguments, dict)
                or (self.units is not None and set(arguments)-allowed[operation])):
            raise ValueError('Tham số hộp thư không hợp lệ')
        if operation == 'danh_sach':
            return {'agents': self.agents(actor)}
        if operation == 'doc_hop_thu':
            return {'messages': self.read(actor, arguments.get('peer'))}
        return self.send(actor, arguments.get('recipient'), arguments.get('body'))

    def _scope(self, actor, db):
        if actor.get('mcp_delegation') is not None:
            raise PermissionError('Credential MCP chưa được cấp quyền hộp thư')
        return self.units.require(actor, db)

    @staticmethod
    def _members(db, unit_id):
        # Danh tính toàn cổng bị khóa không còn là người nhận, dù membership còn.
        return db.execute('''SELECT m.identity AS id,
            CASE WHEN m.identity='chu-quan' THEN 'Chủ quản' ELSE a.ten END AS name,
            CASE WHEN m.identity='chu-quan' THEN 'quan-tri' ELSE a.role END AS role,
            1 AS active,m.epoch
            FROM don_vi_members m LEFT JOIN agents a ON a.ma=m.identity
            WHERE m.unit_id=? AND m.active=1
              AND (m.identity='chu-quan' OR (a.active=1 AND a.role='operator'))
            ORDER BY m.identity''', (unit_id,)).fetchall()

    def agents(self, actor):
        if self.units is None:
            return self.kho.agents(actor)
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            scope = self._scope(actor, db)
            return [{key: row[key] for key in ('id','name','role','active')}
                    for row in self._members(db, scope.unit_id)]

    def read(self, actor, peer=None):
        if self.units is None:
            return self.kho.hop_thu(actor['id'], peer)
        if peer is not None and (not isinstance(peer, str) or not 1 <= len(peer) <= 64):
            raise ValueError('Người đối thoại không hợp lệ')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN')
            scope = self._scope(actor, db)
            sql = '''SELECT id,sender,recipient,body,created FROM unit_messages
                WHERE unit_id=? AND ((sender=? AND sender_epoch=?) OR
                                      (recipient=? AND recipient_epoch=?))'''
            values = [scope.unit_id, scope.identity, scope.epoch, scope.identity, scope.epoch]
            if peer:
                sql += ' AND (sender=? OR recipient=?)'
                values += [peer, peer]
            rows = db.execute(sql+' ORDER BY created DESC,id DESC LIMIT 100', values).fetchall()
            return [dict(row) for row in reversed(rows)]

    def send(self, actor, recipient, body):
        if self.units is None:
            return self.kho.gui(actor['id'], recipient, body)
        if (not isinstance(recipient, str) or not 1 <= len(recipient) <= 64
                or not isinstance(body, str) or not 1 <= len(body.strip()) <= 4000):
            raise ValueError('Người nhận hoặc nội dung không hợp lệ')
        identifier, now = secrets.token_hex(12), time.time()
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            scope = self._scope(actor, db)
            target = next((row for row in self._members(db, scope.unit_id) if row['id'] == recipient), None)
            if target is None:
                raise PermissionError('Người nhận không thuộc phạm vi đơn vị đang hoạt động')
            db.execute('INSERT INTO unit_messages VALUES(?,?,?,?,?,?,?,?)',
                       (identifier, scope.unit_id, scope.identity, recipient,
                        scope.epoch, target['epoch'], body.strip(), now))
            # Audit chỉ giữ mã đơn vị/thông điệp; nội dung riêng nằm trong bảng có scope.
            db.execute('INSERT INTO su_kien(actor,action,target,created) VALUES(?,?,?,?)',
                       (scope.identity, 'gui-thong-diep-don-vi', scope.unit_id+':'+identifier, now))
        return {'id': identifier, 'status': 'da-giao-hop-thu', 'recipient': recipient}
