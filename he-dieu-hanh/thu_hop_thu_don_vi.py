"""Hộp thư qua nhân thật trên SQLite tạm, không dùng dữ liệu khách."""
import tempfile
import unittest

from may_chu import UngDung
from sao_luu_he_thong import backup, restore
from pathlib import Path


class ThuHopThuDonVi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = UngDung(self.tmp.name, 'https://mailbox.test', True, unit_preview=True)
        self.addCleanup(self.close)
        self.root = {'id': 'chu-quan', 'role': 'quan-tri'}
        self.app.kho.tao_chu('synthetic-password-only')
        for identity in ('nguoi-a', 'nguoi-b', 'nguoi-c'):
            self.app.kho.tao_agent(identity, identity, 'operator')
        self.units = [self.app.units.create(self.root, {'name': 'Don vi '+name, 'admin': 'nguoi-a'})['id']
                      for name in ('A', 'B')]
        for unit in self.units:
            admin = self.actor('nguoi-a', unit)
            for identity in ('nguoi-b', 'nguoi-c'):
                self.app.units.set_member(admin, {'unit_id': unit, 'identity': identity, 'role': 'member'})

    def close(self):
        self.app.tasks.close()
        self.app.core.audit.close()
        self.tmp.cleanup()

    def actor(self, identity, unit=None):
        return self.app.units.bind({'id': identity, 'name': identity, 'role': 'operator'}, unit or self.units[0])

    def call(self, actor, tool, args=None):
        return self.app.core.goi(actor, tool, args or {})

    def value(self, actor, tool, args=None):
        result = self.call(actor, tool, args)
        self.assertTrue(result.get('ok'), result)
        return result['ket_qua']

    def test_mail_stays_in_unit_and_admin_cannot_read_others(self):
        a, b, c = (self.actor(name) for name in ('nguoi-a', 'nguoi-b', 'nguoi-c'))
        sent = self.value(b, 'agent.gui_tin', {'recipient': 'nguoi-c', 'body': 'Thu rieng trong don vi A'})
        self.assertEqual(self.value(c, 'agent.doc_hop_thu')['messages'][0]['id'], sent['id'])
        self.assertEqual(self.value(a, 'agent.doc_hop_thu'), {'messages': []})
        other = self.actor('nguoi-b', self.units[1])
        self.assertEqual(self.value(other, 'agent.doc_hop_thu'), {'messages': []})

    def test_directory_and_recipient_stay_in_membership(self):
        a = self.actor('nguoi-a')
        self.app.kho.tao_agent('ngoai-don-vi', 'Ngoai', 'operator')
        directory = self.value(a, 'agent.danh_sach')['agents']
        self.assertEqual({row['id'] for row in directory}, {'nguoi-a','nguoi-b','nguoi-c'})
        self.assertTrue(all(set(row) == {'id','name','role','active'} for row in directory))
        self.assertFalse(self.call(a, 'agent.gui_tin', {'recipient':'ngoai-don-vi','body':'Khong duoc gui'}).get('ok'))
        self.assertFalse(self.call({**self.root, 'name':'Chu'}, 'agent.doc_hop_thu').get('ok'))
        self.app.kho.thu_hoi_agent('nguoi-c')
        self.assertNotIn('nguoi-c', {r['id'] for r in self.value(a, 'agent.danh_sach')['agents']})
        self.assertFalse(self.call(a, 'agent.gui_tin', {'recipient':'nguoi-c','body':'Khong duoc gui'}).get('ok'))

    def test_rejoin_does_not_restore_old_mail_but_peer_keeps_own_history(self):
        a, b, c = (self.actor(name) for name in ('nguoi-a','nguoi-b','nguoi-c'))
        sent = self.value(b, 'agent.gui_tin', {'recipient':'nguoi-c','body':'Thu truoc khi roi don vi'})
        self.app.units.set_member(a, {'unit_id':self.units[0],'identity':'nguoi-c','role':'revoke'})
        self.assertFalse(self.call(c, 'agent.doc_hop_thu').get('ok'))
        self.assertEqual(self.value(b, 'agent.doc_hop_thu', {'peer':'nguoi-c'})['messages'][0]['id'], sent['id'])
        self.app.units.set_member(a, {'unit_id':self.units[0],'identity':'nguoi-c','role':'member'})
        c = self.actor('nguoi-c')
        self.assertEqual(self.value(c, 'agent.doc_hop_thu'), {'messages':[]})
        self.assertEqual(self.value(self.actor('nguoi-c',self.units[1]), 'agent.doc_hop_thu'), {'messages':[]})
        newer = self.value(c, 'agent.gui_tin', {'recipient':'nguoi-b','body':'Thu trong lan tham gia moi'})
        self.assertEqual([r['id'] for r in self.value(c, 'agent.doc_hop_thu')['messages']], [newer['id']])
        self.app.units.set_member(a, {'unit_id':self.units[0],'identity':'nguoi-b','role':'revoke'})
        self.app.units.set_member(a, {'unit_id':self.units[0],'identity':'nguoi-b','role':'member'})
        self.assertEqual(self.value(self.actor('nguoi-b'), 'agent.doc_hop_thu'), {'messages':[]})
        self.assertEqual([r['id'] for r in self.value(c, 'agent.doc_hop_thu')['messages']], [newer['id']])

    def test_role_change_gate_and_extra_arguments(self):
        a, b, c = (self.actor(name) for name in ('nguoi-a','nguoi-b','nguoi-c'))
        sent = self.value(b, 'agent.gui_tin', {'recipient':'nguoi-c','body':'  Noi dung da trim  '})
        self.app.units.set_member(a, {'unit_id':self.units[0],'identity':'nguoi-b','role':'admin'})
        self.assertFalse(self.call(b, 'agent.doc_hop_thu').get('ok'))
        b = self.actor('nguoi-b')
        self.assertEqual(self.value(b, 'agent.doc_hop_thu')['messages'][0]['id'], sent['id'])
        self.assertEqual(self.value(c, 'agent.doc_hop_thu')['messages'][0]['body'], 'Noi dung da trim')
        self.assertFalse(self.call(b, 'agent.gui_tin', {'recipient':'nguoi-c','body':'x','sender':'nguoi-a'}).get('ok'))
        self.app.core.nhan.chinh_sach.cong_ghi.dong()
        self.assertFalse(self.call(b, 'agent.gui_tin', {'recipient':'nguoi-c','body':'x'}).get('ok'))
        self.assertEqual(len(self.value(b, 'agent.doc_hop_thu')['messages']), 1)

    def test_restored_mail_is_readable_only_in_bound_unit(self):
        b, c = self.actor('nguoi-b'), self.actor('nguoi-c')
        sent = self.value(b, 'agent.gui_tin', {'recipient':'nguoi-c','body':'Thu de kiem phuc hoi'})
        self.app.kho.gui('nguoi-b','nguoi-c','Thu legacy khong duoc tron vao don vi')
        with tempfile.TemporaryDirectory() as area:
            bundle, restored = Path(area)/'bundle', Path(area)/'restored'
            backup(self.app.kho.root, bundle)
            restore(bundle, restored)
            other = UngDung(restored/'data', 'https://mailbox.test', True, unit_preview=True)
            try:
                actor = other.units.bind({'id':'nguoi-c','name':'C','role':'operator'}, self.units[0])
                result = other.core.goi(actor, 'agent.doc_hop_thu', {})
                self.assertTrue(result.get('ok'), result)
                self.assertEqual([r['id'] for r in result['ket_qua']['messages']], [sent['id']])
            finally:
                other.tasks.close()
                other.core.audit.close()

    def test_self_conversation_does_not_mix_other_conversations(self):
        a = self.actor('nguoi-a')
        own = self.value(a, 'agent.gui_tin', {'recipient':'nguoi-a','body':'Ghi chu cho chinh minh'})
        self.value(a, 'agent.gui_tin', {'recipient':'nguoi-b','body':'Trao doi voi dong nghiep'})
        selected = self.value(a, 'agent.doc_hop_thu', {'peer':'nguoi-a'})['messages']
        self.assertEqual([row['id'] for row in selected], [own['id']])


if __name__ == '__main__':
    unittest.main()
