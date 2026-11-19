"""Callback provider đến trễ không được ghi vào lượt tác vụ mới."""
import tempfile
import threading
import time
import unittest
from kho import Kho
from cong_viec import CongViec
from thu_cong_viec import NhanThu, MoHinhTat, A


class LateProvider:
    configured=True
    configuration_error=''
    def __init__(self):
        self.release=threading.Event()
        self.delivered=threading.Event()
        self.calls=0
        self.thread=None
    def public_status(self): return {'configured':True,'mode':'api','model':'synthetic-provider'}
    def run(self,prompt,context,core,actor,on_event,stop):
        self.calls+=1
        if self.calls==1:
            def deliver():
                try:
                    if self.release.wait(4):
                        on_event('team-state','Sự kiện tổng hợp đến muộn',team={'agents':[{
                            'skill_id':'late','state':'completed','name':'late','output':'OLD_PRIVATE_SYNTHETIC'}]})
                except RuntimeError:
                    pass
                finally: self.delivered.set()
            self.thread=threading.Thread(target=deliver)
            self.thread.start()
        return '# Báo cáo provider tổng hợp'


class ThuTheHeCongViec(unittest.TestCase):
    def test_future_da_huy_cua_che_do_cu_khong_chay_luot_moi(self):
        with tempfile.TemporaryDirectory() as folder:
            core=NhanThu();core.block=threading.Event()
            tasks=CongViec(Kho(folder),core);tasks.model=MoHinhTat()
            args={'prompt':'Tạo báo cáo kiểm tác vụ đang xếp hàng','template':'de-xuat-giai-phap'}
            try:
                one=tasks.create(A,args)['id'];two=tasks.create(A,args)['id']
                deadline=time.monotonic()+3
                while len(core.calls)<2 and time.monotonic()<deadline: time.sleep(.01)
                self.assertEqual(len(core.calls),2)
                target=tasks.create(A,args)['id']
                tasks.cancel(A,target)
                tasks.followup(A,target,'Cấp lại lượt mới sau khi đã hủy Future đang xếp hàng')
                core.block.set()
                for identifier in (one,two,target): self.finish(tasks,identifier)
                tasks.close()
                result=tasks.detail(A,target)
                self.assertEqual(result['status'],'completed')
                self.assertEqual([artifact['run'] for artifact in result['artifacts']],[2])
            finally:
                core.block.set();tasks.close()

    def test_callback_tu_luot_cu_tren_thread_khac_khong_ghi_luot_moi(self):
        with tempfile.TemporaryDirectory() as folder:
            tasks=CongViec(Kho(folder),NhanThu())
            provider=LateProvider();tasks.model=provider
            try:
                identifier=tasks.create(A,{'prompt':'Tạo báo cáo kiểm thế hệ lượt chạy', 'template':'de-xuat-giai-phap'})['id']
                self.finish(tasks,identifier)
                tasks.followup(A,identifier,'Bổ sung báo cáo thuộc lượt mới riêng biệt')
                self.finish(tasks,identifier)
                provider.release.set()
                self.assertTrue(provider.delivered.wait(3))
                result=tasks.detail(A,identifier)
                self.assertEqual([item['run'] for item in result['artifacts']],[1,2])
                self.assertNotIn('OLD_PRIVATE_SYNTHETIC',str(result))
            finally:
                provider.release.set()
                if provider.thread: provider.thread.join(timeout=5)
                tasks.close()

    def finish(self,tasks,identifier):
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            result=tasks.detail(A,identifier)
            if result['status'] in ('completed','failed'): break
            time.sleep(.01)
        self.assertEqual(result['status'],'completed')


if __name__=='__main__': unittest.main()
