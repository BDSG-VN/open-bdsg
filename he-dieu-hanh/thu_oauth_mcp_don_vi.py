"""OAuth qua interface backend và SQLite thật; không HTTP/consent UI giả."""
import base64
import hashlib
import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import thu_mcp_uy_quyen_don_vi as fixture
from may_chu import UngDung
from mcp_uy_quyen_don_vi import LoiChungThuMCP
from oauth_mcp_don_vi import LoiOAuth
from sao_luu_he_thong import backup, restore


class ThuOAuthMCPDonVi(unittest.TestCase):
    def setUp(self):
        fixture.ThuUyQuyenMCPDonVi.setUp(self)
        self.oauth = self.app.oauth_mcp
        self.oauth.clock = lambda: self.now
        self.app.web_sessions.clock = lambda: self.now
        self.session = self.web_session(fixture.USER)
        self.client = self.oauth.register_client(fixture.OWNER, {'name': 'Client OAuth thu',
            'redirect_uris': ['https://client.test/callback?tenant=synthetic'],
            'allowed_tools': ['du_an.danh_sach', 'cong_viec.tao']})
        self.verifier = 'synthetic-verifier-'+('v'*48)
        self.challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip('=')

    def web_session(self, actor):
        with self.app.kho.ket_noi() as db:
            return self.app.kho.cap_phien(db, actor['id'], self.now)

    def parameters(self, **extra):
        return {'client_id': self.client['id'], 'redirect_uri': self.client['redirect_uris'][0],
                'response_type': 'code', 'resource': self.service.resource,
                'code_challenge': self.challenge, 'code_challenge_method': 'S256',
                'scope': 'tool:du_an.danh_sach', 'state': 'synthetic-state&with=delimiter', **extra}

    def selection(self, **extra):
        return {'tools': ['du_an.danh_sach'], 'project_ids': [self.project], 'expires_in': 900, **extra}

    def pending(self, actor=None, session=None, **extra):
        request = self.oauth.start(self.parameters(**extra))['request']
        self.oauth.bind(actor or self.actor, session or self.session, request)
        return request

    def approve(self, actor=None, session=None, selection=None, **parameters):
        request = self.pending(actor, session, **parameters)
        result = self.oauth.decide(actor or self.actor, session or self.session, request, approve=True,
                                   selection=selection or self.selection())
        callback = parse_qs(urlsplit(result['redirect_uri']).query)
        self.assertEqual(callback['state'], ['synthetic-state&with=delimiter'])
        self.assertEqual(callback['iss'], [self.app.origin])
        self.assertEqual(callback['tenant'], ['synthetic'])
        return callback['code'][0]

    def exchange(self, code, **extra):
        return self.oauth.exchange({'grant_type': 'authorization_code', 'code': code,
            'client_id': self.client['id'], 'redirect_uri': self.client['redirect_uris'][0],
            'code_verifier': self.verifier, 'resource': self.service.resource, **extra})

    def test_consent_pkce_exchange_uses_actual_identity_and_existing_scope_kernel(self):
        token = self.exchange(self.approve())
        actor = self.service.authenticate(token['access_token'])
        self.assertEqual(actor['id'], fixture.USER['id'])
        self.assertEqual(token['scope'], 'tool:du_an.danh_sach')
        self.assertNotIn('refresh_token', token)
        self.assertEqual(self.service.list(self.actor)['grants'][0]['credential_type'], 'oauth_access_token')
        result = self.service.call(actor, 'du_an.danh_sach', {})
        self.assertEqual([row['id'] for row in result['ket_qua']['projects']], [self.project])
        self.assertNotIn('OUTSIDE-PROJECT', json.dumps(result))

    def test_admin_registration_exact_redirect_public_client_and_no_member_bypass(self):
        with self.assertRaises(PermissionError):
            self.oauth.register_client(self.actor, {'name': 'Client khong duoc', 'redirect_uris': ['https://safe.test/cb'],
                'allowed_tools': ['du_an.danh_sach']})
        for uri in ('http://example.test/cb', 'https://user:pass@example.test/cb', 'https://example.test/cb#fragment',
                    'https://example.test/cb?%63ode=pretend', 'https://example.test/cb\r\nLocation: other',
                    'https://[bad-address/callback'):
            with self.subTest(uri=uri), self.assertRaises(LoiOAuth):
                self.oauth.register_client(fixture.OWNER, {'name': 'Client sai callback', 'redirect_uris': [uri],
                    'allowed_tools': ['du_an.danh_sach']})
        native = self.oauth.register_client(fixture.OWNER, {'name': 'Client local thu',
            'redirect_uris': ['http://127.0.0.1:54321/callback'], 'allowed_tools': ['du_an.danh_sach']})
        self.assertEqual(native['token_endpoint_auth_method'], 'none')

    def test_start_rejects_redirect_pkce_resource_scope_and_extra_fields(self):
        for extra in ({'redirect_uri': 'https://client.test/callback?tenant=other'},
                      {'code_challenge_method': 'plain'}, {'resource': 'https://other.test/mcp'},
                      {'scope': 'tool:*'}, {'scope': 'tool:hanh_dong.duyet'},
                      {'actor': fixture.OWNER}, {'client_id': 'pretend'}):
            with self.subTest(extra=extra), self.assertRaises(LoiOAuth): self.oauth.start(self.parameters(**extra))
        request = self.oauth.start(self.parameters(scope=''))['request']
        self.assertEqual(self.oauth.bind(self.actor, self.session, request)['tools'], ['du_an.danh_sach'])

    def test_binding_rejects_different_session_identity_or_unit(self):
        request = self.pending()
        other_session = self.web_session(fixture.USER)
        member_session = self.web_session(fixture.MEMBER)
        for actor, session in ((self.actor, other_session), (self.actor_b, self.session), (self.member, member_session)):
            with self.subTest(identity=actor['id']), self.assertRaises(PermissionError):
                self.oauth.bind(actor, session, request)
        self.assertEqual(self.oauth.bind(self.actor, self.session, request)['unit_id'], self.units[0])

    def test_consent_scope_is_subset_and_cannot_substitute_actor_or_project(self):
        request = self.pending()
        for selection in (self.selection(tools=['cong_viec.tao']), self.selection(project_ids=[self.other_project], actor='pretend'),
                          self.selection(project_ids=['not-a-project'])):
            with self.subTest(selection=selection), self.assertRaises((LoiOAuth, PermissionError, ValueError)):
                self.oauth.decide(self.actor, self.session, request, approve=True, selection=selection)
        self.assertEqual(self.service.list(self.actor)['grants'], [])

    def test_deny_is_terminal_callback_and_no_grant(self):
        request = self.pending()
        result = self.oauth.decide(self.actor, self.session, request, approve=False)
        callback = parse_qs(urlsplit(result['redirect_uri']).query)
        self.assertEqual(callback['error'], ['access_denied'])
        self.assertNotIn('code', callback)
        self.assertEqual(self.service.list(self.actor)['grants'], [])
        with self.assertRaises(LoiOAuth):
            self.oauth.decide(self.actor, self.session, request, approve=True, selection=self.selection())

    def test_callback_preserves_registered_query_encoding(self):
        uri = 'https://client.test/callback?encoded=%2f&empty=&repeated=a&repeated=b'
        client = self.oauth.register_client(fixture.OWNER, {'name': 'Client giu query',
            'redirect_uris': [uri], 'allowed_tools': ['du_an.danh_sach']})
        request = self.pending(client_id=client['id'], redirect_uri=uri)
        result = self.oauth.decide(self.actor, self.session, request, approve=True, selection=self.selection())
        self.assertTrue(result['redirect_uri'].startswith(uri+'&code='), 'Giữ nguyên query callback đã đăng ký')

    def test_empty_state_is_preserved_when_explicitly_requested(self):
        request = self.pending(state='')
        result = self.oauth.decide(self.actor, self.session, request, approve=False)
        self.assertEqual(parse_qs(urlsplit(result['redirect_uri']).query, keep_blank_values=True)['state'], [''])

    def test_oauth_task_profile_runs_with_bound_grant_in_worker(self):
        code = self.approve(scope='tool:cong_viec.tao', selection=self.selection(
            tools=['cong_viec.tao'], task_profile={'allow_ai': False}))
        actor = self.service.authenticate(self.exchange(code)['access_token'])
        result = self.service.call(actor, 'cong_viec.tao', {'prompt': 'Tong hop danh muc qua OAuth backend',
            'project_id': self.project, 'template': 'tong-quan', 'module_ids': []})
        self.assertTrue(result['ok'])
        until = time.monotonic()+5
        while time.monotonic() < until:
            task = self.app.tasks.detail(self.actor, result['ket_qua']['id'])
            if task['status'] in ('completed', 'failed', 'interrupted', 'cancelled'): break
            time.sleep(.01)
        self.assertEqual(task['status'], 'completed')
        self.assertTrue(task['mcp_delegated'])

    def test_pending_requests_are_bounded_and_expired_binding_is_rejected(self):
        first = None
        for _ in range(128):
            request = self.oauth.start(self.parameters())['request']
            first = first or request
        with self.assertRaises(LoiOAuth): self.oauth.start(self.parameters())
        self.now += 601
        with self.assertRaises(LoiOAuth): self.oauth.bind(self.actor, self.session, first)
        self.assertEqual(self.oauth.start(self.parameters())['expires_in'], 600)

    def test_exchange_mismatch_does_not_consume_code_or_issue_grant(self):
        code = self.approve()
        for extra in ({'code_verifier': 'wrong-'+('w'*50)}, {'redirect_uri': 'https://other.test/cb'},
                      {'resource': 'https://other.test/mcp'}, {'owner': 'pretend'}, {'client_id': 'pretend'}):
            with self.subTest(kind=list(extra)), self.assertRaises(LoiOAuth): self.exchange(code, **extra)
        self.assertEqual(self.service.list(self.actor)['grants'], [])
        self.assertEqual(self.exchange(code)['token_type'], 'Bearer')

    def test_code_replay_revokes_issued_token_but_wrong_verifier_does_not(self):
        code = self.approve()
        token = self.exchange(code)['access_token']
        with self.assertRaises(LoiOAuth): self.exchange(code, code_verifier='x'*64)
        self.service.authenticate(token)
        with self.assertRaises(LoiOAuth): self.exchange(code)
        with self.assertRaises(LoiChungThuMCP): self.service.authenticate(token)
        self.assertEqual(len(self.service.list(self.actor)['grants']), 1)

    def test_code_and_request_expiry_no_token(self):
        code = self.approve()
        self.now += 301
        with self.assertRaises(LoiOAuth): self.exchange(code)
        request = self.pending()
        self.now += 601
        with self.assertRaises(LoiOAuth): self.oauth.bind(self.actor, self.session, request)
        self.assertEqual(self.service.list(self.actor)['grants'], [])

    def test_logout_after_consent_blocks_exchange(self):
        code = self.approve()
        self.app.kho.dang_xuat(self.session)
        with self.assertRaises(LoiOAuth): self.exchange(code)
        self.assertEqual(self.service.list(self.actor)['grants'], [])

    def test_membership_change_after_bind_requires_new_request(self):
        request = self.pending()
        self.app.units.set_member(fixture.OWNER, {'unit_id': self.units[0], 'identity': fixture.OWNER['id'], 'role': 'admin'})
        self.app.units.set_member(fixture.OWNER, {'unit_id': self.units[0], 'identity': fixture.USER['id'], 'role': 'member'})
        fresh = self.app.units.bind(fixture.USER, self.units[0])
        with self.assertRaises(PermissionError):
            self.oauth.decide(fresh, self.session, request, approve=True, selection=self.selection())

    def test_project_revoke_regrant_after_consent_does_not_refresh_scope(self):
        grant = {'id': self.project, 'identity': fixture.MEMBER['id']}
        self.app.projects.share(self.actor, {**grant, 'role': 'viewer'})
        session = self.web_session(fixture.MEMBER)
        code = self.approve(self.member, session)
        self.app.projects.share(self.actor, {**grant, 'role': 'revoke'})
        self.app.projects.share(self.actor, {**grant, 'role': 'viewer'})
        with self.assertRaises(LoiOAuth): self.exchange(code)

    def test_mcp_actor_cannot_bind_consent_or_issue_without_snapshot(self):
        request = self.oauth.start(self.parameters())['request']
        issued = fixture.ThuUyQuyenMCPDonVi.grant(self)
        delegated = self.service.authenticate(issued['credential'])
        with self.assertRaises(PermissionError): self.oauth.bind(delegated, self.session, request)
        data = {**self.selection(), 'name': self.client['name'], 'client_id': self.client['id']}
        with self.app.kho.ket_noi() as db, self.assertRaises(PermissionError):
            self.service.issue_oauth(self.actor, data, None, self.client['revision'], db)

    def test_root_mcp_token_cannot_manage_clients_or_consent(self):
        self.app.units.set_member(fixture.OWNER, {'unit_id': self.units[0], 'identity': fixture.OWNER['id'], 'role': 'member'})
        root = self.app.units.bind(fixture.OWNER, self.units[0])
        issued = self.service.create(root, {'name': 'Root doc thu', 'client_id': 'root-read-only',
            'tools': ['nen_tang.danh_sach'], 'project_ids': [], 'expires_in': 900})
        actor = self.service.authenticate(issued['credential'])
        with self.assertRaises(PermissionError):
            self.oauth.register_client(actor, {'name': 'Client khong duoc tao', 'redirect_uris': ['https://safe.test/cb'],
                                               'allowed_tools': ['du_an.danh_sach']})
        with self.assertRaises(PermissionError): self.oauth.disable_client(actor, self.client['id'])
        with self.assertRaises(PermissionError): self.oauth.decide(actor, self.session, self.pending(), approve=False)

    def test_client_disable_blocks_pending_codes_and_active_tokens(self):
        code = self.approve()
        token = self.exchange(code)['access_token']
        pending_code = self.approve()
        self.oauth.disable_client(fixture.OWNER, self.client['id'])
        with self.assertRaises(LoiOAuth): self.exchange(pending_code)
        with self.assertRaises(LoiChungThuMCP): self.service.authenticate(token)

    def test_exchange_failure_rolls_back_grant_and_code_consumption(self):
        code = self.approve()
        original = self.service.issue_oauth
        def fail_after_insert(*args):
            original(*args)
            raise RuntimeError('Loi DB tong hop sau tao grant')
        self.service.issue_oauth = fail_after_insert
        with self.assertRaises(RuntimeError): self.exchange(code)
        self.assertEqual(self.service.list(self.actor)['grants'], [])
        self.service.issue_oauth = original
        self.assertEqual(self.exchange(code)['token_type'], 'Bearer')

    def test_concurrent_exchange_mints_once_replay_revokes_first(self):
        code = self.approve()
        def exchange():
            try: return self.exchange(code)
            except LoiOAuth as error: return {'error': error.code}
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: exchange(), range(2)))
        self.assertEqual(sum('access_token' in outcome for outcome in outcomes), 1)
        token = next(outcome['access_token'] for outcome in outcomes if 'access_token' in outcome)
        with self.assertRaises(LoiChungThuMCP): self.service.authenticate(token)
        self.assertEqual(len(self.service.list(self.actor)['grants']), 1)

    def test_codes_tokens_and_sessions_not_in_metadata_snapshot_or_audit(self):
        request = self.pending()
        response = self.oauth.decide(self.actor, self.session, request, approve=True, selection=self.selection())
        code = parse_qs(urlsplit(response['redirect_uri']).query)['code'][0]
        token = self.exchange(code)['access_token']
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder)/'bundle'
            backup(self.app.kho.root, bundle)
            raw = (bundle/'data/van-hanh.db').read_bytes()
            for credential in (request, code, token, self.session):
                self.assertTrue(credential.encode() not in raw, 'Snapshot không chứa credential thô')
                self.assertTrue(credential not in json.dumps(self.service.list(self.actor)), 'Metadata không chứa credential thô')
                self.assertTrue(credential not in (self.app.kho.root/'nhat-ky-nhan.jsonl').read_text(), 'Audit không chứa credential thô')

    def test_restart_keeps_valid_code_and_restore_rejects_old_code_client(self):
        code = self.approve()
        restarted = UngDung(self.app.kho.root, self.app.origin, True, unit_preview=True)
        try:
            result = restarted.oauth_mcp.exchange({'grant_type': 'authorization_code', 'code': code,
                'client_id': self.client['id'], 'redirect_uri': self.client['redirect_uris'][0],
                'code_verifier': self.verifier, 'resource': self.service.resource})
            restarted.inbound_mcp.authenticate(result['access_token'])
        finally:
            restarted.tasks.close(); restarted.core.audit.close()
        code = self.approve()
        with tempfile.TemporaryDirectory() as folder:
            bundle, target = Path(folder)/'bundle', Path(folder)/'restored'
            backup(self.app.kho.root, bundle)
            restore(bundle, target)
            restored = UngDung(target/'data', self.app.origin, True, unit_preview=True)
            try:
                with self.assertRaises(LoiOAuth):
                    restored.oauth_mcp.exchange({'grant_type': 'authorization_code', 'code': code,
                        'client_id': self.client['id'], 'redirect_uri': self.client['redirect_uris'][0],
                        'code_verifier': self.verifier, 'resource': self.service.resource})
            finally:
                restored.tasks.close(); restored.core.audit.close()


if __name__ == '__main__': unittest.main()
