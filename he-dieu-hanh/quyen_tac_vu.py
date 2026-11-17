"""Quyền tác vụ dùng chung cho worker và giữ trước ngân sách AI.

Tham chiếu lưu theo lượt không được tự làm mới bằng tư cách vừa cấp lại.
Các hàm nhận kết nối của bên gọi để kiểm quyền trong cùng giao dịch ghi.
"""
import json


def _stored_task(db, task_id):
    tables = {row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if 'cong_viec_tasks' not in tables:
        return None
    row = db.execute('SELECT owner,document,status FROM cong_viec_tasks WHERE id=?',
                     (task_id,)).fetchone()
    if row is None:
        return None
    if 'cong_viec_units' not in tables:
        raise ValueError('Tác vụ chưa có ràng buộc đơn vị')
    binding = db.execute('SELECT unit_id,epoch,revision FROM cong_viec_units WHERE task_id=?',
                         (task_id,)).fetchone()
    try:
        task = json.loads(row[1])
        if (not binding or task['owner'] != row[0]
                or task['unit_id'] != binding[0]):
            raise ValueError('Tác vụ không khớp ràng buộc đơn vị')
    except (ValueError,TypeError,KeyError):
        raise ValueError('Tác vụ chưa có ràng buộc hợp lệ') from None
    reference = {'identity':row[0], 'unit_id':binding[0],
                 'epoch':binding[1], 'revision':binding[2]}
    return task, reference, row[2]


def task_reference(db, task):
    """Lấy tham chiếu đã lưu, kiểm cả hàng SQL và tài liệu tác vụ."""
    stored = _stored_task(db, task['id'])
    if (stored is None or stored[1]['identity'] != task['owner']
            or stored[1]['unit_id'] != task.get('unit_id')):
        raise ValueError('Không tìm thấy tác vụ trong phạm vi quyền')
    return stored[1]


def _project(db, actor, task, project_id, projects):
    actual = task.get('project_id', '')
    if not isinstance(actual, str):
        raise PermissionError('Tác vụ chưa có ràng buộc dự án hợp lệ')
    if project_id and actual != project_id:
        raise PermissionError('Dự án không khớp tác vụ')
    if actual:
        if projects is None:
            raise PermissionError('Cần kiểm quyền dự án trong phạm vi đơn vị')
        projects.authorize(actor, actual, db=db)
    return actual


def authorize_claim(db, actor, task_id, units, projects, project_id=''):
    """Tạo mới được phép chưa có tác vụ; lượt tiếp tục kiểm chủ/đơn vị/dự án."""
    scope = units.require(actor, db)
    try:
        stored = _stored_task(db, task_id)
    except ValueError as error:
        raise PermissionError(str(error)) from None
    if stored is None:
        task = {'project_id':project_id}
    else:
        task, reference, _ = stored
        if reference['identity'] != scope.identity or reference['unit_id'] != scope.unit_id:
            raise PermissionError('Tác vụ không thuộc phạm vi này')
    return scope, _project(db, actor, task, project_id, projects)


def authorize_run(db, actor, task_id, run, units, projects, project_id='', *, authorizer=None):
    """Kiểm tư cách sống, lượt, vòng đời và tham chiếu đóng băng trước AI."""
    scope = units.require(actor, db)
    if type(run) is not int or run < 1:
        raise PermissionError('Cần lượt chạy cụ thể của tác vụ trong đơn vị')
    try:
        stored = _stored_task(db, task_id)
    except ValueError as error:
        raise PermissionError(str(error)) from None
    if stored is None:
        raise PermissionError('Không tìm thấy tác vụ trong phạm vi')
    task, reference, status = stored
    if task.get('mcp_delegated'):
        if authorizer is None:
            raise PermissionError('Thiếu bộ kiểm nguồn ủy quyền của lượt chạy')
        authorizer(actor, task, db)
    if (reference != {'identity':scope.identity, 'unit_id':scope.unit_id,
                      'epoch':scope.epoch, 'revision':scope.revision}
            or status not in ('queued','running')):
        raise PermissionError('Không tìm thấy tác vụ trong phạm vi')
    actual_run = task.get('run')
    if type(actual_run) is not int or actual_run < 1:
        raise PermissionError('Tác vụ chưa có ràng buộc lượt chạy hợp lệ')
    if task.get('cancelled') or task.get('cancel_requested') or run != actual_run:
        raise PermissionError('Tác vụ không thuộc phạm vi lượt chạy')
    return scope, _project(db, actor, task, project_id, projects)
