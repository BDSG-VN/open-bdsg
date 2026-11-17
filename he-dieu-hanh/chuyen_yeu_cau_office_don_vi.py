"""Phân loại yêu cầu Office cũ trên bản sao tổng hợp, không phải cutover."""
import re
import time

from van_phong import validate_request_mapping


def migrate_legacy(office, actor, *, copy_only=False):
    """Caller xác nhận đang làm trên bản sao; không tự đoán đơn vị từ chia sẻ."""
    if not copy_only or office.projects.units is None:
        raise ValueError("Chỉ chuyển bản sao đã có registry đơn vị")
    with office.kho.ket_noi() as db:
        db.execute("BEGIN IMMEDIATE")
        identity = office.projects.units.require_system_admin(actor, db)
        legacy = db.execute("SELECT unit_id FROM don_vi_migrations WHERE version='projects-v1'").fetchone()
        marker = db.execute("SELECT unit_id FROM don_vi_migrations WHERE version='office-requests-v1'").fetchone()
        creates = db.execute("SELECT * FROM office_creates").fetchall()
        uploads = db.execute("SELECT id,owner,project_id,request_key FROM office_uploads").fetchall()
        # Kiểm cả khi chạy lại: writer cũ hoặc bản sao hỏng không được đi qua marker.
        for table in ('office_creates', 'office_uploads'):
            if db.execute(f"""SELECT 1 FROM {table} r LEFT JOIN du_an_units p
                    ON p.project_id=r.project_id WHERE p.project_id IS NULL LIMIT 1""").fetchone():
                raise ValueError("Yêu cầu Office mồ côi; cần đối soát")
        if db.execute("""SELECT 1 FROM office_creates r LEFT JOIN office_files f ON f.id=r.file_id
                WHERE f.id IS NULL OR f.project_id<>r.project_id OR f.owner<>r.owner LIMIT 1""").fetchone():
            raise ValueError("Yêu cầu tạo không khớp tệp; cần đối soát")
        if db.execute("""SELECT 1 FROM office_uploads r LEFT JOIN office_files f ON f.id=r.file_id
                WHERE r.file_id IS NOT NULL AND (f.id IS NULL OR f.project_id<>r.project_id
                OR f.owner<>r.owner) LIMIT 1""").fetchone():
            raise ValueError("Phiên tải hoàn tất không khớp tệp; cần đối soát")
        if db.execute("""SELECT 1 FROM office_request_units r
                LEFT JOIN don_vi d ON d.id=r.unit_id
                LEFT JOIN office_creates c ON r.kind='create' AND c.owner=r.owner AND c.request=r.internal_key
                LEFT JOIN office_uploads u ON r.kind='upload' AND u.owner=r.owner AND u.request_key=r.internal_key
                WHERE d.id IS NULL OR r.kind NOT IN ('create','upload')
                OR (r.kind='create' AND c.file_id IS NULL)
                OR (r.kind='upload' AND u.id IS NULL) LIMIT 1""").fetchone():
            raise ValueError("Metadata yêu cầu mồ côi; cần đối soát")
        for mapping in db.execute("SELECT * FROM office_request_units"):
            validate_request_mapping(mapping)
        unclassified = []
        for kind, rows, key in [('create', creates, 'request'), ('upload', uploads, 'request_key')]:
            for row in rows:
                classified = db.execute("""SELECT unit_id,request_key FROM office_request_units
                    WHERE kind=? AND owner=? AND internal_key=?""", (kind,row['owner'],row[key])).fetchone()
                if classified:
                    if kind == 'upload' and not db.execute("SELECT 1 FROM office_upload_units WHERE upload_id=? AND unit_id=?",
                            (row['id'],classified['unit_id'])).fetchone():
                        raise ValueError("Phạm vi phiên tải không khớp")
                elif marker:
                    raise ValueError("Có yêu cầu cũ chưa phân loại; cần đối soát")
                else:
                    unclassified.append((kind, row, key))
        if marker:
            if not legacy or marker[0] != legacy[0]:
                raise ValueError("Marker Office không khớp nguồn legacy")
            return {"changed":False,"unit_id":marker[0]}
        if (not legacy or db.execute("SELECT count(*) FROM don_vi").fetchone()[0] != 1
                or db.execute("SELECT 1 FROM du_an_units WHERE unit_id<>? LIMIT 1",(legacy[0],)).fetchone()
                or db.execute("SELECT 1 FROM du_an_unit_grants WHERE unit_id<>? LIMIT 1",(legacy[0],)).fetchone()):
            raise ValueError("Nguồn legacy không rõ hoặc đã có chia sẻ đa đơn vị")
        unit = legacy[0]
        count = 0
        for kind, row, key in unclassified:
            if not re.fullmatch(r'[a-f0-9-]{32,64}',row[key]):
                raise ValueError("Khóa yêu cầu legacy chưa xác định")
            bound = office.projects.units.bind(
                {"id":row['owner'],"role":"quan-tri" if row['owner']=='chu-quan' else "operator"},unit)
            internal = office._request_key(db,bound,kind,row[key],persist=True)
            if kind == 'create':
                db.execute("UPDATE office_creates SET request=? WHERE owner=? AND request=?",(internal,row['owner'],row[key]))
            else:
                db.execute("UPDATE office_uploads SET request_key=? WHERE id=?",(internal,row['id']))
                db.execute("INSERT INTO office_upload_units VALUES(?,?)",(row['id'],unit))
            count += 1
        db.execute("INSERT INTO don_vi_migrations VALUES('office-requests-v1',?,?)",(unit,time.time()))
        db.execute("INSERT INTO su_kien(actor,action,target,created) VALUES(?,?,?,?)",
            (identity,'chuyen-yeu-cau-office-don-vi',unit,time.time()))
        return {"changed":True,"unit_id":unit,"requests":count}
