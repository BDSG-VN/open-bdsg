"""Kiểm OAuth bằng danh tính tổng hợp; không dùng tài khoản/token Google thật."""

import concurrent.futures
import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit, urlencode

from dang_nhap_google import DangNhapGoogle, LoiDangNhapGoogle, xac_minh_id_token
from kho import Kho
from may_chu import UngDung, tao_may_chu


class ThuDangNhapGoogle(unittest.TestCase):
    def test_official_verifier_checks_real_rsa_signature_audience_issuer_expiry(self):
        try:
            from google.auth import crypt, jwt
            from google.auth.exceptions import GoogleAuthError
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
        except ImportError:
            self.skipTest('Cần requirements-google-login.txt cho kiểm chữ ký RSA')
        from types import SimpleNamespace
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private = key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        public = key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        signer = crypt.RSASigner.from_string(private, key_id='synthetic-key')
        now = int(time.time())
        payload = {'iss':'https://accounts.google.com','aud':'synthetic-client','sub':'synthetic-sub','iat':now,'exp':now+3600}
        response = SimpleNamespace(status=200,data=json.dumps({'synthetic-key':public}).encode())
        with patch('google.auth.transport.requests.Request',return_value=lambda *a,**kw:response):
            self.assertEqual(xac_minh_id_token(jwt.encode(signer,payload),'synthetic-client')['sub'],'synthetic-sub')
            for changes in [{'aud':'wrong-client'},{'iss':'https://evil.test'},{'exp':now-3600}]:
                with self.subTest(changes=changes), self.assertRaises((ValueError, GoogleAuthError)):
                    xac_minh_id_token(jwt.encode(signer,{**payload,**changes}),'synthetic-client')
            damaged = bytearray(jwt.encode(signer,payload)); damaged[-10] = ord('A') if damaged[-10]!=ord('A') else ord('B')
            with self.assertRaises((ValueError, GoogleAuthError)):xac_minh_id_token(bytes(damaged),'synthetic-client')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.client = 'synthetic.apps.googleusercontent.com'
        (root/'client.json').write_text(json.dumps({'web':{
            'client_id':self.client,'client_secret':'synthetic-secret-not-live',
            'redirect_uris':['https://thanhhoa.bdsg.vn/api/google/callback']}}))
        (root/'invites.json').write_text(json.dumps({'allowed_emails':['tester@example.test']}))
        self.environ = {'BDSG_GOOGLE_CLIENT_FILE':str(root/'client.json'),
                        'BDSG_GOOGLE_LOGIN_FILE':str(root/'invites.json')}
        self.kho = Kho(root/'data')
        self.exchange = Mock(return_value='synthetic-id-token-not-live')
        self.verify = Mock()
        self.login = DangNhapGoogle(self.kho,'https://thanhhoa.bdsg.vn',self.environ,self.exchange,self.verify)

    def begin(self):
        url, binding = self.login.start('127.0.0.1')
        query = parse_qs(urlsplit(url).query)
        now = int(time.time())
        self.verify.return_value = {'iss':'https://accounts.google.com','aud':self.client,
            'sub':'synthetic-subject-001','email':'tester@example.test','email_verified':True,
            'hd':'example.test','iat':now,'exp':now+3600,'nonce':query['nonce'][0],'name':'Người kiểm Google'}
        return query, binding

    def finish(self, query, binding):
        return self.login.callback({'state':query['state'],'code':['synthetic-code']},binding)

    def test_pkce_minimal_scope_single_use_and_operator_session(self):
        query,binding=self.begin()
        self.assertEqual(query['scope'],['openid email profile'])
        self.assertEqual(query['code_challenge_method'],['S256'])
        self.assertEqual(query['access_type'],['online'])
        self.assertNotIn('synthetic-secret-not-live',json.dumps(query))
        token=self.finish(query,binding)
        actor=self.kho.tu_phien(token)
        self.assertEqual(actor['role'],'operator')
        self.assertNotEqual(actor['id'],'chu-quan')
        self.verify.assert_called_once_with('synthetic-id-token-not-live',self.client)
        with self.kho.ket_noi() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM web_users').fetchone()[0],0)
            self.assertNotIn(token,str(db.execute('SELECT * FROM phien').fetchall()))
        with self.assertRaises(LoiDangNhapGoogle):self.finish(query,binding)
        self.assertEqual(self.exchange.call_count,1)

    def test_wrong_browser_does_not_consume_real_state(self):
        query,binding=self.begin()
        with self.assertRaises(LoiDangNhapGoogle):self.finish(query,'wrong-binding-at-least-twenty')
        self.exchange.assert_not_called()
        self.assertTrue(self.kho.tu_phien(self.finish(query,binding)))

    def test_claims_and_invitation_rejections_create_no_identity(self):
        invalids=[{'nonce':'wrong'}, {'iss':'https://evil.test'}, {'aud':'other-client'},
                  {'azp':'other-client'}, {'exp':int(time.time())-1}, {'exp':True},
                  {'iat':int(time.time())+300}, {'email_verified':'true'},
                  {'email':'outsider@example.test'}, {'hd':None}, {'sub':''}]
        for number,changes in enumerate(invalids):
            with self.subTest(changes=changes):
                url,binding=self.login.start('synthetic-ip-'+str(number))
                query=parse_qs(urlsplit(url).query)
                self.verify.return_value={'iss':'https://accounts.google.com','aud':self.client,
                    'sub':'synthetic-subject','email':'tester@example.test','email_verified':True,
                    'hd':'example.test','iat':int(time.time()),'exp':int(time.time())+3600,
                    'nonce':query['nonce'][0],**changes}
                with self.assertRaises(LoiDangNhapGoogle):self.finish(query,binding)
        with self.kho.ket_noi() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM agents').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM phien').fetchone()[0],0)

    def test_google_error_consumed_without_exchange(self):
        query,binding=self.begin()
        with self.assertRaises(LoiDangNhapGoogle):
            self.login.callback({'state':query['state'],'error':['access_denied']},binding)
        with self.assertRaises(LoiDangNhapGoogle):self.finish(query,binding)
        self.exchange.assert_not_called()

    def test_repeated_login_maps_subject_and_revocation_is_final(self):
        query,binding=self.begin()
        actor=self.kho.tu_phien(self.finish(query,binding))
        query,binding=self.begin()
        again=self.kho.tu_phien(self.finish(query,binding))
        self.assertEqual(actor['id'],again['id'])
        self.kho.thu_hoi_agent(actor['id'])
        query,binding=self.begin()
        with self.assertRaises(LoiDangNhapGoogle):self.finish(query,binding)
        with self.kho.ket_noi() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM agents').fetchone()[0],1)

    def test_concurrent_same_state_only_one_exchange(self):
        query,binding=self.begin()
        def call():
            try:return bool(self.finish(query,binding))
            except LoiDangNhapGoogle:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(lambda _:call(),range(2))),[False,True])
        self.assertEqual(self.exchange.call_count,1)

    def test_expired_state_and_duplicate_parameters_are_rejected(self):
        query,binding=self.begin()
        with self.assertRaises(LoiDangNhapGoogle):
            self.login.callback({'state':query['state']*2,'code':['code']},binding)
        with self.kho.ket_noi() as db:db.execute('UPDATE google_login_states SET expires=0')
        with self.assertRaises(LoiDangNhapGoogle):self.finish(query,binding)
        self.exchange.assert_not_called()

    def test_start_burst_is_bounded_and_disabled_is_honest(self):
        for _ in range(8):self.login.start('same-ip')
        with self.assertRaises(LoiDangNhapGoogle):self.login.start('same-ip')
        self.assertTrue(self.login.start('other-ip'))
        disabled=DangNhapGoogle(self.kho,'https://thanhhoa.bdsg.vn',{})
        self.assertFalse(disabled.status()['available'])
        with self.assertRaises(LoiDangNhapGoogle):disabled.start('any-ip')

    def test_exchange_error_never_exposes_code_or_secret(self):
        query,binding=self.begin()
        self.exchange.side_effect=ValueError('synthetic-secret-not-live synthetic-code')
        with self.assertRaises(LoiDangNhapGoogle) as error:self.finish(query,binding)
        self.assertNotIn('synthetic-secret-not-live',str(error.exception))
        self.assertNotIn('synthetic-code',str(error.exception))

    def test_http_origin_cookies_callback_and_kernel_permissions(self):
        app=UngDung(str(Path(self.temp.name)/'http-data'),'https://thanhhoa.bdsg.vn',True)
        self.addCleanup(app.core.audit.close)
        self.addCleanup(app.tasks.close)
        app.google_login=self.login
        # Cùng kho cho phiên HTTP và module đăng nhập.
        self.login.kho=app.kho
        with app.kho.ket_noi() as db:
            for name in ['google_login_states','google_login_identities']:
                with self.kho.ket_noi() as original:
                    sql=original.execute('SELECT sql FROM sqlite_master WHERE name=?',(name,)).fetchone()[0]
                db.execute('DROP TABLE IF EXISTS '+name);db.execute(sql)
        server=tao_may_chu(app,0)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        def close():server.shutdown();server.server_close()
        self.addCleanup(close)
        def request(method,path,body=None,cookie=None,origin=None):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            headers={'Content-Type':'application/json'}
            if origin:headers['Origin']=origin
            if cookie:headers['Cookie']=cookie
            connection.request(method,path,json.dumps(body) if body is not None else None,headers)
            response=connection.getresponse();raw=response.read()
            result=response.status,json.loads(raw) if raw else {},response.getheaders()
            connection.close();return result
        self.assertEqual(request('GET','/api/auth/google')[1],{'available':True,'registration':'invite-only'})
        self.assertEqual(request('POST','/api/auth/google/start',{},origin='https://evil.test')[0],403)
        status,body,headers=request('POST','/api/auth/google/start',{},origin=app.origin)
        self.assertEqual(status,200)
        binding_cookie=next(v for k,v in headers if k=='Set-Cookie')
        self.assertIn('Secure; HttpOnly; SameSite=Lax',binding_cookie)
        query=parse_qs(urlsplit(body['url']).query)
        self.verify.return_value={'iss':'https://accounts.google.com','aud':self.client,
            'sub':'http-subject','email':'tester@example.test','email_verified':True,'hd':'example.test',
            'iat':int(time.time()),'exp':int(time.time())+3600,'nonce':query['nonce'][0]}
        status,_,headers=request('GET','/api/google/callback?'+urlencode({'state':query['state'][0],'code':'synthetic-code'}),cookie=binding_cookie.split(';')[0])
        self.assertEqual(status,303)
        cookies=[v for k,v in headers if k=='Set-Cookie']
        self.assertEqual(len(cookies),2)
        session=next(v for v in cookies if v.startswith('bdsg_session='))
        self.assertIn('Secure; HttpOnly; SameSite=Strict',session)
        status,body,_=request('GET','/api/me',cookie=session.split(';')[0])
        self.assertEqual(body['user']['role'],'operator')
        denied=app.core.goi(body['user'],'mo_hinh.cau_hinh',{})
        self.assertFalse(denied['ok'])


if __name__=='__main__':unittest.main()
