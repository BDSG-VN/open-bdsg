"""Yêu cầu kinh doanh qua nhân thật trên dữ liệu tổng hợp tạm."""
import tempfile
import unittest
from pathlib import Path

from may_chu import UngDung
from sao_luu_he_thong import backup, restore


class ThuKinhDoanhDonVi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = UngDung(self.tmp.name, 'https://business.test', True, unit_preview=True)
        self.addCleanup(self.close)
        self.root = {'id': 'chu-quan', 'role': 'quan-tri', 'name':'Chu quan'}
        self.app.kho.tao_chu('synthetic-password-only')
        for identity in ('nguoi-a', 'nguoi-b', 'nguoi-c'):
            self.app.kho.tao_agent(identity, identity, 'operator')
        self.units = [self.app.units.create(self.root, {'name': 'Don vi '+name, 'admin': 'nguoi-a'})['id']
                      for name in ('A', 'B')]
        for unit in self.units:
            for identity in ('nguoi-b', 'nguoi-c'):
                self.app.units.set_member(self.actor('nguoi-a', unit),
                    {'unit_id': unit, 'identity': identity, 'role': 'member'})

    def close(self):
        self.app.tasks.close()
        self.app.core.audit.close()
        self.tmp.cleanup()

    def actor(self, identity, unit=None):
        return self.app.units.bind({'id': identity, 'role': 'operator', 'name': identity}, unit or self.units[0])

    def call(self, actor, tool, args=None):
        return self.app.core.goi(actor, tool, args or {})

    def value(self, actor, tool, args=None):
        result = self.call(actor, tool, args)
        self.assertTrue(result.get('ok'), result)
        return result['ket_qua']

    def create(self, actor, **extra):
        return self.value(actor, 'kinh_doanh.tao_yeu_cau',
            {'title': 'Yeu cau thu nghiem', 'sector': 'thuong-mai',
             'description': 'Noi dung tong hop de kiem thu', **extra})

    def test_project_request_uses_live_cross_unit_grants(self):
        b = self.actor('nguoi-b')
        c = self.actor('nguoi-c', self.units[1])
        project = self.value(b, 'du_an.tao', {'name': 'Du an kinh doanh chung'})['id']
        request = self.create(b, project_id=project)
        share = {'id': project, 'identity': 'nguoi-c', 'unit_id': self.units[1]}
        self.value(b, 'don_vi.chia_se_du_an', {**share, 'role': 'viewer'})
        self.assertEqual([r['id'] for r in self.value(c, 'kinh_doanh.danh_sach')['requests']], [request['id']])
        change = {'id': request['id'], 'stage': 'van-hanh'}
        self.assertFalse(self.call(c, 'kinh_doanh.doi_chang', change).get('ok'))
        self.assertFalse(self.call(c, 'kinh_doanh.tao_yeu_cau',
            {'project_id': project, 'title': 'Khong duoc tao', 'sector': 'thuong-mai',
             'description': 'Noi dung cua nguoi chi doc'}).get('ok'))
        self.value(b, 'don_vi.chia_se_du_an', {**share, 'role': 'editor'})
        self.assertEqual(self.value(c, 'kinh_doanh.doi_chang', change)['stage'], 'van-hanh')
        second = self.create(c, project_id=project)
        self.assertEqual({r['id'] for r in self.value(b, 'kinh_doanh.danh_sach')['requests']},
                         {request['id'], second['id']})
        self.value(b, 'don_vi.chia_se_du_an', {**share, 'role': 'revoke'})
        self.assertEqual(self.value(c, 'kinh_doanh.danh_sach')['requests'], [])
        self.assertFalse(self.call(c, 'kinh_doanh.doi_chang', {'id':second['id'], 'stage':'tu-van'}).get('ok'))
        self.assertEqual(self.value(self.actor('nguoi-a'), 'kinh_doanh.danh_sach')['requests'], [])

    def test_membership_rejoin_hides_personal_requests_and_revoked_project_grant(self):
        b, a = self.actor('nguoi-b'), self.actor('nguoi-a')
        old = self.create(b)
        project = self.value(a, 'du_an.tao', {'name':'Du an thu hoi quyen'})['id']
        self.create(a, project_id=project)
        self.value(a, 'don_vi.chia_se_du_an', {'id':project, 'identity':'nguoi-b',
                    'unit_id':self.units[0], 'role':'editor'})
        self.assertEqual(len(self.value(b, 'kinh_doanh.danh_sach')['requests']), 2)
        member = {'unit_id':self.units[0], 'identity':'nguoi-b'}
        self.app.units.set_member(a, {**member, 'role':'revoke'})
        self.assertFalse(self.call(b, 'kinh_doanh.danh_sach').get('ok'))
        self.app.units.set_member(a, {**member, 'role':'member'})
        self.assertFalse(self.call(b, 'kinh_doanh.danh_sach').get('ok'))
        fresh = self.actor('nguoi-b')
        self.assertEqual(self.value(fresh, 'kinh_doanh.danh_sach')['requests'], [])
        self.assertFalse(self.call(fresh, 'kinh_doanh.doi_chang', {'id':old['id'], 'stage':'van-hanh'}).get('ok'))
        self.create(fresh)
        self.assertEqual(len(self.value(fresh, 'kinh_doanh.danh_sach')['requests']), 1)

    def test_archive_validation_and_write_gate_preserve_content(self):
        b = self.actor('nguoi-b')
        project = self.value(b, 'du_an.tao', {'name':'Du an luu tru'})['id']
        created = self.create(b, project_id=project)
        self.value(b, 'du_an.luu_tru', {'id':project})
        payload = {'title':'Yeu cau thu', 'sector':'thuong-mai', 'description':'Noi dung de kiem thu'}
        self.assertFalse(self.call(b, 'kinh_doanh.tao_yeu_cau', {**payload,'project_id':project}).get('ok'))
        self.assertFalse(self.call(b, 'kinh_doanh.doi_chang', {'id':created['id'],'stage':'van-hanh'}).get('ok'))
        self.assertEqual(self.value(b, 'kinh_doanh.danh_sach')['requests'][0]['stage'], 'tu-van')
        self.value(b, 'du_an.khoi_phuc', {'id':project})
        for extra in ({'owner':'nguoi-a'}, {'unit_id':self.units[1]}, {'title':'x'},
                      {'sector':'khong-co'}, {'description':'ngan'}, {'project_id':37}):
            self.assertFalse(self.call(b, 'kinh_doanh.tao_yeu_cau', {**payload, **extra}).get('ok'))
        self.assertFalse(self.call(b, 'kinh_doanh.doi_chang', {'id':created['id'],'stage':'khong-co'}).get('ok'))
        self.app.core.nhan.chinh_sach.cong_ghi.dong()
        self.assertFalse(self.call(b, 'kinh_doanh.tao_yeu_cau', payload).get('ok'))
        self.assertFalse(self.call(b, 'kinh_doanh.doi_chang', {'id':created['id'],'stage':'van-hanh'}).get('ok'))
        self.assertEqual(len(self.value(b, 'kinh_doanh.danh_sach')['requests']), 1)

    def test_backup_restore_keeps_scope_without_legacy_mix(self):
        b = self.actor('nguoi-b')
        created = self.create(b)
        self.app.kho.tao_yeu_cau('nguoi-b', {'title':'Yeu cau legacy', 'sector':'cong-nghe',
                                          'description':'Du lieu cu khong duoc tron'})
        with tempfile.TemporaryDirectory() as area:
            bundle, restored = Path(area)/'bundle', Path(area)/'restored'
            backup(self.app.kho.root, bundle)
            restore(bundle, restored)
            other = UngDung(restored/'data', 'https://business.test', True, unit_preview=True)
            try:
                for unit, expected in ((self.units[0], [created['id']]), (self.units[1], [])):
                    actor = other.units.bind({'id':'nguoi-b', 'role':'operator', 'name':'Nguoi B'}, unit)
                    result = other.core.goi(actor, 'kinh_doanh.danh_sach', {})
                    self.assertTrue(result.get('ok'), result)
                    self.assertEqual([r['id'] for r in result['ket_qua']['requests']], expected)
            finally:
                other.tasks.close()
                other.core.audit.close()

    def test_personal_request_is_private_to_unit_and_creator(self):
        b = self.actor('nguoi-b')
        request = self.create(b)
        rows = self.value(b, 'kinh_doanh.danh_sach')['requests']
        self.assertEqual([r['id'] for r in rows], [request['id']])
        self.assertEqual(rows[0]['stage'], 'tu-van')
        for other in (self.actor('nguoi-a'), self.actor('nguoi-c'), self.actor('nguoi-b', self.units[1])):
            self.assertEqual(self.value(other, 'kinh_doanh.danh_sach')['requests'], [])
            self.assertFalse(self.call(other, 'kinh_doanh.doi_chang',
                {'id': request['id'], 'stage': 'kinh-doanh'}).get('ok'))
        changed = self.value(b, 'kinh_doanh.doi_chang', {'id': request['id'], 'stage': 'trien-khai'})
        self.assertEqual(changed['stage'], 'trien-khai')
        self.assertFalse(self.call(self.root, 'kinh_doanh.danh_sach').get('ok'))


if __name__ == '__main__':
    unittest.main()
