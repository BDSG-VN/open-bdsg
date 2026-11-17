"""AI theo phạm vi đơn vị; SQLite là nguồn cấu hình chuẩn của proxy loopback.

Master key chỉ backend giữ. Alias riêng không phải cách ly mật mã tại proxy.
Mỗi lần gửi kiểm lại cấu hình và quyền trong giao dịch giữ ngân sách.
"""
import copy
import json
import secrets

from mo_hinh_bdsg import LoiMoHinhBDSG
from ngan_sach_ai import DEFAULT_POLICY, NganSachAI
from quyen_tac_vu import authorize_run
from trung_tam_ai import TrungTamAI, MoHinhLiteLLM, validate_catalogue, choose_catalogue


def unit_proxy_config(db):
    """Tái sinh chính xác proxy từ snapshot SQLite, dùng cả khi kiểm sao lưu."""
    rows = db.execute('SELECT unit_id,revision,document FROM ai_unit_configs ORDER BY unit_id').fetchall()
    master = db.execute('SELECT master_key FROM ai_unit_proxy WHERE id=1').fetchone()
    if not rows and not master:
        return None
    if not rows or not master or not isinstance(master[0],str) or len(master[0]) < 32:
        raise ValueError('Nguồn cấu hình AI đơn vị thiếu cặp proxy')
    models=[]
    total_models=0
    for unit_id,revision,document in rows:
        data=json.loads(document)
        validated=validate_catalogue({k:data[k] for k in ('enabled','default_model','models','policy')}, {'models':[]})
        if data.get('revision') != revision or not isinstance(revision,str) or len(revision)!=24:
            raise ValueError('Revision AI đơn vị không khớp')
        total_models += len(validated['models'])
        if validated['enabled']:
            for model in validated['models']:
                models.append({**model,'id':unit_id+'-'+model['id'],'revision':revision})
    if total_models>128:
        raise ValueError('Vượt trần mô hình toàn máy chủ')
    result=TrungTamAI.proxy_config({'enabled':False,'models':[],'revision':'','gateway_key':master[0]})
    for model in models:
        compiled=TrungTamAI.proxy_config({'enabled':True,'models':[model],
            'revision':model['revision'],'gateway_key':master[0]})
        result['model_list'].extend(compiled['model_list'])
    return result


class AITheoDonVi:
    def __init__(self,kho,units,projects,*,probe=None,adapter_factory=None,host_policy=None):
        self.kho,self.units,self.projects=kho,units,projects
        self.probe=probe or TrungTamAI._probe
        self.factory=adapter_factory or (lambda alias,key:MoHinhLiteLLM(alias,key))
        self.proxy_path=kho.root/'litellm-config.json'
        self.budget=NganSachAI(kho,units=units,projects=projects,host_policy=host_policy)
        with kho.ket_noi() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS ai_unit_configs(
                unit_id TEXT PRIMARY KEY REFERENCES don_vi(id),revision TEXT NOT NULL,document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS ai_unit_proxy(id INTEGER PRIMARY KEY CHECK(id=1),master_key TEXT NOT NULL);''')

    @staticmethod
    def _empty():
        return {'enabled':False,'default_model':None,'models':[], 'policy':dict(DEFAULT_POLICY),'revision':'none'}

    def _read(self,db,unit_id):
        row=db.execute('SELECT document FROM ai_unit_configs WHERE unit_id=?',(unit_id,)).fetchone()
        return json.loads(row[0]) if row else self._empty()

    def _scope(self,actor,db,admin=False):
        scope=self.units.require(actor,db)
        if admin and scope.role!='admin':
            raise PermissionError('Chỉ quản trị đơn vị được cấu hình AI của đơn vị')
        return scope

    @staticmethod
    def _catalogue(data):
        return {'enabled':data['enabled'],'default_model':data['default_model'],
                'models':[{k:m[k] for k in ('id','label','capabilities','skills')} for m in data['models']],
                'automatic_selection':True}

    def catalogue(self,actor):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN'); scope=self._scope(actor,db)
            return self._catalogue(self._read(db,scope.unit_id))

    def _admin_result(self,data):
        result=self._catalogue(data)
        result.update(models=[{**{k:v for k,v in m.items() if k!='api_key'},'has_api_key':bool(m.get('api_key'))} for m in data['models']],
            policy=dict(data['policy']),configured=bool(data['enabled'] and data['models']),verified=False,revision=data['revision'])
        return result

    def admin(self,actor):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN'); scope=self._scope(actor,db,True)
            return self._admin_result(self._read(db,scope.unit_id))

    def save(self,actor,data):
        previous=None; written=False
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            scope=self._scope(actor,db,True)
            if any((self.kho.root/name).exists() for name in ('ai-models-private.json','model-private.json')):
                raise ValueError('Cần chuyển đổi cấu hình AI cũ rõ ràng trước khi công bố AI đơn vị')
            # Không tự sửa trạng thái bất nhất sau sự cố bằng một lần lưu khác.
            current=unit_proxy_config(db)
            if current is not None: self._consistent(db)
            elif self.proxy_path.exists():
                raise ValueError('Proxy chưa có nguồn cấu hình đơn vị tương ứng')
            candidate=validate_catalogue(data,self._read(db,scope.unit_id))
            candidate['revision']=secrets.token_hex(12)
            db.execute('INSERT INTO ai_unit_configs VALUES(?,?,?) ON CONFLICT(unit_id) DO UPDATE SET revision=excluded.revision,document=excluded.document',
                (scope.unit_id,candidate['revision'],json.dumps(candidate,ensure_ascii=False)))
            db.execute('INSERT OR IGNORE INTO ai_unit_proxy VALUES(1,?)',(secrets.token_urlsafe(36),))
            proxy=unit_proxy_config(db)
            if len(json.dumps(proxy).encode())>2*1024*1024: raise ValueError('Cấu hình proxy vượt kích thước cho phép')
            previous=json.loads(self.proxy_path.read_text(encoding='utf-8')) if self.proxy_path.exists() else None
            try:
                written=True; TrungTamAI._write(self.proxy_path,proxy)
                self._scope(actor,db,True)
                self.units._audit(db,actor['id'],'cau-hinh-ai-don-vi',scope.unit_id+':'+candidate['revision'])
                db.commit()
            except BaseException:
                db.rollback()
                if written:
                    try:
                        if previous is None: self.proxy_path.unlink(missing_ok=True)
                        else: TrungTamAI._write(self.proxy_path,previous)
                    except OSError: pass  # Lần admission sau đối soát đầy đủ và đóng cổng.
                raise
        return self._admin_result(candidate)

    def repair_proxy(self,actor):
        """Chỉ vận hành phục hồi tệp đã gián đoạn từ nguồn SQLite nguyên vẹn.

        Không cấp qua HTTP và không suy đoán khóa/revision khi nguồn bị thiếu.
        Lỗi ghi vẫn giữ cổng đóng nhờ đối soát trước mỗi admission/lời gọi.
        """
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            identity=self.units.require_system_admin(actor,db)
            if any((self.kho.root/name).exists() for name in ('ai-models-private.json','model-private.json')):
                raise ValueError('Cần chuyển đổi cấu hình AI cũ rõ ràng trước khi phục hồi proxy đơn vị')
            expected=unit_proxy_config(db)
            if expected is None:
                raise ValueError('Chưa có nguồn cấu hình AI đơn vị để phục hồi proxy')
            TrungTamAI._write(self.proxy_path,expected)
            self.units.require_system_admin(actor,db)
            self.units._audit(db,identity,'phuc-hoi-proxy-ai-don-vi','proxy')
            return {'repaired':True,
                    'units':db.execute('SELECT count(*) FROM ai_unit_configs').fetchone()[0],
                    'models':len(expected['model_list'])}

    def _consistent(self,db):
        expected=unit_proxy_config(db)
        try: actual=json.loads(self.proxy_path.read_text(encoding='utf-8'))
        except (OSError,ValueError): actual=None
        if expected is None or actual!=expected:
            raise LoiMoHinhBDSG('Cấu hình AI và proxy chưa nhất quán; chưa gửi yêu cầu tới nhà cung cấp')
        return expected

    def quota(self,actor):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN'); scope=self._scope(actor,db)
            policy=self._read(db,scope.unit_id)['policy']
        result=self.budget.status(actor,policy)
        if scope.role!='admin': result['policy']={k:v for k,v in result['policy'].items() if k.endswith('_per_user')}
        return result

    def bind(self,actor):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN'); scope=self._scope(actor,db)
            return _AIPhamVi(self,self.units.reference(actor,db),self._read(db,scope.unit_id)['revision'])

    def require_config_revision(self, actor, revision, db):
        """Kiểm cấu hình trong giao dịch dự thảo, không probe mạng khi giữ writer."""
        scope = self._scope(actor, db)
        data = self._read(db, scope.unit_id)
        if data['revision'] != revision or not data['enabled'] or not data['models']:
            raise PermissionError('Cấu hình AI của lượt đề xuất đã thay đổi')


class _AIPhamVi:
    def __init__(self,service,reference,revision):
        self.service,self.reference,self.revision=service,reference,revision
        self.configuration_error=''

    def _live(self,db,actor=None,ready=False):
        restored=self.service.units.restore(self.reference,db)
        if actor is not None and self.service.units.reference(actor,db)!=self.reference:
            raise PermissionError('Danh tính không khớp ràng buộc AI')
        data=self.service._read(db,self.reference['unit_id'])
        if data['revision']!=self.revision:
            raise LoiMoHinhBDSG('Cấu hình AI của lượt chạy đã thay đổi; cần tạo lượt mới')
        if ready:
            proxy=self.service._consistent(db)
            aliases={self._alias(m,data) for m in data['models']} if data['enabled'] else set()
            if not aliases or not self.service.probe(proxy['general_settings']['master_key'],aliases):
                raise LoiMoHinhBDSG('Gateway AI chưa nạp danh mục mới hoặc chưa hoạt động')
        return restored,data

    def _alias(self,model,data):
        return self.reference['unit_id']+'-'+model['id']+'-'+data['revision']

    @property
    def configured(self):
        with self.service.kho.ket_noi() as db:
            db.execute('BEGIN'); _,data=self._live(db)
            return bool(data['enabled'] and data['models'])

    def public_status(self):
        configured=self.configured
        return {'configured':configured,'mode':'mo-hinh-api' if configured else 'quy-trinh','provider':'litellm',
                'model':'Tự động theo công việc' if configured else None,'verified':False,'configuration_revision':self.revision}

    def catalogue(self):
        with self.service.kho.ket_noi() as db:
            db.execute('BEGIN'); _,data=self._live(db)
            return self.service._catalogue(data)

    def admit(self,db,actor,task_id,run,selection='auto',project_id=''):
        _,data=self._live(db,actor,True)
        choose_catalogue(data,{'model_selection':selection})
        self.service.budget.claim_task(db,actor,task_id,run,data['policy'],project_id=project_id)

    def run(self,prompt,context,core,actor,on_event=None,cancelled=None):
        def stop():
            if cancelled and cancelled(): raise LoiMoHinhBDSG('Tác vụ đã được yêu cầu dừng')
        stop()
        with self.service.kho.ket_noi() as db:
            db.execute('BEGIN'); _,config=self._live(db,actor,True)
            master=self.service._consistent(db)['general_settings']['master_key']
        model,config,reason=choose_catalogue(copy.deepcopy(config),context)
        emit=on_event or (lambda *a,**k:None)
        emit('model-selected','Đã chọn mô hình trong danh mục đơn vị.',model_id=model['id'],model_label=model['label'],selection_reason=reason)
        adapter=self.service.factory(self._alias(model,config),master)
        def guard(db):
            self._live(db,actor,True)
        def event(kind,message,**extra):
            if kind=='model-reserve':
                stop()
                count=extra.get('input_bytes')
                if type(count) is not int or count<1: raise LoiMoHinhBDSG('Thiếu số đo ngữ cảnh để giữ ngân sách')
                self.service.budget.reserve(actor,context.get('task_id',''),model['id'],count+4096,
                    MoHinhLiteLLM.MAX_OUTPUT_TOKENS,model['prices'],config['policy'],
                    project_id=context.get('project_id',''),run=context.get('run'),guard=guard)
            emit(kind,message,**extra)
            if kind=='model-reserve':
                # Callback có thể vừa thu hồi quyền hoặc xoay cấu hình. Kiểm lần
                # cuối sau callback, không giữ khóa writer khi gọi mã bên ngoài.
                stop()
                with self.service.kho.ket_noi() as db:
                    db.execute('BEGIN IMMEDIATE')
                    self._live(db,actor)
                    authorize_run(db,actor,context.get('task_id',''),context.get('run'),
                        self.service.units,self.service.projects,context.get('project_id',''))
                    self.service._consistent(db)
        return adapter.run(prompt,context,core,actor,event,cancelled)
