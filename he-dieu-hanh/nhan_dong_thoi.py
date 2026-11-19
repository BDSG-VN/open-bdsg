"""Synchronize short kernel bookkeeping, never hold a lock during tool execution."""

import threading
from nhan.han_muc import BoHanMuc, HanMuc
from nhan.nhat_ky import NhatKy


class HanMucDongThoi(BoHanMuc):
    def __init__(self):
        super().__init__(mac_dinh=HanMuc(so_lan=60, cua_so_giay=60.0))
        self.lock = threading.RLock()

    def kiem_va_ghi(self, *args, **kwargs):
        with self.lock:
            return super().kiem_va_ghi(*args, **kwargs)


class NhatKyDongThoi(NhatKy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock = threading.RLock()

    def ghi(self, *args, **kwargs):
        with self.lock:
            return super().ghi(*args, **kwargs)
