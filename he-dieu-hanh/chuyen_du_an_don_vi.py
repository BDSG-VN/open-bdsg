"""Chuyển quan hệ dự án cũ trên bản sao; chưa phải cutover đa đơn vị toàn cổng."""
import time


def migrate_legacy(projects, actor):
    if projects.units is None:
        raise ValueError("Cần Module đơn vị trước khi chuyển dữ liệu")
    with projects.kho.ket_noi() as db:
        db.execute("BEGIN IMMEDIATE")
        identity = projects.units.require_system_admin(actor, db)
        marker = db.execute("SELECT unit_id FROM don_vi_migrations WHERE version='projects-v1'").fetchone()
        identities = {"chu-quan": 1}
        identities.update({row[0]: row[1] for row in db.execute("SELECT ma,active FROM agents WHERE role='operator'")})
        old_projects = db.execute("SELECT id,owner FROM du_an").fetchall()
        grants = db.execute("SELECT project_id,identity,role FROM du_an_members").fetchall()
        project_ids = {row[0] for row in old_projects}
        if any(row[1] not in identities for row in old_projects) or any(
                row[0] not in project_ids or row[1] not in identities or row[2] not in ('viewer','editor') for row in grants):
            raise ValueError("Có chủ sở hữu hoặc quyền cũ chưa xác định; cần đối soát")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ('documents','office_files','office_uploads'):
            if table in tables and db.execute(f"SELECT 1 FROM {table} d LEFT JOIN du_an p ON p.id=d.project_id WHERE p.id IS NULL LIMIT 1").fetchone():
                raise ValueError("Có tài liệu không gắn dự án hợp lệ; giữ dữ liệu để đối soát")
        if marker:
            missing = db.execute("SELECT 1 FROM du_an p LEFT JOIN du_an_units s ON s.project_id=p.id WHERE s.project_id IS NULL LIMIT 1").fetchone()
            if missing:
                raise ValueError("Có dự án chưa phân loại; cần đối soát thay vì gán đơn vị mặc định")
            return {"unit_id": marker[0], "changed": False}
        if db.execute("SELECT 1 FROM don_vi LIMIT 1").fetchone():
            raise ValueError("Chỉ chuyển dữ liệu cũ trước khi tạo các đơn vị mới")
        unit_id = 'legacy-thanhhoa'
        db.execute("INSERT INTO don_vi VALUES(?,?,1,?)", (unit_id, "Không gian hiện tại — chưa phân loại", time.time()))
        for person, active in identities.items():
            db.execute("INSERT INTO don_vi_members(unit_id,identity,role,active,epoch) VALUES(?,?,?,?,1)", (unit_id, person, 'admin' if person=='chu-quan' else 'member', int(bool(active))))
        db.executemany("INSERT INTO du_an_units VALUES(?,?)", ((pid, unit_id) for pid in project_ids))
        db.executemany("INSERT INTO du_an_unit_grants VALUES(?,?,?,?,1)",
            ((row[0], unit_id, row[1], row[2]) for row in grants))
        # Quyền toàn cổng của chủ quản trước migration được ghi rõ trên từng
        # project legacy; không biến thành bypass đối với các đơn vị mới.
        db.executemany("""INSERT INTO du_an_unit_grants VALUES(?,?,'chu-quan','manager',1)
            ON CONFLICT(project_id,unit_id,identity) DO UPDATE SET role='manager'""", ((pid, unit_id) for pid in project_ids))
        db.execute("INSERT INTO don_vi_migrations VALUES('projects-v1',?,?)", (unit_id, time.time()))
        db.execute("INSERT INTO su_kien(actor,action,target,created) VALUES(?,?,?,?)", (identity, 'chuyen-du-an-don-vi', unit_id, time.time()))
        return {"unit_id": unit_id, "changed": True, "projects": len(project_ids), "source_grants": len(grants)}
