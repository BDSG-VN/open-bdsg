"""Authorization code S256 và consent BDSG; nền backend, chưa có HTTP/UI."""
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from mcp_uy_quyen_don_vi import READ_TOOLS, TASK_TOOLS

TOOLS = READ_TOOLS | TASK_TOOLS


class LoiOAuth(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


class OAuthMCPDonVi:
    def __init__(self, kho, authority, sessions, *, origin, clock=time.time):
        self.kho, self.authority, self.sessions = kho, authority, sessions
        self.origin, self.clock = origin.rstrip('/'), clock
        if self.origin+'/mcp' != authority.resource:
            raise ValueError('Issuer và resource OAuth không khớp')
        with kho.ket_noi() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS unit_oauth_clients(
                id TEXT PRIMARY KEY,revision TEXT NOT NULL,document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS unit_oauth_requests(
                hash TEXT PRIMARY KEY,expires REAL NOT NULL,state TEXT NOT NULL,document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS unit_oauth_codes(
                hash TEXT PRIMARY KEY,request_hash TEXT NOT NULL REFERENCES unit_oauth_requests(hash),
                expires REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0,grant_id TEXT NOT NULL DEFAULT '');''')
        authority.oauth_clients = self.require_client

    @staticmethod
    def _redirect(uri):
        if not isinstance(uri, str) or len(uri) > 2048 or not uri.isascii() or any(ord(c) <= 32 for c in uri):
            raise LoiOAuth('invalid_redirect_uri')
        parsed = urlsplit(uri)
        try: port = parsed.port
        except ValueError: raise LoiOAuth('invalid_redirect_uri') from None
        loopback = parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', '::1') and port is not None and port > 0
        if (not parsed.hostname or parsed.username or parsed.password or parsed.fragment
                or (parsed.scheme != 'https' and not loopback)
                or any(key in {'code', 'state', 'iss', 'error', 'error_description'} for key, _ in parse_qsl(parsed.query))):
            raise LoiOAuth('invalid_redirect_uri')
        return uri

    def register_client(self, actor, data):
        if not isinstance(data, dict) or set(data) != {'name', 'redirect_uris', 'allowed_tools'}:
            raise LoiOAuth('invalid_client_metadata')
        name, uris, tools = (data[key] for key in ('name', 'redirect_uris', 'allowed_tools'))
        if (not isinstance(name, str) or not 3 <= len(name.strip()) <= 100 or not name.isprintable()
                or not isinstance(uris, list) or not 1 <= len(uris) <= 10
                or not isinstance(tools, list) or not tools
                or any(not isinstance(tool, str) or tool not in TOOLS for tool in tools)
                or len(set(tools)) != len(tools)):
            raise LoiOAuth('invalid_client_metadata')
        uris = [self._redirect(uri) for uri in uris]
        if len(set(uris)) != len(uris): raise LoiOAuth('invalid_client_metadata')
        identifier, revision = 'bdsg_client_'+secrets.token_urlsafe(18), secrets.token_hex(16)
        document = {'id': identifier, 'name': name.strip(), 'redirect_uris': uris,
                    'allowed_tools': list(tools), 'revision': revision, 'enabled': True,
                    'issuer_epoch': self.authority.issuer_epoch,
                    'token_endpoint_auth_method': 'none'}
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            self._system_actor(actor, db)
            if db.execute('SELECT count(*) FROM unit_oauth_clients').fetchone()[0] >= 256:
                raise LoiOAuth('temporarily_unavailable')
            db.execute('INSERT INTO unit_oauth_clients VALUES(?,?,?)', (identifier, revision, json.dumps(document)))
            self.authority.units._audit(db, actor['id'], 'dang-ky-client-oauth', identifier)
        return document

    def _system_actor(self, actor, db):
        if not isinstance(actor, dict) or 'mcp_delegation' in actor:
            raise PermissionError('Cần chủ quản web để quản lý client OAuth')
        self.authority.units.require_system_admin(actor, db)

    def _client(self, db, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r'bdsg_client_[A-Za-z0-9_-]{24}', identifier):
            raise LoiOAuth('invalid_client')
        row = db.execute('SELECT document FROM unit_oauth_clients WHERE id=?', (identifier,)).fetchone()
        client = json.loads(row[0]) if row else None
        if not client or not client['enabled'] or client.get('issuer_epoch') != self.authority.issuer_epoch:
            raise LoiOAuth('invalid_client')
        return client

    def require_client(self, document, db):
        client = self._client(db, document['client_id'])
        if client['revision'] != document.get('oauth_client_revision'):
            raise LoiOAuth('invalid_client')

    def disable_client(self, actor, identifier):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            self._system_actor(actor, db)
            client = self._client(db, identifier)
            client.update(enabled=False, revision=secrets.token_hex(16))
            db.execute('UPDATE unit_oauth_clients SET revision=?,document=? WHERE id=?',
                       (client['revision'], json.dumps(client), identifier))
            self.authority.units._audit(db, actor['id'], 'ngat-client-oauth', identifier)
        return {'id': identifier, 'enabled': False}

    def start(self, parameters):
        required = {'client_id', 'redirect_uri', 'response_type', 'code_challenge', 'code_challenge_method', 'resource'}
        if not isinstance(parameters, dict) or not required <= set(parameters) or set(parameters)-required-{'scope', 'state'}:
            raise LoiOAuth('invalid_request')
        if parameters['response_type'] != 'code': raise LoiOAuth('unsupported_response_type')
        if parameters['resource'] != self.authority.resource: raise LoiOAuth('invalid_target')
        challenge = parameters['code_challenge']
        if parameters['code_challenge_method'] != 'S256' or not isinstance(challenge, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', challenge):
            raise LoiOAuth('invalid_request')
        state, scope = parameters.get('state', ''), parameters.get('scope', '')
        if (not isinstance(state, str) or len(state) > 512 or not state.isascii()
                or any(ord(c) < 32 for c in state) or not isinstance(scope, str) or len(scope) > 1024):
            raise LoiOAuth('invalid_request')
        tools = [value.removeprefix('tool:') for value in scope.split()] if scope else sorted(READ_TOOLS)
        if (not tools or len(set(tools)) != len(tools)
                or any(value not in TOOLS for value in tools)
                or (scope and any(not value.startswith('tool:') for value in scope.split()))):
            raise LoiOAuth('invalid_scope')
        request = secrets.token_urlsafe(32)
        now = self.clock()
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            client = self._client(db, parameters['client_id'])
            if not scope: tools = sorted(READ_TOOLS & set(client['allowed_tools']))
            if parameters['redirect_uri'] not in client['redirect_uris']: raise LoiOAuth('invalid_redirect_uri')
            if not tools or not set(tools) <= set(client['allowed_tools']): raise LoiOAuth('invalid_scope')
            # Chỉ dọn trạng thái OAuth đã hết hơn thời hạn token tối đa.
            db.execute('DELETE FROM unit_oauth_codes WHERE expires<?', (now-86400,))
            db.execute('DELETE FROM unit_oauth_requests WHERE expires<? AND hash NOT IN (SELECT request_hash FROM unit_oauth_codes)', (now-86400,))
            count = db.execute('SELECT count(*) FROM unit_oauth_requests WHERE expires>?', (now,)).fetchone()[0]
            own = db.execute("SELECT count(*) FROM unit_oauth_requests WHERE expires>? AND json_extract(document,'$.client_id')=?",
                             (now, client['id'])).fetchone()[0]
            total = db.execute('SELECT count(*) FROM unit_oauth_requests').fetchone()[0]
            if count >= 1024 or own >= 128 or total >= 10000: raise LoiOAuth('temporarily_unavailable')
            document = {'client_id': client['id'], 'client_revision': client['revision'], 'redirect_uri': parameters['redirect_uri'],
                'challenge': challenge, 'state': state, 'tools': tools, 'resource': self.authority.resource,
                'state_present': 'state' in parameters,
                'issuer_epoch': self.authority.issuer_epoch, 'expires': now+600}
            db.execute('INSERT INTO unit_oauth_requests VALUES(?,?,?,?)',
                       (_hash(request), now+600, 'pending', json.dumps(document)))
        return {'request': request, 'expires_in': 600}

    def _request(self, db, request, states=('pending', 'bound')):
        if not isinstance(request, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', request):
            raise LoiOAuth('invalid_request')
        row = db.execute('SELECT * FROM unit_oauth_requests WHERE hash=?', (_hash(request),)).fetchone()
        if not row or row['expires'] <= self.clock() or row['state'] not in states: raise LoiOAuth('invalid_request')
        document = json.loads(row['document'])
        client = self._client(db, document['client_id'])
        if document['issuer_epoch'] != self.authority.issuer_epoch or client['revision'] != document['client_revision']:
            raise LoiOAuth('invalid_request')
        return document, client

    def _bound(self, actor, session, document, db):
        current = self.sessions.authorization_reference(actor, session, db)
        owner = self.authority.units.reference(actor, db)
        if document.get('session') != current or document.get('owner_scope') != owner:
            raise PermissionError('Tài khoản, phiên hoặc đơn vị đã thay đổi; cần xin quyền lại')

    def bind(self, actor, session, request):
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            document, client = self._request(db, request)
            if not isinstance(actor, dict) or 'mcp_delegation' in actor:
                raise PermissionError('Cần phiên web để duyệt OAuth')
            if 'session' not in document:
                document['session'] = self.sessions.authorization_reference(actor, session, db)
                document['owner_scope'] = self.authority.units.reference(actor, db)
                db.execute("UPDATE unit_oauth_requests SET state='bound',document=? WHERE hash=?",
                           (json.dumps(document), _hash(request)))
            self._bound(actor, session, document, db)
            return {'request': request, 'client': {'id': client['id'], 'name': client['name']},
                    'tools': document['tools'], 'resource': document['resource'], 'unit_id': document['owner_scope']['unit_id'],
                    'expires': document['expires']}

    @staticmethod
    def _callback(document, **values):
        parsed = urlsplit(document['redirect_uri'])
        pairs = list(values.items())
        if document.get('state_present', bool(document['state'])): pairs.append(('state', document['state']))
        query = parsed.query+('&' if parsed.query else '')+urlencode(pairs)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ''))

    def decide(self, actor, session, request, *, approve, selection=None):
        if type(approve) is not bool: raise LoiOAuth('invalid_request')
        if not isinstance(actor, dict) or 'mcp_delegation' in actor:
            raise PermissionError('Cần phiên web để duyệt OAuth')
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            document, client = self._request(db, request, ('bound',))
            self._bound(actor, session, document, db)
            code = None
            if approve:
                if (not isinstance(selection, dict) or not {'tools', 'project_ids', 'expires_in'} <= set(selection)
                        or set(selection)-{'tools', 'project_ids', 'expires_in', 'task_profile'}
                        or not isinstance(selection['tools'], list)
                        or any(not isinstance(tool, str) or tool not in document['tools'] for tool in selection['tools'])):
                    raise LoiOAuth('invalid_scope')
                data = {**selection, 'name': client['name'], 'client_id': client['id']}
                document['snapshot'] = self.authority.consent_snapshot(actor, data, db)
                document['grant_data'] = data
                code = 'bdsg_c_'+secrets.token_urlsafe(32)
                db.execute('INSERT INTO unit_oauth_codes(hash,request_hash,expires) VALUES(?,?,?)',
                           (_hash(code), _hash(request), min(document['expires'], self.clock()+300)))
            db.execute('UPDATE unit_oauth_requests SET state=?,document=? WHERE hash=?',
                       ('approved' if approve else 'denied', json.dumps(document), _hash(request)))
            self.authority.units._audit(db, actor['id'], 'duyet-oauth' if approve else 'tu-choi-oauth', _hash(request))
        return {'redirect_uri': self._callback(document, **({'code': code, 'iss': self.origin} if approve else {'error': 'access_denied', 'iss': self.origin}))}

    def exchange(self, parameters):
        required = {'grant_type', 'code', 'client_id', 'redirect_uri', 'code_verifier', 'resource'}
        if not isinstance(parameters, dict) or set(parameters) != required:
            raise LoiOAuth('invalid_request')
        if parameters['grant_type'] != 'authorization_code': raise LoiOAuth('unsupported_grant_type')
        verifier, code = parameters['code_verifier'], parameters['code']
        if (not isinstance(verifier, str) or not re.fullmatch(r'[A-Za-z0-9._~-]{43,128}', verifier)
                or not isinstance(code, str) or not re.fullmatch(r'bdsg_c_[A-Za-z0-9_-]{43}', code)):
            raise LoiOAuth('invalid_grant')
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        failure, response = None, None
        with self.kho.ket_noi() as db:
            db.execute('BEGIN IMMEDIATE')
            client = self._client(db, parameters['client_id'])
            row = db.execute('SELECT * FROM unit_oauth_codes WHERE hash=?', (_hash(code),)).fetchone()
            request = db.execute('SELECT document,state FROM unit_oauth_requests WHERE hash=?', (row['request_hash'],)).fetchone() if row else None
            document = json.loads(request['document']) if request else None
            if (not document or document['client_id'] != client['id'] or document['client_revision'] != client['revision']
                    or document['redirect_uri'] != parameters['redirect_uri'] or request['state'] != 'approved'
                    or document['resource'] != parameters['resource'] or document['issuer_epoch'] != self.authority.issuer_epoch
                    or not hmac.compare_digest(challenge, document['challenge'])):
                raise LoiOAuth('invalid_grant')
            if row['used']:
                self.authority.revoke_oauth(row['grant_id'], client['id'], db)
                failure = LoiOAuth('invalid_grant')
            else:
                if row['expires'] <= self.clock(): raise LoiOAuth('invalid_grant')
                try:
                    actor = self.authority.units.restore(document['owner_scope'], db)
                    self.sessions.require_authorization(actor, document['session'], db)
                    issued = self.authority.issue_oauth(actor, document['grant_data'], document['snapshot'], client['revision'], db)
                except (PermissionError, ValueError):
                    raise LoiOAuth('invalid_grant') from None
                db.execute('UPDATE unit_oauth_codes SET used=1,grant_id=? WHERE hash=?', (issued['id'], _hash(code)))
                response = {'access_token': issued['credential'], 'token_type': 'Bearer',
                            'expires_in': document['grant_data']['expires_in'],
                            'scope': ' '.join('tool:'+tool for tool in document['grant_data']['tools'])}
        if failure is not None: raise failure
        return response
