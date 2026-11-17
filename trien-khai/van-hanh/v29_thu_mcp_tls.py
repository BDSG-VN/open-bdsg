"""Hồi quy TLS/slow-header MCP trong namespace riêng; chỉ dữ liệu tổng hợp.

Chạy bằng root trên Linux có systemd. Không sửa mạng host: xác minh namespace
và loopback trước mọi thao tác IP; không có endpoint hoặc chứng thư thật.
"""
import json
import os
import pathlib
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def run(host_netns):
    assert os.readlink('/proc/self/ns/net') != host_netns, 'Refuse host network changes'
    links=json.loads(subprocess.check_output(['ip','-j','link']))
    assert len(links)==1 and links[0]['ifname']=='lo', 'Require fresh loopback-only namespace'
    subprocess.run(['ip','link','set','lo','up'],check=True)
    subprocess.run(['ip','addr','add','1.1.1.1/32','dev','lo'],check=True)
    assert not json.loads(subprocess.check_output(['ip','-j','route','show','default']))
    sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'he-dieu-hanh'))
    from mcp_truyen_tai import TruyenTaiMCP

    with tempfile.TemporaryDirectory(prefix='bdsg-r8-tls-') as folder:
        root=pathlib.Path(folder)
        cert,key=root/'cert.pem',root/'key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
            '-subj','/CN=crm.bdsg.vn','-addext','subjectAltName=DNS:crm.bdsg.vn',
            '-keyout',str(key),'-out',str(cert)],check=True,capture_output=True)
        requests=[]
        token='synthetic-tls-key-never-live'
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args):pass
            def do_POST(self):
                assert self.headers.get('Authorization')=='Bearer '+token
                request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(request['method'])
                if self.path=='/slow-header':
                    try:
                        self.wfile.write(b'HTTP/1.0 200 OK\r\nX-Slow: ');self.wfile.flush()
                        for _ in range(100):
                            self.wfile.write(b'x');self.wfile.flush();time.sleep(.05)
                        self.wfile.write(b'\r\nContent-Length: 0\r\n\r\n');self.wfile.flush()
                    except (BrokenPipeError,ConnectionResetError,ssl.SSLError):pass
                    return
                if self.path=='/redirect':
                    self.send_response(302);self.send_header('Location','https://other.bdsg.vn/mcp');self.end_headers();return
                if request['method']=='notifications/initialized':
                    self.send_response(202);self.send_header('Content-Length','0');self.end_headers();return
                result=({'protocolVersion':'2025-06-18','capabilities':{}} if request['method']=='initialize' else
                    {'tools':[{'name':'crm.list'}]} if request['method']=='tools/list' else
                    {'content':[{'type':'text','text':'Kết quả tổng hợp TLS'}]})
                body=json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result},ensure_ascii=False).encode()
                streaming=request['method']=='tools/call'
                if streaming:body=b'data: '+body+b'\n\n'
                self.send_response(200)
                self.send_header('Content-Type','text/event-stream' if streaming else 'application/json')
                self.send_header('Mcp-Session-Id','synthetic-tls-session')
                self.send_header('Content-Length',str(len(body)))
                self.send_header('Connection','close');self.end_headers();self.wfile.write(body)
            def do_DELETE(self):
                assert self.headers.get('Authorization')=='Bearer '+token
                requests.append('DELETE');self.send_response(204);self.end_headers()
        server=ThreadingHTTPServer(('1.1.1.1',443),Handler)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
        server.socket=context.wrap_socket(server.socket,server_side=True)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        os.environ['SSL_CERT_FILE']=str(cert)
        os.environ['HTTPS_PROXY']='http://127.0.0.1:9'
        resolutions=[]
        def resolve(host,*_args,**_options):
            resolutions.append(host);return [(2,1,6,'',('1.1.1.1',443))]
        config={'url':'https://crm.bdsg.vn/mcp','token':token}
        transport=TruyenTaiMCP(resolver=resolve)
        try:
            result=transport.goi(config,'tools/list',{},lambda:None)
            assert result=={'tools':[{'name':'crm.list'}]}
            assert requests==['initialize','notifications/initialized','tools/list','DELETE']
            assert resolutions==['crm.bdsg.vn']
            result=transport.goi(config,'tools/call',{'name':'crm.list','arguments':{}},lambda:None)
            assert result['content'][0]['text']=='Kết quả tổng hợp TLS'
            before=len(requests)
            try:transport.goi({**config,'url':'https://wrong.bdsg.vn/mcp'},'tools/list',{},lambda:None)
            except ssl.SSLCertVerificationError:pass
            else:raise AssertionError('Wrong hostname accepted')
            assert len(requests)==before
            del os.environ['SSL_CERT_FILE']
            try:transport.goi(config,'tools/list',{},lambda:None)
            except ssl.SSLCertVerificationError:pass
            else:raise AssertionError('Untrusted certificate accepted')
            assert len(requests)==before
            os.environ['SSL_CERT_FILE']=str(cert)
            try:transport.goi({**config,'url':'https://crm.bdsg.vn/redirect'},'tools/list',{},lambda:None)
            except ValueError:pass
            else:raise AssertionError('Redirect accepted')
            assert len(requests)==before+1
            blocked=TruyenTaiMCP(resolver=lambda *_args,**_options:[(2,1,6,'',('127.0.0.1',443))])
            try:blocked.goi(config,'tools/list',{},lambda:None)
            except PermissionError:pass
            else:raise AssertionError('Private IP accepted')
            assert len(requests)==before+1
            started=time.monotonic()
            try:TruyenTaiMCP(resolver=resolve,timeout=1).goi({**config,'url':'https://crm.bdsg.vn/slow-header'},'tools/list',{},lambda:None)
            except (OSError,ValueError):pass
            else:raise AssertionError('Slow header accepted')
            elapsed=time.monotonic()-started
            assert elapsed<2, {'slow_header_exceeded_deadline_seconds':elapsed}
            print(json.dumps({'status':'ok','data':'synthetic-only','network_namespace_private':True,
                'external_routes':False,'real_tls_http_json_and_sse':True,'hostname_mismatch_denied_before_http':True,
                'untrusted_ca_denied_before_http':True,'proxy_environment_ignored':True,'redirect_not_followed':True,
                'private_dns_denied':True,'ip_pinned_with_original_hostname_tls':True,'real_bdsg_endpoint_tested':False,
                'slow_header_deadline_enforced':True,'slow_header_elapsed_seconds':round(elapsed,3)}))
        finally:
            server.shutdown();server.server_close()

def main():
    if len(sys.argv)==3 and sys.argv[1]=='--in-namespace':
        run(sys.argv[2]);return
    if len(sys.argv)!=1 or sys.platform!='linux' or os.geteuid()!=0:
        raise SystemExit('Cần root trên Linux/systemd để tạo mạng kiểm thử cô lập')
    args=['systemd-run','--quiet','--wait','--pipe','--collect',
        '--unit=bdsg-mcp-tls-check-'+str(os.getpid())]
    properties={'PrivateNetwork':'yes','PrivateTmp':'yes','NoNewPrivileges':'yes',
        'CapabilityBoundingSet':'CAP_NET_ADMIN CAP_NET_BIND_SERVICE','ProtectHome':'read-only',
        'ProtectSystem':'strict','PrivateDevices':'yes','ProtectKernelTunables':'yes',
        'ProtectKernelModules':'yes','ProtectControlGroups':'yes','UMask':'0077',
        'RuntimeMaxSec':'60','KillMode':'control-group','LimitCORE':'0',
        'InaccessiblePaths':'-/var/lib/bdsg-thanhhoa -/etc/bdsg-thanhhoa /root'}
    for key,value in properties.items():args+=['--property='+key+'='+value]
    args += [sys.executable,'-B',str(pathlib.Path(__file__).resolve()),'--in-namespace',os.readlink('/proc/self/ns/net')]
    result=subprocess.run(args,capture_output=True,timeout=75)
    sys.stdout.buffer.write(result.stdout);sys.stderr.buffer.write(result.stderr)
    raise SystemExit(result.returncode)

if __name__=='__main__':main()
