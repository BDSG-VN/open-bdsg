#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nhan/thu_han_muc.py — BÀI TỰ KIỂM CHO HẠN MỨC.

CHẠY:
    .venv/bin/python nhan/thu_han_muc.py

KHÔNG cần mạng. KHÔNG cần CSDL. KHÔNG đọc biến môi trường. KHÔNG ngủ thật một
giây nào — toàn bộ thời gian trong bài này là một ĐỒNG HỒ BƠM TAY, nên bài chạy
xong dưới một phần mười giây và không bao giờ chập chờn theo tải máy.

VÌ SAO CÓ BÀI NÀY
-----------------
`nhan/han_muc.py` là một trong ba phép thử mà BDSG vừa khẳng định CÔNG KHAI trên
trang bdsg.vn/open-bdsg và trong README: "mọi lời gọi công cụ đều đi qua nhân,
nên nó luôn có một chủ thể, một phép thử quyền và một dòng nhật ký". Một khẳng
định công khai dựa trên mã CHƯA CÓ MỘT BÀI KIỂM NÀO là đúng họ lỗi "hỏng mà
không báo" mà dự án này đặt tên riêng. Bài này biến khẳng định ấy thành phép đo
cho phần HẠN MỨC.

NĂM CHỖ HẠN MỨC HỎNG MÀ KHÔNG TỰ BÁO — cả năm đều có phép kiểm ở đây:

  1. CỬA SỔ HOÁ RA LÀ CỬA SỔ CỐ ĐỊNH. Mã nói là cửa sổ trượt. Nếu nó thật ra
     reset theo mốc thì dồn hai cửa sổ hạn mức vào vài giây quanh mốc là được,
     mà không dòng nhật ký nào báo vượt. Phép kiểm 3 và 6 đo đúng chỗ đó.
  2. SAI MỘT ĐƠN VỊ Ở RANH GIỚI. Hạn mức 3 mà cho qua 4 lượt (hoặc chỉ 2) là
     lỗi hay gặp nhất của mô-đun kiểu này, và nó không bao giờ tự lộ: người
     dùng chỉ thấy "thỉnh thoảng bị chặn sớm". Phép kiểm 4 và 5.
  3. XEM TRƯỚC MÀ TIÊU LƯỢT. Nếu `kiem` cũng ghi nhận thì mỗi lần xem trước ăn
     mất một lượt của người gọi, và người gọi không hề biết. Phép kiểm 7.
  4. TÍNH PHÍ MỘT LƯỢT CHƯA HỀ CHẠY. Lời gọi bị ô công cụ chặn mà vẫn trừ vào ô
     vai là ăn gian ngược người dùng. Phép kiểm 11.
  5. Ô CỦA NGƯỜI NÀY RÒ SANG NGƯỜI KHÁC. Một khoá dựng sai là hạn mức dùng
     chung toàn hệ, và triệu chứng là "hệ chạy chậm dần khi đông người". Phép
     kiểm 12, 13.

BÀI NÀY KHÔNG NÓI GÌ VỀ: hạn mức dưới NHIỀU TIẾN TRÌNH (kho trong bộ nhớ không
chia sẻ — đây là giới hạn ĐÃ BIẾT, ghi rõ trong `KhoHanMuc`), về tranh chấp
luồng, và về trần theo TOKEN hay theo TIỀN (mô-đun này chỉ đếm LƯỢT).

MÃ THOÁT: 0 = mọi phép kiểm ĐẠT. 1 = có phép kiểm HỎNG.

Viết ngày 26/09/2026. Python 3.9.6.
"""

from __future__ import annotations

import os
import sys
import traceback

THU_MUC = os.path.dirname(os.path.abspath(__file__))
GOC_KHO = os.path.dirname(THU_MUC)

# Thư mục "nhan" là tên mô-đun Python hợp lệ, nhưng khi chạy TỆP NÀY trực tiếp
# thì sys.path[0] là chính thư mục nhan/, không phải gốc kho — nên `import nhan`
# hỏng. Thêm gốc kho vào đầu đường dẫn.
if __package__:
    from . import han_muc as _han_muc
    from . import danh_tinh as _danh_tinh
else:
    if GOC_KHO not in sys.path:
        sys.path.insert(0, GOC_KHO)
    from nhan import danh_tinh as _danh_tinh  # noqa: E402
    from nhan import han_muc as _han_muc  # noqa: E402

DanhTinh = _danh_tinh.DanhTinh
BoHanMuc = _han_muc.BoHanMuc
HanMuc = _han_muc.HanMuc
KhoTrongBoNho = _han_muc.KhoTrongBoNho
LoiHanMuc = _han_muc.LoiHanMuc


# ----------------------------------------------------------------------
# Khung chạy thử tối giản (không dùng pytest — kho không có pytest trong .venv,
# và một bài tự kiểm cần thêm phụ thuộc mới chạy được là bài sẽ không ai chạy).
# Giống hệt khung trong phuc-vu/thu_cong_mo_hinh.py, cố ý.
# ----------------------------------------------------------------------

_KET_QUA = []


def phep_kiem(ten):
    def bao(ham):
        def chay():
            try:
                ghi_chu = ham()
                _KET_QUA.append((ten, True, ghi_chu or ""))
                print("  [ĐẠT ] {}{}".format(ten, "  — " + ghi_chu if ghi_chu else ""))
                return True
            except Exception as loi:  # noqa: BLE001 — bài tự kiểm phải bắt hết
                _KET_QUA.append((ten, False, "{}: {}".format(type(loi).__name__, loi)))
                print("  [HỎNG] {}".format(ten))
                print("         {}: {}".format(type(loi).__name__, loi))
                for dong in traceback.format_exc().splitlines()[-6:]:
                    print("         | " + dong)
                return False

        chay.__name__ = ham.__name__
        return chay

    return bao


def bang(dieu_kien, thong_diep):
    if not dieu_kien:
        raise AssertionError(thong_diep)


class DongHoBom:
    """Đồng hồ giả, bơm tay từng giây.

    KHÔNG dùng time.sleep: một bài kiểm hạn mức ngủ thật 61 giây thì không ai
    chạy nó, và nó vẫn chập chờn khi máy bận. Bơm tay còn đo được cả những mốc
    mà ngủ thật không đo nổi — như "đúng giây thứ 59".
    """

    def __init__(self, bat_dau: float = 1000.0) -> None:
        self.t = float(bat_dau)

    def __call__(self) -> float:
        return self.t

    def troi(self, giay: float) -> float:
        self.t += float(giay)
        return self.t


def _danh_tinh_thu(ma="nguoi-thu", vai=("nhan-vien",)):
    return DanhTinh(ma=ma, ten="Tên Chỉ Để Kiểm", vai=vai, nguon="bai-tu-kiem")


# ══════════════════════════════════════════════════════════════════════════
# Nhóm 1 — HanMuc: từ chối cấu hình vô lý ngay lúc dựng
# ══════════════════════════════════════════════════════════════════════════


@phep_kiem("1. HanMuc từ chối cấu hình vô lý ngay lúc dựng, không âm thầm nhận")
def kiem_han_muc_tu_choi_vo_ly():
    cac_ca_hong = [
        (-1, 60.0, "số lượt âm"),
        (5, 0, "cửa sổ 0 giây"),
        (5, -3.0, "cửa sổ âm"),
        ("nhieu", 60.0, "số lượt là chuỗi"),
    ]
    for so_lan, cua_so, vi_sao in cac_ca_hong:
        try:
            HanMuc(so_lan, cua_so)
        except LoiHanMuc:
            continue
        raise AssertionError(
            "HanMuc(%r, %r) — %s — mà vẫn dựng được. Một hạn mức vô lý nhận lặng "
            "lẽ lúc dựng sẽ chỉ lộ ra lúc chạy, dưới dạng 'không ai bị chặn'."
            % (so_lan, cua_so, vi_sao)
        )
    # Và cấu hình hợp lệ thì phải dựng được, kèm mô tả đọc được.
    hm = HanMuc(10, 60.0)
    bang("10" in hm.mo_ta() and "60" in hm.mo_ta(), "mo_ta() phải nêu cả hai con số")
    return "4 cấu hình hỏng bị ném LoiHanMuc; mo_ta() = %r" % hm.mo_ta()


# ══════════════════════════════════════════════════════════════════════════
# Nhóm 2 — Cửa sổ TRƯỢT, và ranh giới đúng bằng hạn mức
# ══════════════════════════════════════════════════════════════════════════


@phep_kiem("2. Đúng là cửa sổ TRƯỢT: giây 59 vẫn bị chặn, giây 61 được qua")
def kiem_cua_so_truot():
    dh = DongHoBom()
    bo = BoHanMuc(HanMuc(10, 60.0), dong_ho=dh)
    dt = _danh_tinh_thu()

    for i in range(10):
        qua, ly_do = bo.kiem_va_ghi(dt, "cong-cu-thu")
        bang(qua, "lượt %d/10 phải qua, lại bị chặn: %s" % (i + 1, ly_do))

    dh.troi(59.0)
    qua, ly_do = bo.kiem_va_ghi(dt, "cong-cu-thu")
    bang(
        not qua,
        "Ở GIÂY 59 mà đã cho gọi lượt thứ 11 — cửa sổ 60 giây không còn là 60 "
        "giây. Trả về: %s" % ly_do,
    )

    dh.troi(2.0)  # tổng 61 giây kể từ lượt đầu
    qua, ly_do = bo.kiem_va_ghi(dt, "cong-cu-thu")
    bang(
        qua,
        "Ở GIÂY 61 mà vẫn chặn — cửa sổ KHÔNG trượt: 10 mốc cũ hơn 60 giây lẽ ra "
        "đã hết hiệu lực. Trả về: %s" % ly_do,
    )
    return "10 lượt/60s: giây 59 chặn, giây 61 qua"


@phep_kiem("3. Không có mốc reset theo lịch để canh: dồn hai cửa sổ KHÔNG lọt")
def kiem_khong_co_moc_reset():
    # Đây là lỗ của cửa sổ CỐ ĐỊNH mà đầu tệp han_muc.py mô tả: 23:59 gọi hết
    # hạn mức, 00:01 gọi tiếp hết hạn mức — gấp đôi trong hai phút. Dựng lại
    # đúng tình huống ấy: tiêu hết hạn mức ở cuối cửa sổ, rồi nhích một chút.
    dh = DongHoBom()
    bo = BoHanMuc(HanMuc(5, 60.0), dong_ho=dh)
    dt = _danh_tinh_thu()

    dh.troi(58.0)
    for i in range(5):
        qua, _ = bo.kiem_va_ghi(dt, "cc")
        bang(qua, "lượt %d trong chùm đầu phải qua" % (i + 1))

    dh.troi(3.0)  # sang "cửa sổ sau" nếu là cửa sổ cố định 60 giây
    qua, ly_do = bo.kiem_va_ghi(dt, "cc")
    bang(
        not qua,
        "Vừa qua một mốc chẵn 60 giây là hạn mức mở lại nguyên vẹn — ĐÂY LÀ CỬA "
        "SỔ CỐ ĐỊNH, không phải cửa sổ trượt, và nó cho phép dồn gấp đôi hạn mức "
        "quanh mốc reset. Trả về: %s" % ly_do,
    )
    return "5 mốc tiêu ở giây 58 vẫn còn hiệu lực ở giây 61"


@phep_kiem("4. Ranh giới ĐÚNG BẰNG hạn mức: lượt thứ N qua, lượt thứ N+1 chặn")
def kiem_ranh_gioi_dung_bang():
    # Sai một đơn vị ở đây là lỗi hay gặp nhất của mô-đun kiểu này. Quét vài giá
    # trị N chứ không chỉ một, vì `<` và `<=` chỉ lệch nhau ở đúng một điểm.
    for n in (1, 2, 3, 7):
        dh = DongHoBom()
        bo = BoHanMuc(HanMuc(n, 60.0), dong_ho=dh)
        dt = _danh_tinh_thu(ma="nguoi-%d" % n)
        for i in range(n):
            qua, ly_do = bo.kiem_va_ghi(dt, "cc")
            bang(
                qua,
                "hạn mức %d mà lượt thứ %d đã bị chặn (chặn SỚM một đơn vị): %s"
                % (n, i + 1, ly_do),
            )
        qua, ly_do = bo.kiem_va_ghi(dt, "cc")
        bang(
            not qua,
            "hạn mức %d mà lượt thứ %d vẫn qua (cho qua THỪA một đơn vị): %s"
            % (n, n + 1, ly_do),
        )
    return "N ∈ {1,2,3,7}: đúng N lượt qua, lượt N+1 chặn"


@phep_kiem("5. Mốc ĐÚNG BẰNG tuổi cửa sổ được coi là hết hạn — biên (t−w, t]")
def kiem_bien_dung_bang_cua_so():
    # Hành vi này được KHAI trong tài liệu đầu han_muc.py: đếm số mốc nằm trong
    # (bây_giờ − cửa_sổ, bây_giờ]. Kiểm đúng cái đã khai, chứ không kiểm cái ta
    # tưởng — nếu người sau đổi sang [t−w, t] thì phép kiểm này phải đỏ để họ
    # biết mình vừa đổi một hành vi có tài liệu.
    dh = DongHoBom()
    bo = BoHanMuc(HanMuc(1, 60.0), dong_ho=dh)
    dt = _danh_tinh_thu()

    bang(bo.kiem_va_ghi(dt, "cc")[0], "lượt đầu phải qua")
    dh.troi(59.999)
    bang(not bo.kiem_va_ghi(dt, "cc")[0], "ở 59,999 giây vẫn phải chặn")
    dh.troi(0.001)  # đúng 60,000 giây
    qua, ly_do = bo.kiem_va_ghi(dt, "cc")
    bang(
        qua,
        "mốc đúng 60,000 giây tuổi lẽ ra đã rơi ra ngoài cửa sổ (t−w, t] nhưng "
        "vẫn bị tính: %s" % ly_do,
    )
    return "59,999s chặn · 60,000s qua"


# ══════════════════════════════════════════════════════════════════════════
# Nhóm 3 — kiem vs kiem_va_ghi
# ══════════════════════════════════════════════════════════════════════════


@phep_kiem("6. `kiem` XEM TRƯỚC mà KHÔNG tiêu lượt — gọi 20 lần vẫn còn nguyên")
def kiem_xem_truoc_khong_tieu_luot():
    dh = DongHoBom()
    bo = BoHanMuc(HanMuc(3, 60.0), dong_ho=dh)
    dt = _danh_tinh_thu()

    for i in range(20):
        qua, ly_do = bo.kiem(dt, "cc")
        bang(
            qua,
            "lần XEM TRƯỚC thứ %d đã bị chặn ⇒ `kiem` đang GHI NHẬN. Người gọi "
            "xem trước hai lần là mất hai lượt mà không hề biết. Trả về: %s"
            % (i + 1, ly_do),
        )

    # Sau 20 lần xem trước, hạn mức phải còn nguyên vẹn 3 lượt.
    for i in range(3):
        bang(
            bo.kiem_va_ghi(dt, "cc")[0],
            "sau 20 lần xem trước, lượt THẬT thứ %d phải còn" % (i + 1),
        )
    bang(not bo.kiem_va_ghi(dt, "cc")[0], "lượt thật thứ 4 phải bị chặn")
    return "20 lần `kiem` tiêu 0 lượt; 3 lượt thật vẫn còn nguyên"


@phep_kiem("7. Lượt BỊ TỪ CHỐI không tính vào hạn mức — thử lại không tự kéo dài khoá")
def kiem_luot_bi_tu_choi_khong_tinh():
    # Nếu lượt bị từ chối cũng được ghi nhận thì (a) người đã vượt hạn mức tự
    # kéo dài thời gian khoá của mình mỗi lần thử lại, và (b) một bên thứ ba
    # biết mã danh tính có thể bắn lời gọi hỏng để khoá người khác.
    dh = DongHoBom()
    bo = BoHanMuc(HanMuc(2, 60.0), dong_ho=dh)
    dt = _danh_tinh_thu()

    bo.kiem_va_ghi(dt, "cc")  # t = 1000
    dh.troi(1.0)
    bo.kiem_va_ghi(dt, "cc")  # t = 1001 — đầy

    dh.troi(1.0)
    for _ in range(30):  # đập cửa 30 lần ở t = 1002
        bang(not bo.kiem_va_ghi(dt, "cc")[0], "phải bị chặn khi đã đầy")

    # Mốc cũ nhất là t=1000, nên đúng t=1060 phải mở lại đúng MỘT lượt.
    dh.t = 1060.0
    qua, ly_do = bo.kiem_va_ghi(dt, "cc")
    bang(
        qua,
        "30 lần thử lại bị từ chối đã bị ghi nhận thành 30 lượt, đẩy hạn mức lùi "
        "xa: %s" % ly_do,
    )
    return "30 lượt bị từ chối không để lại mốc nào"


# ══════════════════════════════════════════════════════════════════════════
# Nhóm 4 — Vai và công cụ
# ══════════════════════════════════════════════════════════════════════════


@phep_kiem("8. Nhiều vai thì lấy vai RỘNG NHẤT, và rộng đo bằng TỐC ĐỘ không bằng số lượt")
def kiem_vai_rong_nhat():
    dh = DongHoBom()
    bo = BoHanMuc(HanMuc(1, 60.0), dong_ho=dh)
    # 100 lượt/giờ = 0,028 lượt/giây — SỐ LƯỢT lớn nhưng TỐC ĐỘ nhỏ.
    bo.dat_han_muc_vai("khach", HanMuc(100, 3600.0))
    # 10 lượt/phút = 0,167 lượt/giây — số lượt nhỏ nhưng tốc độ lớn gấp 6.
    bo.dat_han_muc_vai("quan-tri", HanMuc(10, 60.0))

    dt = DanhTinh(ma="hai-vai", vai=("khach", "quan-tri"), nguon="bai-tu-kiem")
    for i in range(10):
        qua, ly_do = bo.kiem_va_ghi(dt, "cc")
        bang(
            qua,
            "lượt %d bị chặn ⇒ đã chọn vai HẸP hơn. Cấp thêm một vai mà làm người "
            "ta gọi được ÍT đi là hành vi bất ngờ. Trả về: %s" % (i + 1, ly_do),
        )
    qua, ly_do = bo.kiem_va_ghi(dt, "cc")
    bang(not qua, "quá 10 lượt/phút vẫn phải chặn: %s" % ly_do)
    bang(
        "quan-tri" in ly_do,
        "câu từ chối phải nói rõ vai nào đang áp, đang là: %s" % ly_do,
    )
    return "chọn 10 lượt/60s (0,167/s) thay vì 100 lượt/3600s (0,028/s)"


@phep_kiem("9. Không vai nào khai hạn mức thì rơi về MẶC ĐỊNH")
def kiem_roi_ve_mac_dinh():
    dh = DongHoBom()
    bo = BoHanMuc(HanMuc(2, 60.0), dong_ho=dh)
    bo.dat_han_muc_vai("vai-khac", HanMuc(999, 60.0))
    dt = _danh_tinh_thu(vai=("vai-khong-khai",))

    bang(bo.kiem_va_ghi(dt, "cc")[0], "lượt 1 phải qua")
    bang(bo.kiem_va_ghi(dt, "cc")[0], "lượt 2 phải qua")
    qua, ly_do = bo.kiem_va_ghi(dt, "cc")
    bang(not qua, "lượt 3 phải bị chặn theo hạn mức mặc định: %s" % ly_do)
    bang("mặc định" in ly_do, "câu từ chối phải nói rõ là hạn mức mặc định: %s" % ly_do)

    # Danh tính KHÔNG VAI cũng phải rơi về mặc định, không phải mở toang.
    dt0 = DanhTinh.khong_vai("nguoi-khong-vai", nguon="bai-tu-kiem")
    bo2 = BoHanMuc(HanMuc(1, 60.0), dong_ho=dh)
    bang(bo2.kiem_va_ghi(dt0, "cc")[0], "danh tính không vai: lượt 1 qua")
    bang(
        not bo2.kiem_va_ghi(dt0, "cc")[0],
        "danh tính KHÔNG VAI mà không bị hạn mức nào áp — hạn mức mở toang cho "
        "đúng loại danh tính đáng ngờ nhất",
    )
    return "vai lạ và danh tính không vai đều theo mặc định"


@phep_kiem("10. Hạn mức CÔNG CỤ chặt hơn thì THẮNG hạn mức vai rộng")
def kiem_cong_cu_chat_hon_thang():
    dh = DongHoBom()
    bo = BoHanMuc(HanMuc(1000, 60.0), dong_ho=dh)
    bo.dat_han_muc_vai("quan-tri", HanMuc(1000, 60.0))
    bo.dat_han_muc_cong_cu("nen-tang-yeu", HanMuc(2, 60.0))
    dt = _danh_tinh_thu(vai=("quan-tri",))

    bang(bo.kiem_va_ghi(dt, "nen-tang-yeu")[0], "lượt 1 qua")
    bang(bo.kiem_va_ghi(dt, "nen-tang-yeu")[0], "lượt 2 qua")
    qua, ly_do = bo.kiem_va_ghi(dt, "nen-tang-yeu")
    bang(
        not qua,
        "vai cho 1000 lượt nên công cụ chỉ cho 2 lượt bị bỏ qua — trần tuyệt đối "
        "do người vận hành đặt cho một nền tảng yếu đã không có tác dụng: %s"
        % ly_do,
    )
    bang("nen-tang-yeu" in ly_do, "câu từ chối phải nêu tên công cụ: %s" % ly_do)

    # Công cụ KHÁC không bị ảnh hưởng — trần là của riêng công cụ ấy.
    bang(
        bo.kiem_va_ghi(dt, "nen-tang-khoe")[0],
        "trần của một công cụ đã tràn sang công cụ khác",
    )
    return "vai 1000 lượt nhưng công cụ 2 lượt ⇒ chặn ở lượt 3"


@phep_kiem("11. Ô công cụ chặn thì ô VAI KHÔNG bị trừ — không tính phí lượt chưa chạy")
def kiem_cong_cu_chan_khong_tru_o_vai():
    dh = DongHoBom()
    bo = BoHanMuc(HanMuc(5, 60.0), dong_ho=dh)
    bo.dat_han_muc_cong_cu("cc-chat", HanMuc(1, 60.0))
    dt = _danh_tinh_thu()

    bang(bo.kiem_va_ghi(dt, "cc-chat")[0], "lượt 1 qua (vai 1/5, công cụ 1/1)")
    for _ in range(10):
        bang(not bo.kiem_va_ghi(dt, "cc-chat")[0], "công cụ đã đầy, phải chặn")

    # Ô vai mới tiêu ĐÚNG 1 lượt. Còn 4 lượt cho công cụ khác.
    for i in range(4):
        qua, ly_do = bo.kiem_va_ghi(dt, "cc-rong")
        bang(
            qua,
            "10 lần bị ô CÔNG CỤ chặn đã bị trừ vào ô VAI: lượt %d ở công cụ khác "
            "đã hết. Trả về: %s" % (i + 1, ly_do),
        )
    bang(not bo.kiem_va_ghi(dt, "cc-rong")[0], "lượt thứ 6 của ô vai phải bị chặn")
    return "10 lần bị công cụ chặn để lại 0 mốc trong ô vai"


@phep_kiem("12. Hạn mức 0 lượt chặn TẤT CẢ, kể cả lượt đầu tiên")
def kiem_han_muc_khong():
    dh = DongHoBom()
    bo = BoHanMuc(HanMuc(0, 60.0), dong_ho=dh)
    dt = _danh_tinh_thu()
    qua, ly_do = bo.kiem_va_ghi(dt, "cc")
    bang(
        not qua,
        "hạn mức 0 mà lượt ĐẦU TIÊN vẫn qua — đây đúng là lỗi 'đếm từ 0 nên được "
        "một lượt miễn phí': %s" % ly_do,
    )
    bang("0" in ly_do, "câu từ chối nên nói rõ hạn mức là 0: %s" % ly_do)

    bo.dat_han_muc_cong_cu("cam-han", HanMuc(0, 60.0))
    bo2 = BoHanMuc(HanMuc(10, 60.0), dong_ho=dh)
    bo2.dat_han_muc_cong_cu("cam-han", HanMuc(0, 60.0))
    bang(
        not bo2.kiem_va_ghi(dt, "cam-han")[0],
        "hạn mức công cụ 0 lượt phải chặn ngay cả khi vai còn rộng",
    )
    bang(bo2.kiem_va_ghi(dt, "cc-khac")[0], "công cụ khác không bị ảnh hưởng")
    return "0 lượt chặn cả lượt đầu, ở cả ô vai lẫn ô công cụ"


@phep_kiem("13. Không có danh tính thì TỪ CHỐI, không lặng lẽ cho qua")
def kiem_khong_danh_tinh():
    dh = DongHoBom()
    bo = BoHanMuc(HanMuc(10, 60.0), dong_ho=dh)
    qua, ly_do = bo.kiem_va_ghi(None, "cc")
    bang(
        not qua,
        "danh tính None mà vẫn qua hạn mức — một lời gọi KHÔNG CHỦ THỂ đã lọt, "
        "đúng thứ khẳng định công khai nói là không thể: %s" % ly_do,
    )
    bang("danh tính" in ly_do, "câu từ chối phải nói rõ vì sao: %s" % ly_do)
    return "None ⇒ từ chối kèm lý do đọc được"


# ══════════════════════════════════════════════════════════════════════════
# Nhóm 5 — Kho: ô riêng từng khoá, và dọn không xoá nhầm
# ══════════════════════════════════════════════════════════════════════════


@phep_kiem("14. Ô của danh tính A KHÔNG rò sang danh tính B")
def kiem_o_rieng_tung_danh_tinh():
    dh = DongHoBom()
    bo = BoHanMuc(HanMuc(3, 60.0), dong_ho=dh)
    a = _danh_tinh_thu(ma="nguoi-a")
    b = _danh_tinh_thu(ma="nguoi-b")

    for _ in range(3):
        bang(bo.kiem_va_ghi(a, "cc")[0], "A phải được 3 lượt")
    bang(not bo.kiem_va_ghi(a, "cc")[0], "A phải hết lượt")

    for i in range(3):
        qua, ly_do = bo.kiem_va_ghi(b, "cc")
        bang(
            qua,
            "B mất lượt vì A đã gọi ⇒ khoá dựng sai, hạn mức thành DÙNG CHUNG "
            "toàn hệ. Lượt %d của B: %s" % (i + 1, ly_do),
        )
    bang(not bo.kiem_va_ghi(b, "cc")[0], "B cũng phải hết ở lượt 4")
    return "A tiêu hết 3 lượt, B vẫn còn đủ 3 lượt"


@phep_kiem("15. KhoTrongBoNho: đếm theo khoá, dọn khoá rỗng (không rò bộ nhớ chậm)")
def kiem_kho_trong_bo_nho():
    kho = KhoTrongBoNho()
    kho.ghi_nhan("A", 100.0)
    kho.ghi_nhan("A", 101.0)
    kho.ghi_nhan("B", 100.5)

    bang(kho.dem_tu("A", 99.0) == 2, "khoá A phải có 2 mốc")
    bang(kho.dem_tu("B", 99.0) == 1, "khoá B phải có 1 mốc, không lẫn của A")
    bang(kho.dem_tu("C", 0.0) == 0, "khoá chưa từng ghi phải đếm 0, không ném lỗi")
    bang(kho.moc_cu_nhat_tu("A", 99.0) == 100.0, "mốc cũ nhất của A phải là 100,0")
    bang(kho.moc_cu_nhat_tu("C", 0.0) is None, "khoá rỗng phải trả None")

    # `don` chỉ được xoá mốc ĐÃ RA NGOÀI cửa sổ, không đụng mốc còn hiệu lực.
    kho.don("A", 100.0)
    bang(
        kho.dem_tu("A", 99.0) == 1,
        "don(100,0) phải bỏ đúng mốc 100,0 và GIỮ mốc 101,0 — xoá nhầm mốc còn "
        "hiệu lực là tặng không một lượt",
    )
    bang(kho.dem_tu("B", 99.0) == 1, "dọn khoá A không được đụng khoá B")

    # Dọn sạch thì khoá phải biến mất khỏi bảng, không nằm lại làm rác.
    kho.don("A", 1000.0)
    kho.don("B", 1000.0)
    bang(
        kho.so_khoa() == 0,
        "khoá rỗng còn nằm lại trong bảng: bảng sẽ phình theo TỔNG SỐ danh tính "
        "từng gọi, mãi mãi — một rò rỉ bộ nhớ chỉ lộ ra sau vài tháng chạy. "
        "Còn %d khoá." % kho.so_khoa(),
    )
    return "3 mốc / 2 khoá; don() giữ mốc còn hiệu lực; bảng về 0 khoá"


@phep_kiem("16. Dùng đồng hồ TIÊM VÀO, không phải đồng hồ hệ thống")
def kiem_dong_ho_tiem_vao():
    # Nếu BoHanMuc lén gọi time.monotonic() ở đâu đó thay vì dùng đồng hồ được
    # tiêm, thì mọi phép kiểm thời gian ở trên chỉ đúng vì may mắn — và bài kiểm
    # sẽ chập chờn trên máy chạy chậm. Kiểm bằng cách bơm đồng hồ LÙI: chỉ có
    # đồng hồ tiêm vào mới lùi được.
    dh = DongHoBom(bat_dau=5000.0)
    bo = BoHanMuc(HanMuc(1, 60.0), dong_ho=dh)
    dt = _danh_tinh_thu()
    bang(bo.kiem_va_ghi(dt, "cc")[0], "lượt đầu qua")
    dh.t = 1_000_000.0  # nhảy xa về tương lai
    qua, _ = bo.kiem_va_ghi(dt, "cc")
    bang(
        qua,
        "bơm đồng hồ đi xa mà mốc cũ vẫn tính ⇒ mô-đun KHÔNG dùng đồng hồ được "
        "tiêm vào, và mọi phép kiểm thời gian ở trên là vô giá trị",
    )
    return "đồng hồ tiêm vào điều khiển được toàn bộ hành vi cửa sổ"


CAC_PHEP_KIEM = [
    kiem_han_muc_tu_choi_vo_ly,
    kiem_cua_so_truot,
    kiem_khong_co_moc_reset,
    kiem_ranh_gioi_dung_bang,
    kiem_bien_dung_bang_cua_so,
    kiem_xem_truoc_khong_tieu_luot,
    kiem_luot_bi_tu_choi_khong_tinh,
    kiem_vai_rong_nhat,
    kiem_roi_ve_mac_dinh,
    kiem_cong_cu_chat_hon_thang,
    kiem_cong_cu_chan_khong_tru_o_vai,
    kiem_han_muc_khong,
    kiem_khong_danh_tinh,
    kiem_o_rieng_tung_danh_tinh,
    kiem_kho_trong_bo_nho,
    kiem_dong_ho_tiem_vao,
]


def main():
    print("=" * 78)
    print("BÀI TỰ KIỂM — nhan/han_muc.py (hạn mức, cửa sổ trượt)")
    print("Python {}.{}.{}".format(*sys.version_info[:3]))
    print("KHÔNG cần mạng, KHÔNG cần CSDL, KHÔNG ngủ thật một giây nào.")
    print("=" * 78)
    print()

    tat_ca_dat = True
    for phep in CAC_PHEP_KIEM:
        if not phep():
            tat_ca_dat = False

    print()
    print("=" * 78)
    so_dat = sum(1 for _, dat, _ in _KET_QUA if dat)
    so_hong = len(_KET_QUA) - so_dat
    if tat_ca_dat:
        print("KẾT QUẢ: {}/{} ĐẠT.".format(so_dat, len(_KET_QUA)))
        print()
        print("Nghĩa là gì: cửa sổ ĐÚNG là cửa sổ trượt (không có mốc reset để canh, không")
        print("dồn được gấp đôi hạn mức); ranh giới đúng bằng con số khai, không lệch một")
        print("đơn vị; `kiem` xem trước mà không tiêu lượt; lượt bị từ chối không tự kéo dài")
        print("thời gian khoá; vai rộng nhất thắng nhưng trần công cụ vẫn chặn được; ô của")
        print("mỗi danh tính và mỗi công cụ là riêng.")
        print()
        print("Nghĩa là gì KHÔNG: bài này KHÔNG kiểm hạn mức dưới NHIỀU TIẾN TRÌNH —")
        print("KhoTrongBoNho không chia sẻ giữa các tiến trình, nên chạy hai tiến trình nhân")
        print("thì hạn mức thực tế GẤP ĐÔI. Đó là giới hạn ĐÃ BIẾT, ghi trong KhoHanMuc,")
        print("không phải lỗi ẩn. Bài cũng KHÔNG kiểm tranh chấp luồng, và KHÔNG nói gì về")
        print("trần theo token hay theo tiền — mô-đun này chỉ đếm LƯỢT.")
    else:
        print("KẾT QUẢ: {}/{} ĐẠT, {} HỎNG.".format(so_dat, len(_KET_QUA), so_hong))
        print()
        print("Các phép kiểm hỏng:")
        for ten, dat, ghi_chu in _KET_QUA:
            if not dat:
                print("  - {}: {}".format(ten, ghi_chu))
    print("=" * 78)
    return 0 if tat_ca_dat else 1


if __name__ == "__main__":
    sys.exit(main())
