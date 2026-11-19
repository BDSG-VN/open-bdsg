"""Nghiệm thu thu hồi kết nối Office đang mở trên dữ liệu tổng hợp do người chạy cấp."""
import argparse,asyncio,json,os,pathlib,re,stat,time
from datetime import datetime,timezone
from urllib.parse import urlsplit
from quan_sat_office_polling import QuanSatPolling

phase='opening';events=[];sockets={'a':[],'c':[]};closed_at={};envelopes={}

def frame_types(data):
    if not isinstance(data,str):return []
    try:
        wire=data[1:] if data.startswith('a[') else re.sub(r'^\d+(?=[\[{])','',data)
        value=json.loads(wire)
        values=value if isinstance(value,list) else [value]
        result=[]
        for value in values:
            if isinstance(value,str):
                if not value.startswith(('{','[')):continue
                value=json.loads(value)
            if isinstance(value,dict) and isinstance(value.get('type'),str) and re.fullmatch(r'[A-Za-z]{1,40}',value['type']):
                result.append(value['type'])
        return result
    except (ValueError,TypeError):return []

def record(letter,direction,data):
    prefix=re.match(r'^\d+',data).group(0) if isinstance(data,str) and re.match(r'^\d+',data) else type(data).__name__
    envelopes[prefix]=envelopes.get(prefix,0)+1
    for kind in frame_types(data):events.append({'actor':letter,'direction':direction,'type':kind,'phase':phase,'time':time.monotonic()})

async def login(page,username,password):
    await page.goto(ORIGIN+'/api/me')
    result=await page.evaluate('''async data=>{
      const response=await fetch('/api/login',{method:'POST',credentials:'same-origin',
        headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
      return {status:response.status};
    }''',{'username':username,'password':password})
    assert result['status']==200,'Synthetic login failed'

async def api(page,path,body=None,headers=None):
    return await page.evaluate('''async data=>{
      const response=await fetch(data.path,{method:data.body===null?'GET':'POST',credentials:'same-origin',
        headers:{'Content-Type':'application/json',...data.headers},
        body:data.body===null?undefined:JSON.stringify(data.body)});
      return response.status;
    }''',{'path':path,'body':body,'headers':headers or {}})

async def chot_bao_cao(events,deadline,closed,*,polling=None,new_status=None):
    # drain có thể vừa bổ sung saveChanges sau cửa sổ thu hồi; chỉ chốt
    # số đếm sau await cuối, trước ghi kết quả mà không gọi thêm I/O.
    if polling:await polling.drain()
    after_changes=sum(e['actor']=='c' and e['direction']=='received' and e['type']=='saveChanges'
        and e['time']>=deadline for e in events)
    return {'revoked_actor_change_events_after_5s':after_changes,
        'protocol_types':sorted({e['type'] for e in events}),
        'secure_baseline':closed and after_changes==0 and (polling is None or new_status==403)}

async def main():
    global phase
    result={'measured_at':datetime.now(timezone.utc).isoformat(),'source_commit':fixtures['source_commit'],
            'sdk_engine':'real','launcher':'private harness with backend-issued configs','client_guard':False,
            'attempt':args.label}
    polling=QuanSatPolling(record,lambda:phase) if args.transport=='polling' else None
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser_args=['--host-resolver-rules=MAP '+urlsplit(ORIGIN).hostname+' 127.0.0.1'] if args.loopback else []
        browser=await p.chromium.launch(headless=True,args=browser_args)
        try:
            pages={}
            for letter in ('a','c'):
                context=await browser.new_context(viewport={'width':1440,'height':1000},ignore_https_errors=False)
                if polling:
                    await context.route_web_socket(re.compile(r'/doc/'),polling.blocker(letter))
                page=await context.new_page();pages[letter]=page
                def on_socket(ws,letter=letter):
                    if '/doc/' not in urlsplit(ws.url).path:return
                    sockets[letter].append(ws)
                    ws.on('framereceived',lambda data:record(letter,'received',data))
                    ws.on('framesent',lambda data:record(letter,'sent',data))
                    ws.on('close',lambda:closed_at.setdefault(id(ws),time.monotonic()))
                if polling:polling.attach(page,letter)
                else:page.on('websocket',on_socket)
                await login(page,fixtures['actors'][letter],credentials[letter])
                config=json.dumps(fixtures[letter]['config'],ensure_ascii=False).replace('<',r'\u003c')
                html='''<!doctype html><html lang="vi"><meta charset="utf-8"><title>R14 WS synthetic</title>
                <style>html,body,#editor{height:100%;margin:0}</style><div id="editor"></div>
                <script src="/office-docs/web-apps/apps/api/documents/api.js"></script><script>
                window.__r14Ready=false;window.__dirty=0;window.__errors=[];
                const config=CONFIG;
                config.events={onDocumentReady(){window.__r14Ready=true;},
                  onDocumentStateChange(e){if(e.data)window.__dirty++;},
                  onError(e){window.__errors.push(Number(e.data?.errorCode)||0);}};
                window.editor=new DocsAPI.DocEditor('editor',config);
                </script></html>'''.replace('CONFIG',config)
                def make_fixture_route(body):
                    async def fixture_route(route):await route.fulfill(content_type='text/html; charset=utf-8',body=body)
                    return fixture_route
                await page.route('**/r14-ws-fixture',make_fixture_route(html))
                await page.goto(ORIGIN+'/r14-ws-fixture')
                await page.wait_for_function('window.__r14Ready===true',timeout=90000)
                if polling:
                    await polling.drain()
                    assert polling.ready(letter),'No successful real polling GET/POST'
                else:
                    assert any(not ws.is_closed() for ws in sockets[letter]),'No live document WebSocket'
                await page.screenshot(path=str(ROOT/(letter+'-ready.png')))
            boxes=[]
            for frame in pages['a'].frames:
                boxes+=await frame.locator('canvas').evaluate_all('''elements=>elements.map(e=>{
                  const r=e.getBoundingClientRect();return {id:e.id,x:r.x,y:r.y,width:r.width,height:r.height};
                }).filter(r=>r.width>0&&r.height>0)''')
            (ROOT/'ready.json').write_text(json.dumps({'ready':True,'sockets':{k:len(v) for k,v in sockets.items()},'canvas_boxes':boxes}))
            print(json.dumps({'phase':'ready','both_documents_ready':True}),flush=True)
            coords={'x':args.click_x,'y':args.click_y}
            a,c=pages['a'],pages['c']
            phase='before-revoke'
            await a.bring_to_front();await a.mouse.click(coords['x'],coords['y']);await asyncio.sleep(.2);await a.keyboard.press('Control+Home')
            await a.keyboard.type('BDSG WS BEFORE '+args.label,delay=80)
            await asyncio.sleep(3)
            before_changes=sum(e['actor']=='c' and e['direction']=='received' and e['type']=='saveChanges' for e in events)
            assert before_changes>0,'No collaboration changes reached second editor; baseline invalid'
            engine_path=polling.path('c') if polling else urlsplit(sockets['c'][0].url).path
            allowed_before=await api(c,'/api/office-engine-auth',headers={'X-BDSG-Engine-Path':engine_path})
            assert allowed_before==200,'Lease was not valid before revoke'
            owner_context=await browser.new_context(ignore_https_errors=False)
            owner=await owner_context.new_page();await login(owner,fixtures['actors']['owner'],credentials['root'])
            phase='revoking'
            if polling:
                pending_deadline=time.monotonic()+3
                while not polling.pending('c'):
                    assert time.monotonic()<pending_deadline,'No pending real polling GET'
                    await asyncio.sleep(.05)
                accepted_before=polling.pending('c')
            else:
                accepted_before=tuple(ws for ws in sockets['c'] if not ws.is_closed())
                assert accepted_before,'No accepted WebSocket remained before revoke'
            status=await api(owner,'/api/units/members',{'identity':fixtures['actors']['c'],'role':'revoke'},{'X-BDSG-Unit':fixtures['unit']})
            assert status==200,'Membership revoke was not accepted'
            revoked_at=time.monotonic();phase='after-revoke'
            denied_after=await api(c,'/api/office-engine-auth',headers={'X-BDSG-Engine-Path':engine_path})
            assert denied_after==403,'New document request was not denied after revoke'
            deadline=revoked_at+5
            def ended():
                if polling:return polling.ended_by(accepted_before,deadline)
                return all(ws.is_closed() and closed_at.get(id(ws),float('inf'))<=deadline for ws in accepted_before)
            while time.monotonic()<deadline:
                if ended():break
                await asyncio.sleep(.1)
            closed_within_5s=ended()
            await asyncio.sleep(max(0,deadline-time.monotonic()))
            await a.bring_to_front();await a.mouse.click(coords['x'],coords['y']);await asyncio.sleep(.2);await a.keyboard.press('Control+End')
            await a.keyboard.press('Enter');await a.keyboard.type('BDSG WS AFTER REVOKE '+args.label,delay=80)
            await asyncio.sleep(4)
            await c.screenshot(path=str(ROOT/'c-after-revoke.png'))
            if polling:await polling.drain()
            version=await a.evaluate('''async id=>{
              const response=await fetch('/api/tools',{method:'POST',credentials:'same-origin',
                headers:{'Content-Type':'application/json','X-BDSG-Unit':UNIT},
                body:JSON.stringify({name:'van_phong.doc',arguments:{id}})});
              const body=await response.json();return {status:response.status,ok:body.ok,version:body.ket_qua?.file?.version};
            }'''.replace('UNIT',json.dumps(fixtures['unit'])),fixtures['file'])
            assert version['status']==200 and version['ok'] is True
            result.update({'both_documents_ready':True,'collaboration_before_revoke':before_changes,
                'engine_auth_before':allowed_before,'revoke_status':status,'engine_auth_after':denied_after,
                'stored_file_version_after':version['version'],'no_raw_frames_or_tokens_in_evidence':True})
            new_status=None
            if polling:
                new_status=await api(c,engine_path+'?EIO=4&transport=polling')
                result.update({'transport':'polling-only','pending_polls_before_revoke':len(accepted_before),
                    'revoked_poll_requests_ended_within_5s':closed_within_5s,
                    'new_poll_status_after_revoke':new_status})
            else:
                result['revoked_websocket_closed_within_5s']=closed_within_5s
            result.update(await chot_bao_cao(events,deadline,closed_within_5s,polling=polling,new_status=new_status))
            if polling:
                result.update(polling.summary())
                assert all(result['blocked_websocket_attempts'].values()),'SDK did not attempt WebSocket fallback'
            (ROOT/'result.json').write_text(json.dumps(result,indent=2))
            print(json.dumps(result),flush=True)
        except BaseException as error:
            (ROOT/'failure.json').write_text(json.dumps({'phase':phase,'error_class':type(error).__name__,
                'sockets':{k:len(v) for k,v in sockets.items()},'protocol_types':sorted({e['type'] for e in events}),'envelopes':envelopes}))
            raise
        finally:
            await browser.close()
            if polling:await polling.close()
    if not result['secure_baseline']:raise SystemExit(2)

def private_json(path):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
        raise ValueError('Bundle cần tệp riêng, không dùng liên kết')
    if os.name!='nt' and (info.st_uid not in (0,os.getuid()) or stat.S_IMODE(info.st_mode)&0o077):
        raise ValueError('Bundle cần thuộc người chạy và không cấp quyền group/world')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as stream:
        actual=os.fstat(stream.fileno())
        if (actual.st_dev,actual.st_ino)!=(info.st_dev,info.st_ino):
            raise ValueError('Bundle đã đổi tệp trong lúc đọc')
        raw=stream.read(1024*1024+1)
    if len(raw)>1024*1024:raise ValueError('Bundle vượt giới hạn đọc')
    return json.loads(raw.decode('utf-8-sig'))

class QAParser(argparse.ArgumentParser):
    def error(self,message):
        # Mã2 chỉ dành cho phép đo hợp lệ bị đỏ; không lẫn lỗi thiết lập,
        # và không in lại tham số lạ có thể vô tình chứa thông tin xác thực.
        self.exit(3,'Thiết lập QA không hợp lệ. Kiểm tra --help và bundle riêng.\n')


if __name__=='__main__':
    parser=QAParser(description=__doc__)
    parser.add_argument('--origin',required=True,help='Origin HTTPS của môi trường thử riêng')
    parser.add_argument('--bundle-dir',type=pathlib.Path,required=True,help='credentials.json và fixtures.json riêng, không đưa vào Git')
    parser.add_argument('--output-dir',type=pathlib.Path,required=True,help='Thư mục mới để giữ báo cáo và ảnh dữ liệu tổng hợp')
    parser.add_argument('--label',default='probe',help='Nhãn ASCII của lần thử')
    parser.add_argument('--loopback',action='store_true',help='Ánh xạ hostname thử về127.0.0.1 trong Chromium')
    parser.add_argument('--transport',choices=('websocket','polling'),default='websocket',
                        help='Polling chặn WebSocket thử để SDK thật tự fallback; không giả engine')
    parser.add_argument('--click-x',type=int,default=430)
    parser.add_argument('--click-y',type=int,default=300)
    args=parser.parse_args()
    origin=urlsplit(args.origin)
    if (origin.scheme!='https' or not origin.hostname or origin.username or origin.password
            or origin.path not in ('','/') or origin.query or origin.fragment
            or not re.fullmatch(r'[A-Za-z0-9.-]{1,253}',origin.hostname)):
        parser.error('Origin cần HTTPS, hostname hợp lệ và không có path, query hoặc userinfo')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',args.label):parser.error('Nhãn cần1–32ký tự ASCII chữ/số/_/-')
    if not (0<args.click_x<1440 and 0<args.click_y<1000):parser.error('Điểm nhập phải nằm trong viewport1440x1000')
    ORIGIN=args.origin.rstrip('/')
    fixtures=private_json(args.bundle_dir/'fixtures.json')
    credentials=private_json(args.bundle_dir/'credentials.json')
    if fixtures.get('synthetic') is not True:parser.error('Chỉ nhận bundle dữ liệu tổng hợp đã được đánh dấu synthetic=true')
    if not re.fullmatch(r'[a-f0-9]{40}',fixtures.get('source_commit','')):parser.error('Bundle thiếu commit nguồn được thử')
    for letter in ('a','c'):
        config=fixtures[letter]['config']
        if config['documentType']!='word' or config['editorConfig']['user']['id']!=fixtures['actors'][letter]:
            parser.error('Bundle cần hai cấu hình Word khớp tài khoản thử')
        if config['document']['key']!=fixtures[letter]['key']:
            parser.error('Key cấu hình SDK phải khớp key phiên của backend')
    if fixtures['a']['key']!=fixtures['c']['key']:parser.error('Hai tài khoản cần cùng khóa phiên soạn thảo')
    os.umask(0o077)
    ROOT=args.output_dir
    ROOT.mkdir(mode=0o700,parents=True,exist_ok=False)
    asyncio.run(main())
