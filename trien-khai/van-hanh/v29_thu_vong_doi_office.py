"""Kiểm vòng đời guard trên bfcache Chromium; không dùng tài khoản hoặc engine thật."""
import argparse
import asyncio
import contextlib
import hashlib
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.async_api import async_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument('--output', type=Path, required=True, help='Tệp JSON mới, không ghi đè')
args = parser.parse_args()
if args.output.exists() or args.output.is_symlink() or not args.output.parent.is_dir():
    parser.error('Cần tệp đầu ra mới trong thư mục đã tồn tại')
guard_path = args.source_root / 'khong-gian/bao-ve-office.js'
if guard_path.is_symlink() or not guard_path.is_file():
    parser.error('Không đọc được mã guard thường trong source-root')
guard = guard_path.read_bytes()

parent = '''<!doctype html><meta charset="utf-8"><title>Vòng đời guard</title>
<script>
window.BDSGUnit={capture:()=>1,current:token=>token===1,
 snapshot:()=>({mode:'units',actorId:'actor',status:'ready',selected:{id:'unit',epoch:1,revision:1}})};
</script><a href="/away">Rời trang</a><iframe src="/editor"></iframe>'''
editor = '''<!doctype html><meta charset="utf-8"><title>Editor tổng hợp</title>
<button id="activate">Tương tác</button><div id="editor">Editor tổng hợp</div>
<script>
window.notifications=0;window.calls=[];window.lifecycle=[];
window.BDSGSessionGuard={create:()=>({ready:Promise.resolve(),active:true,assertActive(){},check:async()=>{},
 fetch:async(path,options)=>{calls.push(path);return {ok:true,status:200,json:async()=>
 path==='/api/me'?{authenticated:true,user:{id:'actor'},workspace:{mode:'units'}}:
 {units:[{id:'unit',epoch:1,revision:1}]}}}})};
addEventListener('pageshow',event=>lifecycle.push({event:'pageshow',persisted:event.persisted}));
addEventListener('pagehide',event=>lifecycle.push({event:'pagehide',persisted:event.persisted}));
</script><script src="/guard.js"></script><script>
window.guard=BDSGOfficeGuard.create({onInvalidate:()=>{notifications++;document.querySelector('#editor')?.remove()}});
guard.ready.then(()=>window.ready=true);
</script>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        pages = {'/': parent.encode(), '/editor': editor.encode(),
                 '/away': '<!doctype html><meta charset=utf-8><title>Trang khác</title><h1>Trang khác</h1>'.encode('utf-8'), '/guard.js': guard}
        raw = pages.get(self.path)
        if raw is None:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript' if self.path == '/guard.js' else 'text/html')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'max-age=600')
        self.end_headers()
        self.wfile.write(raw)


async def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    proof = {'passed': False, 'checked_at': datetime.now(timezone.utc).isoformat(),
             'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'guard_sha256': hashlib.sha256(guard).hexdigest(),
             'scope': 'Bfcache Chromium thật; danh tính/editor tổng hợp, không dùng ONLYOFFICE hoặc API đơn vị thật'}
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(channel="chromium",headless=True,args=["--enable-automation"])
            cdp=await browser.new_browser_cdp_session()
            flags=(await cdp.send('Browser.getBrowserCommandLine'))['arguments']
            blocked=[x for x in flags if x=='--disable-back-forward-cache' or (x.startswith('--disable-features=') and 'BackForwardCache' in x)]
            replacements=[]
            for flag in blocked:
                if flag.startswith('--disable-features='):
                    names=[x for x in flag.split('=',1)[1].split(',') if x!='BackForwardCache']
                    if names:replacements.append('--disable-features='+','.join(names))
            proof['default_cache_blockers']=blocked
            await browser.close()
            browser=await p.chromium.launch(channel="chromium",headless=True,ignore_default_args=blocked,args=replacements)
            proof['browser_version'] = browser.version
            page = await browser.new_page()
            diagnostics=await page.context.new_cdp_session(page)
            await diagnostics.send('Page.enable')
            reasons=[]
            diagnostics.on('Page.backForwardCacheNotUsed',lambda value:reasons.extend({k:x.get(k) for k in ('reason','type')} for x in value.get('notRestoredExplanations',[])))
            await page.goto(f'http://127.0.0.1:{server.server_port}/')
            frame = next(f for f in page.frames if f.url.endswith('/editor'))
            await frame.wait_for_function('window.ready===true')
            assert await frame.evaluate('guard.active')
            await frame.locator('#activate').click()
            await page.get_by_role('link', name='Rời trang', exact=True).click()
            await page.get_by_role('heading', name='Trang khác', exact=True).wait_for()
            history=await diagnostics.send('Page.getNavigationHistory')
            assert history['currentIndex']>0
            previous=history['entries'][history['currentIndex']-1]
            assert previous['url']==f'http://127.0.0.1:{server.server_port}/'
            await diagnostics.send('Page.navigateToHistoryEntry',{'entryId':previous['id']})
            # Bfcache không phát DOMContentLoaded mới; đọc context hiện tại của Chrome.
            for _ in range(100):
                value=await diagnostics.send('Runtime.evaluate',{'expression':"document.querySelector('iframe')?.contentWindow?.ready === true",'returnByValue':True})
                if value.get('result',{}).get('value') is True:break
                await asyncio.sleep(.1)
            expression="""(async()=>{
              const child=document.querySelector('iframe').contentWindow;
              let denied=false;try{await child.guard.fetch('/api/tools')}catch(_){denied=true}
              return {events:child.lifecycle,active:child.guard.active,notifications:child.notifications,
                editor_present:!!child.document.querySelector('#editor'),tool_denied:denied,
                tool_called:child.calls.includes('/api/tools')};
            })()"""
            value=await diagnostics.send('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
            assert 'exceptionDetails' not in value
            result=value['result']['value']
            proof['navigation_method']='Lịch sử Chrome thật, không phát sự kiện vòng đời tổng hợp'
            proof.update(result,not_restored_reasons=reasons)
            assert any(x['event'] == 'pageshow' and x['persisted'] for x in result['events']), 'Chrome không phục hồi trang từ bfcache'
            assert not result['active'] and result['notifications'] == 1 and not result['editor_present']
            assert result['tool_denied'] and not result['tool_called']
            proof['passed'] = True
    except Exception as error:
        proof.update(passed=False, error_type=type(error).__name__,
                     reason=(str(error).splitlines() or ['Không có mô tả lỗi'])[0][:160])
    finally:
        if browser is not None:
            with contextlib.suppress(Exception):
                await browser.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
        with args.output.open('x', encoding='utf-8') as output:
            json.dump(proof, output, ensure_ascii=False, indent=2)
        print(json.dumps(proof), flush=True)
    if not proof.get('passed'):
        raise SystemExit(1)


asyncio.run(main())
