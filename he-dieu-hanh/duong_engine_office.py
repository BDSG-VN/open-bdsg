"""Profile đường dẫn engine theo cấu hình nginx ONLYOFFICE đã đối chiếu."""
import re
from urllib.parse import urlsplit, unquote, parse_qsl

KEY=r'bdsg-[a-f0-9]{32}'
VERSION=r'\d+\.\d+\.\d+[.-][A-Za-z0-9_]+'


def phan_loai(path):
    if not isinstance(path,str) or not 1<=len(path)<=8192:
        raise ValueError('Đường engine không hợp lệ')
    if any(ord(c)<32 or ord(c)==127 for c in path) or '\\' in path:
        raise ValueError('Đường engine không hợp lệ')
    parsed=urlsplit(path)
    if parsed.scheme or parsed.netloc or '#' in path:
        raise ValueError('Cần đường dẫn nội bộ engine')
    decoded=unquote(parsed.path)
    if ('%' in decoded or '\\' in decoded or '//' in decoded or ';' in decoded
            or any(ord(c)<32 or ord(c)==127 for c in decoded)
            or any(part in ('.','..') for part in decoded.split('/'))
            or not decoded.startswith('/office-docs/')):
        raise ValueError('Đường engine không chuẩn')
    relative=decoded[len('/office-docs/'):]
    relative=re.sub('^'+VERSION+'/', '', relative, count=1)
    if relative.rsplit('/',1)[-1]=='document_editor_service_worker.js':
        raise ValueError('Cache trình duyệt chưa có vòng đời theo quyền')
    static=(relative.startswith(('web-apps/','sdkjs/','sdkjs-plugins/','fonts/','dictionaries/'))
            or relative=='meta/formats')
    # Service worker hiện cache cả dữ liệu tài liệu trước khi hỏi gateway.
    # Chưa cho đăng ký tới khi có vòng đời cache theo danh tính/thu hồi quyền.
    match=re.fullmatch(r'(?:cache/files/('+KEY+r')(?:_[A-Za-z0-9.-]+)?/.*|doc/('+KEY+r')/.*)',relative)
    if not static and not match:
        raise ValueError('Route engine chưa có hợp đồng quyền')
    key=(match.group(1) or match.group(2)) if match else None
    if any(found!=key for found in re.findall(KEY,relative)):
        raise ValueError('Không được thay key trong đường engine')
    seen=set()
    for name,value in parse_qsl(parsed.query,keep_blank_values=True,max_num_fields=100):
        if (any('%' in item or '\\' in item
                or any(ord(c)<32 or ord(c)==127 for c in item)
                or any(part in ('.','..') for part in item.split('/')) for item in (name,value))
                or name.lower()=='wopisrc'):
            raise ValueError('Query engine chưa được hỗ trợ')
        normalized=name.lower()
        if normalized in ('key','doc','docid','documentid','documentkey','document_id','shardkey'):
            if static or normalized in seen or value!=key:
                raise ValueError('Query không thuộc key của đường engine')
            seen.add(normalized)
        if any(found!=key for found in re.findall(KEY,value)):
            raise ValueError('Query mang key tài liệu khác')
    return ('static' if static else 'document'),key
