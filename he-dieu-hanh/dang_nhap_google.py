"""Đăng nhập Google công khai hoặc theo lời mời; chỉ cấp quyền người dùng."""

import base64
import hashlib
import hmac
import http.client
import json
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

from kho import bam


class LoiDangNhapGoogle(ValueError):
    """Thông báo cố định, không kèm authorization code hoặc token Google."""


def xac_minh_id_token(token, client_id):
    # Dùng bộ kiểm chữ ký/issuer/audience/expiry chính thức của Google.
    import requests
    from google.auth.transport.requests import Request
    from google.oauth2.id_token import verify_oauth2_token

    with requests.Session() as session:
        session.trust_env = False
        request = Request(session=session)

        def limited_request(*args, **kwargs):
            kwargs['timeout'] = 10
            return request(*args, **kwargs)

        return verify_oauth2_token(token, limited_request, audience=client_id)


class DangNhapGoogle:
    def __init__(self, kho, origin, environ=None, exchange=None, verify=None):
        self.kho = kho
        self.redirect = origin.rstrip('/') + '/api/google/callback'
        self.exchange = exchange or self._exchange
        self.verify = verify or xac_minh_id_token
        self.config = None
        self.invites = set()
        self.registration = 'invite-only'
        self.max_accounts = 100
        env = os.environ if environ is None else environ
        try:
            settings = json.loads(Path(env['BDSG_GOOGLE_LOGIN_FILE']).read_text())
            client = json.loads(Path(env['BDSG_GOOGLE_CLIENT_FILE']).read_text())
            if not isinstance(settings, dict) or not isinstance(client, dict):
                raise ValueError()
            client = client.get('web', client)
            if not isinstance(client, dict):
                raise ValueError()
            mode = settings.get('registration', 'invite-only')
            emails = settings.get('allowed_emails', [])
            capacity = settings.get('max_accounts', 1000 if mode == 'public' else 100)
            if (
                set(settings) - {'allowed_emails', 'registration', 'max_accounts'}
                or mode not in ('invite-only', 'public')
                or type(capacity) is not int or not 1 <= capacity <= 100000
                or not isinstance(emails, list) or len(emails) > 100
                or (mode == 'invite-only' and not emails)
                or any(not isinstance(e, str) or not re.fullmatch(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', e) for e in emails)
                or not isinstance(client.get('client_id'), str)
                or not client['client_id'].endswith('.apps.googleusercontent.com')
                or not isinstance(client.get('client_secret'), str) or not client['client_secret']
                or self.redirect not in client['redirect_uris']
            ):
                raise ValueError()
            if verify is None:
                import google.oauth2.id_token  # noqa: F401
                import google.auth.transport.requests  # noqa: F401
            self.config = client
            self.invites = {e.lower() for e in emails}
            self.registration = mode
            self.max_accounts = capacity
        except (KeyError, OSError, TypeError, ValueError, ImportError):
            pass
        with kho.ket_noi() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS google_login_states(
                    state TEXT PRIMARY KEY,binding TEXT NOT NULL,verifier TEXT NOT NULL,
                    nonce TEXT NOT NULL,ip TEXT NOT NULL,expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS google_login_identities(
                    issuer TEXT NOT NULL,subject TEXT NOT NULL,actor TEXT UNIQUE NOT NULL,
                    email TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(issuer,subject));
            ''')

    def status(self):
        return {'available': self.config is not None, 'registration': self.registration}

    def start(self, ip):
        if not self.config:
            raise LoiDangNhapGoogle('Đăng nhập Google chưa được cấu hình')
        now = time.time()
        state = 'login.' + secrets.token_urlsafe(32)
        binding, verifier, nonce = [secrets.token_urlsafe(32) for _ in range(3)]
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM google_login_states WHERE expires<?', (now,))
            count = db.execute('SELECT count(*) FROM google_login_states').fetchone()[0]
            own = db.execute('SELECT count(*) FROM google_login_states WHERE ip=?', (bam(ip),)).fetchone()[0]
            if count >= 100 or own >= 8:
                raise LoiDangNhapGoogle('Có nhiều yêu cầu đăng nhập; vui lòng thử lại sau')
            db.execute('INSERT INTO google_login_states VALUES (?,?,?,?,?,?)',
                       (bam(state), bam(binding), verifier, bam(nonce), bam(ip), now+600))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
            'client_id': self.config['client_id'], 'redirect_uri': self.redirect,
            'response_type': 'code', 'scope': 'openid email profile',
            'state': state, 'nonce': nonce, 'code_challenge': challenge,
            'code_challenge_method': 'S256', 'access_type': 'online',
            'prompt': 'select_account', 'include_granted_scopes': 'false',
        })
        return url, binding

    def _exchange(self, code, verifier):
        body = urlencode({'code': code, 'code_verifier': verifier,
            'client_id': self.config['client_id'], 'client_secret': self.config['client_secret'],
            'redirect_uri': self.redirect, 'grant_type': 'authorization_code'})
        connection = http.client.HTTPSConnection('oauth2.googleapis.com', timeout=15)
        try:
            connection.request('POST', '/token', body, {'Content-Type':'application/x-www-form-urlencoded'})
            response = connection.getresponse()
            raw = response.read(65537)
            if response.status != 200 or len(raw) > 65536:
                raise ValueError()
            data = json.loads(raw)
            token = data.get('id_token')
            if not isinstance(token, str) or not 10 <= len(token) <= 16000:
                raise ValueError()
            return token
        finally:
            connection.close()

    def callback(self, query, binding):
        if not self.config:
            raise LoiDangNhapGoogle('Đăng nhập Google chưa được cấu hình')
        state = query.get('state', [])
        code = query.get('code', [])
        if (len(state) != 1 or not state[0].startswith('login.') or len(state[0]) > 150
                or not isinstance(binding, str) or not 20 <= len(binding) <= 150):
            raise LoiDangNhapGoogle('Phiên đăng nhập Google không hợp lệ')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM google_login_states WHERE state=? AND expires>?',
                             (bam(state[0]), time.time())).fetchone()
            if not row or not hmac.compare_digest(row['binding'], bam(binding)):
                raise LoiDangNhapGoogle('Phiên đăng nhập Google đã hết hạn hoặc không khớp')
            # State dùng một lần kể cả Google từ chối, tránh đổi mã hai lần đồng thời.
            db.execute('DELETE FROM google_login_states WHERE state=?', (bam(state[0]),))
        if 'error' in query or len(code) != 1 or not 1 <= len(code[0]) <= 4096:
            raise LoiDangNhapGoogle('Đăng nhập Google chưa được hoàn tất')
        try:
            claims = self.verify(self.exchange(code[0], row['verifier']), self.config['client_id'])
            subject, email = claims['sub'], claims['email']
            if (claims.get('iss') not in ('accounts.google.com', 'https://accounts.google.com')
                    or claims.get('aud') != self.config['client_id']
                    or claims.get('azp', self.config['client_id']) != self.config['client_id']
                    or type(claims.get('exp')) is not int or claims['exp'] <= time.time()
                    or type(claims.get('iat')) is not int or not time.time()-720 <= claims['iat'] <= time.time()+30
                    or not isinstance(subject, str) or not re.fullmatch(r'[\x21-\x7e]{1,255}', subject)
                    or not isinstance(email, str) or not 3 <= len(email) <= 254 or '@' not in email
                    or claims.get('email_verified') is not True
                    or (self.registration == 'invite-only' and (
                        email.lower() not in self.invites
                        or (not email.lower().endswith('@gmail.com') and not claims.get('hd'))))
                    or not isinstance(claims.get('nonce'), str)
                    or not hmac.compare_digest(bam(claims['nonce']), row['nonce'])):
                raise ValueError()
        except Exception:
            raise LoiDangNhapGoogle('Không xác nhận được tài khoản Google hoặc tài khoản không được phép đăng nhập') from None
        issuer = 'https://accounts.google.com'
        now = time.time()
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            identity = db.execute('SELECT actor FROM google_login_identities WHERE issuer=? AND subject=?',
                                  (issuer, subject)).fetchone()
            if identity:
                actor = identity['actor']
                active = db.execute("SELECT 1 FROM agents WHERE ma=? AND active=1 AND role='operator'", (actor,)).fetchone()
                if not active:
                    raise LoiDangNhapGoogle('Tài khoản BDSG đã bị thu hồi')
            else:
                actor = 'google-' + hashlib.sha256((issuer+'|'+subject).encode()).hexdigest()[:32]
                if db.execute('SELECT count(*) FROM google_login_identities').fetchone()[0] >= self.max_accounts:
                    raise LoiDangNhapGoogle('Chưa thể tạo thêm tài khoản Google')
                name = claims.get('name', 'Người dùng Google')
                if not isinstance(name, str):
                    name = 'Người dùng Google'
                name = ''.join(c for c in name if ord(c) >= 32)[:100].strip() or 'Người dùng Google'
                db.execute('INSERT INTO agents(ma,ten,role,token_hash) VALUES (?,?,?,?)',
                           (actor, name, 'operator', bam(secrets.token_urlsafe(40))))
                db.execute('INSERT INTO google_login_identities VALUES (?,?,?,?,?)',
                           (issuer, subject, actor, email.lower(), now))
            token = self.kho.cap_phien(db, actor, now)
        self.kho.su_kien(actor, 'dang-nhap-google')
        return token
