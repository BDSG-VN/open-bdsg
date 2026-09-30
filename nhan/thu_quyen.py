#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nhan/thu_quyen.py — BÀI TỰ KIỂM CHO nhan/quyen.py.

CHẠY:
    .venv/bin/python nhan/thu_quyen.py

KHÔNG cần mạng. KHÔNG đọc biến môi trường. KHÔNG chạm đĩa. KHÔNG cần CSDL.
Toàn bộ bài chạy xong dưới một giây.

VÌ SAO CÓ BÀI NÀY
-----------------
BDSG đã CÔNG BỐ CÔNG KHAI — trên bdsg.vn/open-bdsg và trong README của kho —
câu này:

    "mọi lời gọi công cụ đều đi qua nhân, nên nó luôn có MỘT CHỦ THỂ, MỘT PHÉP
     THỬ QUYỀN và MỘT DÒNG NHẬT KÝ"

Cho tới hôm nay, phần "MỘT PHÉP THỬ QUYỀN" của câu ấy chưa có một phép đo nào
đứng sau. Một khẳng định công khai không kiểm được chính là họ lỗi "hỏng mà
không báo" mà kho này đặt tên riêng: nó vẫn chạy, vẫn trả True/False, và sai ở
chỗ không ai nhìn thấy. Tệp này biến phần khẳng định ấy thành phép đo.

BÀI NÀY KIỂM ĐÚNG NĂM CHỖ HỎNG MÀ LỖI KHÔNG TỰ BÁO
---------------------------------------------------
  1. MẶC ĐỊNH CHO PHÉP ĐỘI LỐT MẶC ĐỊNH TỪ CHỐI. Một danh sách trắng mà lọt
     được công cụ chưa khai, vai chưa khai hay danh tính rỗng thì nó là danh
     sách đen đội lốt. Hỏng kiểu này im lặng cho tới lúc đọc nhật ký sự cố.
  2. CỔNG GHI QUÁ TAY HOẶC HỤT TAY. Hụt tay: cổng đóng mà công cụ GHI vẫn chạy.
     Quá tay: cổng đóng mà công cụ CHỈ ĐỌC cũng bị chặn — chế độ quan sát thành
     chế độ chết máy, và người ta sẽ mở cổng ghi ra chỉ để đọc được.
  3. "MỞ MỘT LẦN LÀ MỞ MÃI". Trạng thái cổng phải đi cả hai chiều. Một `dong()`
     không đóng thật thì cả kiến trúc "mặc định chỉ đọc" chỉ là lời hứa.
  4. RÒ RỈ TRẠNG THÁI QUA GIÁ TRỊ TRẢ VỀ. Nếu `cong_cu_duoc_phep` trả về chính
     cấu trúc bên trong thì người gọi sửa danh sách ấy là sửa luôn chính sách.
     Lỗi này có thật và rất hay gặp, và nó không để lại dấu vết nào.
  5. NHẤT QUÁN HOA/THƯỜNG VÀ KHOẢNG TRẮNG. Không nhất quán ở đây là một lỗi
     vượt quyền: "crm.ghi" bị chặn còn "CRM.GHI" lọt là đủ.

LUẬT CỦA BÀI NÀY: mỗi ca kiểm ở đây đã được THỬ NGƯỢC — phá `nhan/quyen.py` một
cách nhỏ nhất có thể, xác nhận ca ấy ĐỎ, rồi phục hồi nguyên trạng. Một ca kiểm
chưa thử ngược thì chưa biết nó có đo gì không.

KHÔNG CÒN CA ĐỎ CÓ CHỦ Ý (26/09/2026). Hai ca cuối cùng đã xử xong, và hai cách
xử KHÁC HẲN nhau — ghi ra đây vì chỗ này dễ làm ẩu nhất:

  · 3.3 `CongGhi(mo=True)` mở cổng ghi vô danh → sửa MÃ NGUỒN. Hàm dựng nay nổ
    y như `mo()`. Bài kiểm được viết lại để đòi đúng tiếng nổ ấy, chứ không
    phải để thôi kiểm.
  · 4.1 `cong_cu_duoc_phep` → sửa BÀI KIỂM, và chỉ ở đúng một chỗ: nó đối chiếu
    thứ tự ngược ([kho…, crm…]) trong khi hợp đồng của hàm là SẮP XẾP, đúng
    hợp đồng mà phép kiểm 4.3 ngay bên dưới đang chốt. Mã nguồn không sai.
    Không ca nào được làm xanh bằng cách nới lỏng phép kiểm.

Ca đỏ từ nay đều là HỒI QUY. Đọc phần in ra ở cuối.

BÀI NÀY KHÔNG NÓI GÌ VỀ: nhật ký (xem `nhan/nhat_ky.py`), hạn mức, xác thực,
hay bảy bước của `nhan/dinh_tuyen.py`. Nó chỉ trả lời "người này CÓ ĐƯỢC LÀM
việc này không".

MÃ THOÁT: 0 = mọi phép kiểm ĐẠT. 1 = có phép kiểm HỎNG.

Viết ngày 26/09/2026. Python 3.9.6.
"""

from __future__ import annotations

import os
import sys
import time
import traceback

THU_MUC = os.path.dirname(os.path.abspath(__file__))
GOC_KHO = os.path.dirname(THU_MUC)

# ----------------------------------------------------------------------
# Nạp gói. Khác `phuc-vu/` — thư mục ở đó có gạch ngang nên phải nạp bằng
# importlib; "nhan" là tên mô-đun hợp lệ, nên chỉ cần đặt gốc kho lên sys.path.
# Vẫn phải làm việc này: chạy thẳng tệp thì sys.path[0] là chính thư mục nhan/,
# mà `quyen.py` nhập tương đối (`from .danh_tinh import ...`) nên cần ngữ cảnh
# gói.
# ----------------------------------------------------------------------
if __package__:
    from . import danh_tinh as _danh_tinh
    from . import quyen as _quyen
else:
    if GOC_KHO not in sys.path:
        sys.path.insert(0, GOC_KHO)
    from nhan import danh_tinh as _danh_tinh  # noqa: E402
    from nhan import quyen as _quyen  # noqa: E402

ChinhSach = _quyen.ChinhSach
CongGhi = _quyen.CongGhi
MoTaCongCu = _quyen.MoTaCongCu
LoiChinhSach = _quyen.LoiChinhSach
DOC = _quyen.DOC
GHI = _quyen.GHI

DanhTinh = _danh_tinh.DanhTinh
LoiDanhTinh = _danh_tinh.LoiDanhTinh


# ----------------------------------------------------------------------
# Khung chạy thử tối giản (không pytest, không unittest — cùng lý do như
# `phuc-vu/thu_cong_mo_hinh.py`: một bài tự kiểm cần cài thêm thứ gì mới chạy
# được là một bài tự kiểm sẽ không ai chạy).
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


def nem(lop_loi, ham, thong_diep):
    """Khẳng định `ham()` NÉM đúng loại lỗi ấy.

    Cố ý không dùng `try/except Exception`: một ca kiểm bắt mọi lỗi sẽ xanh cả
    khi mã nổ vì lý do hoàn toàn khác (gõ nhầm tên thuộc tính chẳng hạn), tức là
    ca kiểm vô giá trị mà không ai biết.
    """
    try:
        ham()
    except lop_loi:
        return True
    except Exception as khac:  # noqa: BLE001
        raise AssertionError(
            "{} — nổ đúng chỗ nhưng SAI LOẠI: chờ {}, nhận {}: {}".format(
                thong_diep, lop_loi.__name__, type(khac).__name__, khac
            )
        )
    raise AssertionError(thong_diep + " — KHÔNG nổ gì cả")


# ── Dữ liệu dựng sẵn ─────────────────────────────────────────────────────
# Mã danh tính BỊA, rõ ràng là bịa. Không có khoá, không có mật khẩu, không có
# token nào trong tệp này: lớp quyền không nhìn thấy chứng thư bao giờ — nó chỉ
# nhận một `DanhTinh` đã xác thực xong.
MA_BIA = "nguoi-bia-de-kiem-01"
NGUON_BIA = "nguon-bia"

CC_DOC = "crm.doc_khach"
CC_GHI = "crm.ghi_khach"
CC_DOC_2 = "kho.doc_ton"
CC_CHUA_KHAI = "crm.chua_ai_khai"

VAI_DOC = "nguoi-doc"
VAI_BIEN_TAP = "bien-tap"


def nguoi(vai, ma=MA_BIA, het_han=None):
    """Dựng một danh tính đã-xác-thực-xong với bộ vai cho trước."""
    return DanhTinh(ma=ma, vai=vai, nguon=NGUON_BIA, het_han=het_han)


def chinh_sach_mau(cong_ghi=None):
    """Chính sách nhỏ nhất đủ để hỏi mọi câu: hai công cụ đọc, một công cụ ghi.

    `nguoi-doc` chỉ đọc. `bien-tap` đọc và ghi. Đây là hình dạng thật của một
    cấu hình BDSG thu nhỏ, không phải một đồ chơi.
    """
    cs = ChinhSach(cong_ghi=cong_ghi)
    cs.khai_cong_cu(CC_DOC, ghi=False, mo_ta="đọc hồ sơ khách")
    cs.khai_cong_cu(CC_DOC_2, ghi=False, mo_ta="đọc tồn kho")
    cs.khai_cong_cu(CC_GHI, ghi=True, mo_ta="sửa hồ sơ khách")
    cs.khai_vai(VAI_DOC, doc=[CC_DOC, CC_DOC_2])
    cs.khai_vai(VAI_BIEN_TAP, doc=[CC_DOC, CC_DOC_2], ghi=[CC_GHI])
    return cs


def mo_cong(cs):
    cs.cong_ghi.mo(ly_do="bài tự kiểm", nguoi_mo=MA_BIA)


# ══════════════════════════════════════════════════════════════════════════
# Nhóm 1 — MẶC ĐỊNH LÀ TỪ CHỐI
# Câu hỏi: danh sách trắng này có thật là danh sách trắng không?
# ══════════════════════════════════════════════════════════════════════════


@phep_kiem("1.1 Công cụ CHƯA KHAI thì từ chối, dù vai có đủ quyền khác")
def kiem_cong_cu_chua_khai():
    cs = chinh_sach_mau()
    mo_cong(cs)  # cổng ghi MỞ — để không ai đổ cho cổng
    duoc, ly_do = cs.duoc_goi(nguoi((VAI_BIEN_TAP,)), CC_CHUA_KHAI)
    bang(duoc is False, "công cụ chưa khai mà ĐƯỢC GỌI — đây là lỗi bảo mật")
    bang("danh sách trắng" in ly_do, "lý do không nói rõ vì sao: %r" % (ly_do,))
    return "vai đầy đủ quyền + cổng mở vẫn không lọt"


@phep_kiem("1.2 Vai CHƯA KHAI trong chính sách thì từ chối")
def kiem_vai_chua_khai():
    cs = chinh_sach_mau()
    mo_cong(cs)
    for ten_cc in (CC_DOC, CC_GHI):
        duoc, ly_do = cs.duoc_goi(nguoi(("vai-khong-ai-khai",)), ten_cc)
        bang(duoc is False, "vai chưa khai gọi được %r — lỗi bảo mật" % (ten_cc,))
    bang(
        "chưa khai trong chính sách" in ly_do,
        "lý do không chỉ ra vai chưa khai: %r" % (ly_do,),
    )
    return "cả công cụ đọc lẫn công cụ ghi"


@phep_kiem("1.3 Danh tính KHÔNG VAI NÀO thì từ chối")
def kiem_vai_rong():
    cs = chinh_sach_mau()
    mo_cong(cs)
    khong_vai = DanhTinh.khong_vai(MA_BIA, nguon=NGUON_BIA)
    bang(khong_vai.vai == (), "khong_vai() lẽ ra phải cho bộ vai rỗng")
    for ten_cc in (CC_DOC, CC_GHI):
        duoc, ly_do = cs.duoc_goi(khong_vai, ten_cc)
        bang(duoc is False, "danh tính không vai gọi được %r — lỗi bảo mật" % (ten_cc,))
    bang("không có vai nào" in ly_do, "lý do sai: %r" % (ly_do,))
    return "DanhTinh.khong_vai không gọi được gì"


@phep_kiem("1.4 Danh tính None thì từ chối (lớp quyền không tin lớp trên đã kiểm)")
def kiem_danh_tinh_none():
    cs = chinh_sach_mau()
    mo_cong(cs)
    for ten_cc in (CC_DOC, CC_GHI, CC_CHUA_KHAI):
        duoc, ly_do = cs.duoc_goi(None, ten_cc)
        bang(duoc is False, "None gọi được %r — lỗi bảo mật nặng" % (ten_cc,))
        bang("không có danh tính" in ly_do, "lý do sai: %r" % (ly_do,))
    bang(cs.cong_cu_duoc_phep(None) == [], "cong_cu_duoc_phep(None) phải rỗng")
    return "duoc_goi và cong_cu_duoc_phep đều chặn"


@phep_kiem("1.5 Chính sách TRỐNG từ chối tất cả (không có quyền mặc định nào)")
def kiem_chinh_sach_trong():
    cs = ChinhSach()
    mo_cong(cs)
    ai_do = nguoi(("quan-tri", "bien-tap", "nguoi-doc"))
    for ten_cc in (CC_DOC, CC_GHI, "bat_ky.cong_cu"):
        duoc, _ = cs.duoc_goi(ai_do, ten_cc)
        bang(duoc is False, "chính sách trống mà cho gọi %r" % (ten_cc,))
    bang(cs.cong_cu_da_khai() == [], "chính sách trống mà có công cụ")
    bang(cs.cac_vai_da_khai() == [], "chính sách trống mà có vai")
    bang(cs.cong_cu_duoc_phep(ai_do) == [], "chính sách trống mà cho phép thứ gì đó")
    return "kể cả với vai tên 'quan-tri'"


@phep_kiem("1.6 Ký tự đại diện bị TỪ CHỐI lúc khai vai, không âm thầm bỏ qua")
def kiem_ky_tu_dai_dien():
    cs = chinh_sach_mau()
    for xau in ("*", "crm.*", "*.doc_khach", "crm.doc_*"):
        nem(
            LoiChinhSach,
            lambda x=xau: cs.khai_vai("vai-sao", doc=[x]),
            "ký tự đại diện %r được nhận — danh sách đen đội lốt danh sách trắng" % (xau,),
        )
    bang("vai-sao" not in cs.cac_vai_da_khai(), "vai hỏng vẫn lọt vào sổ vai")
    return "4 dạng dấu sao, và vai hỏng không để lại vết"


@phep_kiem("1.7 Tên công cụ trong khai_vai phải ĐÃ KHAI, gõ nhầm là nổ")
def kiem_go_nham_ten_cong_cu():
    cs = chinh_sach_mau()
    nem(
        LoiChinhSach,
        lambda: cs.khai_vai("vai-moi", doc=[CC_DOC, "crm.doc_kach"]),
        "tên gõ nhầm được nhận — quản trị tưởng đã cấp quyền, người dùng bị từ chối",
    )
    bang("vai-moi" not in cs.cac_vai_da_khai(), "vai hỏng vẫn được ghi vào sổ")
    return "và không cấp một phần: cả lời khai bị huỷ"


# ══════════════════════════════════════════════════════════════════════════
# Nhóm 2 — CỔNG GHI: phải chặn ĐÚNG công cụ ghi, và chỉ công cụ ghi
# ══════════════════════════════════════════════════════════════════════════


@phep_kiem("2.1 Cổng ghi MẶC ĐỊNH ĐÓNG")
def kiem_cong_mac_dinh_dong():
    bang(CongGhi().dang_mo is False, "CongGhi() mặc định MỞ — kiến trúc số 3 hỏng")
    bang(
        ChinhSach().cong_ghi.dang_mo is False,
        "ChinhSach() dựng ra một cổng ghi đang MỞ — mặc định chỉ đọc hỏng",
    )
    return "cả CongGhi() lẫn ChinhSach()"


@phep_kiem("2.2 Cổng ĐÓNG chặn công cụ GHI, kể cả khi vai được cấp quyền ghi")
def kiem_cong_dong_chan_ghi():
    cs = chinh_sach_mau()
    bang(cs.cong_ghi.dang_mo is False, "tiền đề sai: cổng đang mở")
    duoc, ly_do = cs.duoc_goi(nguoi((VAI_BIEN_TAP,)), CC_GHI)
    bang(duoc is False, "cổng đóng mà công cụ GHI vẫn chạy — cổng thứ ba vô nghĩa")
    return "vai có đủ quyền ghi vẫn bị chặn"


@phep_kiem("2.3 Cổng ĐÓNG vẫn cho công cụ CHỈ ĐỌC chạy (không quá tay)")
def kiem_cong_dong_khong_chan_doc():
    cs = chinh_sach_mau()
    bang(cs.cong_ghi.dang_mo is False, "tiền đề sai: cổng đang mở")
    for vai in ((VAI_DOC,), (VAI_BIEN_TAP,)):
        for ten_cc in (CC_DOC, CC_DOC_2):
            duoc, ly_do = cs.duoc_goi(nguoi(vai), ten_cc)
            bang(
                duoc is True,
                "cổng đóng CHẶN LUÔN công cụ chỉ đọc %r cho vai %s — quá tay: "
                "chế độ quan sát thành chế độ chết máy, và người ta sẽ mở cổng "
                "ghi ra chỉ để đọc được. Lý do máy trả: %r" % (ten_cc, vai, ly_do),
            )
    return "chế độ chỉ-đọc vẫn đọc được — 2 vai × 2 công cụ"


@phep_kiem("2.4 Cổng đóng: lý do từ chối phải đổ cho CỔNG, không đổ cho VAI")
def kiem_ly_do_dung_cho():
    cs = chinh_sach_mau()
    _, ly_do = cs.duoc_goi(nguoi((VAI_BIEN_TAP,)), CC_GHI)
    bang(
        "cổng ghi" in ly_do and "ĐÓNG" in ly_do,
        "lý do không nói cổng đang đóng: %r — nói sai lý do thì quản trị đi sửa "
        "nhầm chỗ (đi cấp thêm quyền cho vai thay vì mở cổng)" % (ly_do,),
    )
    bang(
        "vai" not in ly_do.lower(),
        "lý do đổ tội cho vai trong khi lỗi là cổng đóng: %r" % (ly_do,),
    )
    return "thông điệp chỉ đúng chỗ cần sửa"


@phep_kiem("2.5 Cổng MỞ thì công cụ GHI đi qua — nhưng chỉ với vai có quyền ghi")
def kiem_cong_mo():
    cs = chinh_sach_mau()
    mo_cong(cs)
    duoc, ly_do = cs.duoc_goi(nguoi((VAI_BIEN_TAP,)), CC_GHI)
    bang(duoc is True, "cổng mở + vai có quyền ghi mà vẫn bị chặn: %r" % (ly_do,))
    duoc2, ly_do2 = cs.duoc_goi(nguoi((VAI_DOC,)), CC_GHI)
    bang(
        duoc2 is False,
        "cổng mở biến vai CHỈ ĐỌC thành vai ghi được — cổng toàn cục không được "
        "thay thế chính sách vai. Lý do máy trả: %r" % (ly_do2,),
    )
    return "cổng mở là điều kiện CẦN, không phải điều kiện ĐỦ"


@phep_kiem("2.6 Được cấp doc= KHÔNG tự động có ghi= (ba cổng độc lập)")
def kiem_doc_khong_keo_theo_ghi():
    cs = ChinhSach()
    cs.khai_cong_cu(CC_DOC, ghi=False)
    cs.khai_cong_cu(CC_GHI, ghi=True)
    cs.khai_vai(VAI_DOC, doc=[CC_DOC])
    mo_cong(cs)
    bang(cs.duoc_goi(nguoi((VAI_DOC,)), CC_DOC)[0] is True, "mất luôn quyền đọc")
    bang(
        cs.duoc_goi(nguoi((VAI_DOC,)), CC_GHI)[0] is False,
        "vai chỉ có doc= lại gọi được công cụ GHI — mô hình quyền trượt theo "
        "hướng 'đã đọc được thì cho sửa luôn'",
    )
    return "cổng mở, vai có đọc, vẫn không ghi được"


@phep_kiem("2.7 Công cụ ĐỌC cấp qua ghi= và công cụ GHI cấp qua doc= đều NỔ")
def kiem_khai_lech_loai():
    cs = ChinhSach()
    cs.khai_cong_cu(CC_DOC, ghi=False)
    cs.khai_cong_cu(CC_GHI, ghi=True)
    nem(
        LoiChinhSach,
        lambda: cs.khai_vai("v1", ghi=[CC_DOC]),
        "công cụ ĐỌC được nhận vào danh sách ghi= — hai loại trộn vào nhau",
    )
    nem(
        LoiChinhSach,
        lambda: cs.khai_vai("v2", doc=[CC_GHI]),
        "công cụ GHI được nhận vào danh sách doc= — quyền ghi cấp không tường minh",
    )
    return "hai chiều đều bị chặn lúc KHAI BÁO"


# ══════════════════════════════════════════════════════════════════════════
# Nhóm 3 — TRẠNG THÁI CỔNG: "mở một lần là mở mãi" có xảy ra không?
# ══════════════════════════════════════════════════════════════════════════


@phep_kiem("3.1 Mở → đóng → mở → đóng: trạng thái đi đúng cả hai chiều")
def kiem_cong_dao_chieu():
    cs = chinh_sach_mau()
    ai_do = nguoi((VAI_BIEN_TAP,))
    lich_su = []
    for vong in range(3):
        cs.cong_ghi.mo(ly_do="vòng %d" % vong, nguoi_mo=MA_BIA)
        lich_su.append(("mở", cs.cong_ghi.dang_mo, cs.duoc_goi(ai_do, CC_GHI)[0]))
        cs.cong_ghi.dong()
        lich_su.append(("đóng", cs.cong_ghi.dang_mo, cs.duoc_goi(ai_do, CC_GHI)[0]))
    for nhan, dang_mo, goi_duoc in lich_su:
        cho_doi = nhan == "mở"
        bang(
            dang_mo is cho_doi,
            "sau %r thì dang_mo=%r — cổng kẹt trạng thái" % (nhan, dang_mo),
        )
        bang(
            goi_duoc is cho_doi,
            "sau %r thì quyết định quyền ra %r — 'mở một lần là mở mãi'"
            % (nhan, goi_duoc),
        )
    return "3 vòng, 6 lần chuyển, quyết định quyền bám đúng từng lần"


@phep_kiem("3.2 mo() KHÔNG cho mở vô danh / không lý do")
def kiem_mo_phai_co_ly_do():
    for ly_do, nguoi_mo in (("", MA_BIA), ("điều tra", ""), ("", ""), (None, None)):
        c = CongGhi()
        nem(
            LoiChinhSach,
            lambda l=ly_do, n=nguoi_mo: c.mo(ly_do=l, nguoi_mo=n),
            "mở được cổng ghi với ly_do=%r nguoi_mo=%r" % (ly_do, nguoi_mo),
        )
        bang(c.dang_mo is False, "nổ xong mà cổng vẫn MỞ — nổ nửa vời còn tệ hơn")
    return "4 tổ hợp thiếu, và không tổ hợp nào mở hé được cổng"


@phep_kiem("3.3 CongGhi(mo=True) KHÔNG được mở cổng vô danh, không lý do")
def kiem_dung_cong_ghi_vo_danh():
    # `mo()` bắt buộc ly_do và nguoi_mo; hàm dựng thì trước đây không — hai
    # đường vào cùng một trạng thái, chỉ một đường có phép kiểm. Lỗ ấy ĐÃ BỊT
    # trong `quyen.CongGhi.__init__`, nên bài kiểm phải đòi đúng thứ mã nguồn
    # nay làm: NỔ. Bản cũ vẫn gọi `CongGhi(mo=True)` trần rồi mới xem tom_tat,
    # nên nó chết vì LoiChinhSach trước khi kịp kiểm gì — đỏ vì BÀI KIỂM lạc
    # hậu so với bản vá, không phải vì mã sai. Sửa 26/09/2026.
    nem(
        LoiChinhSach,
        lambda: CongGhi(mo=True),
        "CongGhi(mo=True) mở được cổng GHI toàn nhân với ly_do='' và "
        "nguoi_mo='' — hàm dựng đi vòng qua đúng phép kiểm mà mo() bắt buộc. "
        "Hệ quả: một chính sách dựng bằng ChinhSach(cong_ghi=CongGhi(mo=True)) "
        "chạy với cổng ghi MỞ mà nhật ký không trả lời được câu 'vì sao hôm ấy "
        "nhân đang mở ghi' — đúng câu mà chú thích của lớp này nói nó sinh ra "
        "để trả lời.",
    )
    # Thiếu MỘT trong hai cũng phải nổ, không chỉ thiếu cả hai.
    for ly_do, nguoi_mo in (("điều tra", ""), ("", MA_BIA)):
        nem(
            LoiChinhSach,
            lambda l=ly_do, n=nguoi_mo: CongGhi(mo=True, ly_do=l, nguoi_mo=n),
            "CongGhi(mo=True) lọt với ly_do=%r nguoi_mo=%r" % (ly_do, nguoi_mo),
        )
    # Và cửa chính vẫn phải đi qua được: bịt đường vòng KHÔNG được bịt luôn
    # cách dùng đúng, mà đó là kiểu "sửa" hay gặp nhất sau một bản vá bảo mật.
    c = CongGhi(mo=True, ly_do="điều tra sự cố 24/08", nguoi_mo=MA_BIA)
    bang(c.dang_mo is True, "khai đủ lý do và người mở mà cổng vẫn ĐÓNG")
    tt = c.tom_tat()
    bang(
        tt["ly_do"] == "điều tra sự cố 24/08" and tt["nguoi_mo"] == MA_BIA,
        "hàm dựng nhận lý do/người mở nhưng không giữ lại: %r" % (tt,),
    )
    # Mặc định vẫn là ĐÓNG — không lý do thì không cần, vì không mở gì cả.
    bang(CongGhi().dang_mo is False, "CongGhi() mặc định phải ĐÓNG")
    return "hai đường vào cùng một trạng thái, cùng một phép kiểm"


@phep_kiem("3.4 ChinhSach dùng ĐÚNG cổng được tiêm vào, không tự dựng cổng khác")
def kiem_cong_duoc_tiem():
    cong = CongGhi()
    cs = chinh_sach_mau(cong_ghi=cong)
    bang(cs.cong_ghi is cong, "ChinhSach sao chép cổng thay vì dùng chính nó")
    ai_do = nguoi((VAI_BIEN_TAP,))
    bang(cs.duoc_goi(ai_do, CC_GHI)[0] is False, "cổng tiêm vào đang đóng mà lọt")
    cong.mo(ly_do="mở từ bên ngoài", nguoi_mo=MA_BIA)
    bang(
        cs.duoc_goi(ai_do, CC_GHI)[0] is True,
        "mở cổng từ bên ngoài mà chính sách không thấy — hai cổng song song là "
        "kiểu hỏng tệ nhất: quản trị mở một cái, nhân nhìn cái kia",
    )
    return "một cổng duy nhất, nhìn từ cả hai phía"


@phep_kiem("3.5 tom_tat() mang được lý do và người mở (đặc tả hiện trạng)")
def kiem_tom_tat():
    c = CongGhi()
    bang(c.tom_tat() == {"dang_mo": False, "ly_do": "", "nguoi_mo": ""}, "tóm tắt ban đầu sai")
    c.mo(ly_do="điều tra sự cố 24/08", nguoi_mo=MA_BIA)
    tt = c.tom_tat()
    bang(tt["dang_mo"] is True and tt["ly_do"] == "điều tra sự cố 24/08", "tóm tắt sau mở sai")
    bang(tt["nguoi_mo"] == MA_BIA, "tóm tắt mất người mở")
    c.dong()
    sau = c.tom_tat()
    # ĐẶC TẢ HIỆN TRẠNG, không phải mong muốn: `dong()` KHÔNG xoá ly_do/nguoi_mo.
    # Ghi lại ở đây để lần sửa sau là một thay đổi CÓ Ý THỨC chứ không phải một
    # ca kiểm bỗng dưng đỏ. Chấp nhận được vì dang_mo=False vẫn nói đúng sự thật.
    bang(sau["dang_mo"] is False, "đóng rồi mà tóm tắt vẫn báo đang mở — nguy hiểm")
    bang(
        sau["ly_do"] == "điều tra sự cố 24/08",
        "hiện trạng đã đổi: dong() nay có xoá ly_do — cập nhật ca kiểm này",
    )
    tt["ly_do"] = "SỬA TỪ BÊN NGOÀI"
    bang(
        c.tom_tat()["ly_do"] == "điều tra sự cố 24/08",
        "tom_tat() trả về chính cấu trúc bên trong — sửa bản tóm tắt là sửa cổng",
    )
    return "dang_mo trung thực; bản tóm tắt là BẢN SAO"


# ══════════════════════════════════════════════════════════════════════════
# Nhóm 4 — RÒ RỈ TRẠNG THÁI QUA GIÁ TRỊ TRẢ VỀ
# ══════════════════════════════════════════════════════════════════════════


@phep_kiem("4.1 cong_cu_duoc_phep trả BẢN SAO — sửa nó không sửa được chính sách")
def kiem_khong_ro_ri_danh_sach_phep():
    cs = chinh_sach_mau()
    mo_cong(cs)
    ai_do = nguoi((VAI_DOC,))
    goc = cs.cong_cu_duoc_phep(ai_do)
    # THỨ TỰ LÀ SẮP XẾP, không phải thứ tự khai. `cong_cu_duoc_phep` lọc trên
    # `sorted(self._cong_cu)`, và phép kiểm 4.3 bên dưới chốt đúng hợp đồng ấy
    # (`phep == sorted(tinh_lai)`). Hai dòng dưới đây trước viết ngược
    # ([CC_DOC_2, CC_DOC] = kho… trước crm…), nên ca này ĐỎ vì BÀI KIỂM sai chứ
    # không phải mã sai — sửa 26/09/2026. Cố ý KHÔNG đổi thành so sánh tập hợp:
    # thứ tự ổn định là thứ `tools/list` của MCP dựa vào, và một so sánh
    # `sorted(...) == sorted(...)` sẽ thôi không đo nó nữa.
    bang(goc == [CC_DOC, CC_DOC_2], "tập ban đầu sai: %r" % (goc,))

    goc.append(CC_GHI)  # thử leo thang bằng cách sửa danh sách trả về
    goc.remove(CC_DOC)
    sau = cs.cong_cu_duoc_phep(ai_do)
    bang(
        sau == [CC_DOC, CC_DOC_2],
        "sửa danh sách trả về ĐỔI LUÔN chính sách bên trong: nay ra %r. Người gọi "
        "tự cấp cho mình %r." % (sau, CC_GHI),
    )
    bang(
        cs.duoc_goi(ai_do, CC_GHI)[0] is False,
        "thêm %r vào danh sách trả về là cấp được quyền ghi thật" % (CC_GHI,),
    )
    bang(sau is not goc, "hai lần gọi trả về CÙNG một đối tượng — vẫn là rò rỉ")
    return "thêm và bớt đều không xuyên qua được"


@phep_kiem("4.2 cong_cu_da_khai / cac_vai_da_khai cũng trả BẢN SAO")
def kiem_khong_ro_ri_so_dang_ky():
    cs = chinh_sach_mau()
    ds_cc = cs.cong_cu_da_khai()
    ds_cc.clear()
    ds_cc.append("gia_mao.cong_cu")
    bang(
        cs.cong_cu_da_khai() == [CC_DOC, CC_GHI, CC_DOC_2] or
        sorted(cs.cong_cu_da_khai()) == sorted([CC_DOC, CC_GHI, CC_DOC_2]),
        "xoá danh sách trả về làm rỗng luôn sổ công cụ: %r" % (cs.cong_cu_da_khai(),),
    )
    ds_vai = cs.cac_vai_da_khai()
    ds_vai.clear()
    bang(
        sorted(cs.cac_vai_da_khai()) == sorted([VAI_DOC, VAI_BIEN_TAP]),
        "xoá danh sách trả về làm rỗng luôn sổ vai: %r" % (cs.cac_vai_da_khai(),),
    )
    # Và sổ rỗng không được biến thành "cho phép tất cả": nếu xoá sổ mà quyền vẫn
    # còn thì phép kiểm trên xanh vì lý do sai.
    bang(cs.duoc_goi(nguoi((VAI_DOC,)), CC_DOC)[0] is True, "quyền biến mất sau khi sửa bản sao")
    return "cả sổ công cụ lẫn sổ vai"


@phep_kiem("4.3 cong_cu_duoc_phep là TẬP CON, và khớp từng ô với duoc_goi")
def kiem_tap_con_khop_duoc_goi():
    cs = chinh_sach_mau()
    for trang_thai in ("đóng", "mở"):
        if trang_thai == "mở":
            mo_cong(cs)
        for vai in ((VAI_DOC,), (VAI_BIEN_TAP,), ("vai-la",), (VAI_DOC, VAI_BIEN_TAP)):
            ai_do = nguoi(vai)
            phep = cs.cong_cu_duoc_phep(ai_do)
            tat_ca = cs.cong_cu_da_khai()
            bang(
                set(phep) <= set(tat_ca),
                "cong_cu_duoc_phep trả thứ KHÔNG có trong sổ công cụ: %r" % (phep,),
            )
            tinh_lai = [t for t in tat_ca if cs.duoc_goi(ai_do, t)[0]]
            bang(
                phep == sorted(tinh_lai),
                "cong_cu_duoc_phep (%r) lệch với duoc_goi (%r) — vai %r, cổng %s. "
                "Hai đường trả lời khác nhau cho cùng một câu hỏi thì tools/list "
                "hứa một đằng, lời gọi làm một nẻo." % (phep, tinh_lai, vai, trang_thai),
            )
    return "2 trạng thái cổng × 4 bộ vai, không ô nào lệch"


@phep_kiem("4.4 Công cụ GHI BIẾN MẤT khỏi cong_cu_duoc_phep khi cổng đóng")
def kiem_danh_sach_theo_thoi_diem():
    cs = chinh_sach_mau()
    ai_do = nguoi((VAI_BIEN_TAP,))
    bang(CC_GHI not in cs.cong_cu_duoc_phep(ai_do), "cổng đóng mà công cụ ghi còn trong danh sách")
    mo_cong(cs)
    bang(CC_GHI in cs.cong_cu_duoc_phep(ai_do), "cổng mở mà công cụ ghi không hiện ra")
    cs.cong_ghi.dong()
    bang(CC_GHI not in cs.cong_cu_duoc_phep(ai_do), "đóng lại mà công cụ ghi vẫn còn")
    return "tính theo thời điểm hỏi, không theo cấu hình tĩnh"


@phep_kiem("4.5 DanhTinh bất biến: không leo thang bằng cách gán thêm vai")
def kiem_danh_tinh_bat_bien():
    cs = chinh_sach_mau()
    ai_do = nguoi((VAI_DOC,))
    try:
        ai_do.vai = (VAI_BIEN_TAP,)  # type: ignore[misc]
        raise AssertionError(
            "gán được danh_tinh.vai — một trình điều khiển bên thứ ba chỉ cần "
            "một dòng là leo thang quyền"
        )
    except AssertionError:
        raise
    except Exception:
        pass
    mo_cong(cs)
    bang(cs.duoc_goi(ai_do, CC_GHI)[0] is False, "leo thang thành công dù gán bị chặn")
    return "frozen dataclass giữ được"


# ══════════════════════════════════════════════════════════════════════════
# Nhóm 5 — KHAI LẠI: khai hai lần thì cái nào thắng?
# ══════════════════════════════════════════════════════════════════════════


@phep_kiem("5.1 Khai lại công cụ với LOẠI KHÁC thì NỔ (không hạ quyền âm thầm)")
def kiem_khai_lai_doi_loai():
    cs = chinh_sach_mau()
    nem(
        LoiChinhSach,
        lambda: cs.khai_cong_cu(CC_GHI, ghi=False),
        "hạ %r từ GHI xuống ĐỌC bằng cách khai lại — mọi lần cấp quyền trước đó "
        "thành sai mà không ai biết" % (CC_GHI,),
    )
    nem(
        LoiChinhSach,
        lambda: cs.khai_cong_cu(CC_DOC, ghi=True),
        "nâng %r từ ĐỌC lên GHI bằng cách khai lại" % (CC_DOC,),
    )
    bang(cs.la_cong_cu_ghi(CC_GHI) is True, "nổ xong mà loại vẫn bị đổi")
    bang(cs.la_cong_cu_ghi(CC_DOC) is False, "nổ xong mà loại vẫn bị đổi")
    return "hai chiều đều nổ, và trạng thái không suy suyển"


@phep_kiem("5.2 Khai lại CÙNG loại, MÔ TẢ KHÁC: mô tả ĐẦU thắng (đặc tả hiện trạng)")
def kiem_khai_lai_doi_mo_ta():
    cs = ChinhSach()
    cs.khai_cong_cu(CC_DOC, ghi=False, mo_ta="mô tả gốc")
    tra_ve = cs.khai_cong_cu(CC_DOC, ghi=False, mo_ta="MÔ TẢ ĐÈ LÊN")
    # Hiện trạng: lời khai thứ hai bị bỏ qua hoàn toàn, không nổ, không đè.
    # Ghi lại vì đây là một lựa chọn CÓ THẬT chứ không phải chỗ chưa ai nghĩ tới:
    # nếu mai này đổi sang "cái sau thắng" thì đó là một cửa hạ quyền mới, và ca
    # kiểm này sẽ đỏ để nhắc.
    bang(
        cs.mo_ta(CC_DOC).mo_ta == "mô tả gốc",
        "lời khai thứ hai ĐÈ được mô tả — khai lại sửa được sổ công cụ",
    )
    bang(tra_ve is cs.mo_ta(CC_DOC), "khai lại trả về một đối tượng khác trong sổ")
    bang(len(cs.cong_cu_da_khai()) == 1, "khai lại đẻ ra một mục thứ hai")
    return "nhất quán: cái đầu thắng, im lặng, loại thì không đổi được"


@phep_kiem("5.3 Khai lại vai với danh sách NGẮN HƠN phải THU HỒI quyền")
def kiem_khai_lai_vai_thu_hoi():
    # `khai_vai` dùng setdefault().update() nên lời khai sau CỘNG DỒN vào lời
    # khai trước. Đây là ca ĐỎ CỐ Ý — xem phần in ra ở cuối tệp.
    cs = ChinhSach()
    cs.khai_cong_cu(CC_DOC, ghi=False)
    cs.khai_cong_cu(CC_DOC_2, ghi=False)
    cs.khai_cong_cu(CC_GHI, ghi=True)
    cs.khai_vai(VAI_BIEN_TAP, doc=[CC_DOC, CC_DOC_2], ghi=[CC_GHI])
    # Nạp lại chính sách sau khi quản trị RÚT bớt quyền của vai này:
    cs.khai_vai(VAI_BIEN_TAP, doc=[CC_DOC], ghi=[])
    mo_cong(cs)
    ai_do = nguoi((VAI_BIEN_TAP,))
    bang(
        cs.duoc_goi(ai_do, CC_GHI)[0] is False,
        "khai lại vai %r KHÔNG rút được quyền GHI %r: lời khai sau cộng dồn vào "
        "lời khai trước (setdefault().update()) thay vì thay thế. Không có API "
        "thu hồi nào khác trong mô-đun. Hệ quả: nạp lại cấu hình sau khi cắt "
        "quyền một vai thì quyền cũ VẪN CÒN, và quản trị tin rằng đã cắt."
        % (VAI_BIEN_TAP, CC_GHI),
    )
    bang(
        cs.duoc_goi(ai_do, CC_DOC_2)[0] is False,
        "quyền ĐỌC %r cũng không rút được bằng cách khai lại" % (CC_DOC_2,),
    )
    return "khai lại là THAY THẾ, không phải cộng dồn"


@phep_kiem("5.4 Khai lại vai là KHAI BÁO trạng thái cuối, cả khi mở rộng")
def kiem_khai_lai_vai_mo_rong():
    """Ca này từng kỳ vọng NGƯỢC LẠI, và việc nó đổi chiều là có chủ ý.

    Bản đầu của bộ kiểm này viết 5.3 (thu hẹp phải THU HỒI) và 5.4 (mở rộng phải
    CỘNG DỒN) — hai kỳ vọng không thể cùng đúng trên một hàm. Khi `khai_vai` còn
    dùng `setdefault().update()` thì 5.4 xanh và 5.3 đỏ; đó là cách bộ kiểm chỉ ra
    rằng mô-đun KHÔNG có đường thu hồi quyền nào.

    Quyết định ngày 26/09/2026: `khai_vai` KHAI BÁO trạng thái cuối của một vai.
    Chọn như vậy vì trong hai kiểu hỏng, hỏng-không-rút-được-quyền nặng hơn hẳn
    hỏng-phải-khai-đủ-một-lần: cấp nhầm thì còn sửa được, còn không thu hồi được
    thì không có đường sửa nào cả.

    Hệ quả cho người gọi: muốn mở rộng thì khai LẠI CẢ TẬP, đừng khai thêm từng
    mẩu. Nếu về sau thật sự cần cộng dồn (nạp chính sách từ nhiều tệp), hãy thêm
    một hàm RIÊNG có tên nói rõ điều đó — đừng đổi `khai_vai` về update().
    """
    cs = ChinhSach()
    cs.khai_cong_cu(CC_DOC, ghi=False)
    cs.khai_cong_cu(CC_DOC_2, ghi=False)
    cs.khai_vai(VAI_DOC, doc=[CC_DOC])

    # Khai LẠI chỉ với công cụ thứ hai: đây là KHAI BÁO, nên công cụ thứ nhất RỤNG.
    cs.khai_vai(VAI_DOC, doc=[CC_DOC_2])
    phep = cs.cong_cu_duoc_phep(nguoi((VAI_DOC,)))
    bang(
        sorted(phep) == [CC_DOC_2],
        "khai lại vai phải THAY THẾ tập quyền, nhưng nhận được %r — nếu thấy cả "
        "hai công cụ thì `khai_vai` đã quay về cộng dồn, và 5.3 sẽ đỏ theo" % (phep,),
    )

    # Mở rộng ĐÚNG CÁCH: khai lại cả tập.
    cs.khai_vai(VAI_DOC, doc=[CC_DOC, CC_DOC_2])
    phep2 = cs.cong_cu_duoc_phep(nguoi((VAI_DOC,)))
    bang(
        sorted(phep2) == sorted([CC_DOC, CC_DOC_2]),
        "khai lại cả tập phải cấp đủ cả hai, nhận được %r" % (phep2,),
    )
    return "khai lại = khai báo trạng thái cuối; mở rộng bằng cách khai đủ tập"


# ══════════════════════════════════════════════════════════════════════════
# Nhóm 6 — HOA/THƯỜNG VÀ KHOẢNG TRẮNG: bất kỳ câu trả lời nào, MIỄN LÀ NHẤT QUÁN
# ══════════════════════════════════════════════════════════════════════════


@phep_kiem("6.1 Tên công cụ viết HOA bị từ chối ngay lúc KHAI")
def kiem_ten_cong_cu_hoa():
    cs = ChinhSach()
    for xau in ("CRM.GHI", "Crm.ghi", "crm.GHI"):
        nem(
            LoiChinhSach,
            lambda x=xau: cs.khai_cong_cu(x),
            "tên công cụ %r được nhận — %r và %r thành hai công cụ khác nhau, "
            "và chỉ một cái có trong chính sách" % (xau, xau, xau.lower()),
        )
    bang(cs.cong_cu_da_khai() == [], "tên hỏng vẫn lọt vào sổ công cụ")
    return "3 biến thể hoa, không cái nào vào sổ"


@phep_kiem("6.2 Tên công cụ có KHOẢNG TRẮNG THỪA bị từ chối ngay lúc KHAI")
def kiem_ten_cong_cu_khoang_trang():
    cs = ChinhSach()
    for xau in (" crm.ghi", "crm.ghi ", " crm.ghi ", "crm .ghi", "crm. ghi", "crm.ghi\n"):
        nem(
            LoiChinhSach,
            lambda x=xau: cs.khai_cong_cu(x),
            "tên công cụ %r được nhận — mẫu không neo hai đầu thì một dấu xuống "
            "dòng cũng lọt, và nhật ký một-dòng-một-bản-ghi bị bẻ gãy" % (xau,),
        )
    bang(cs.cong_cu_da_khai() == [], "tên hỏng vẫn lọt vào sổ công cụ")
    return "6 biến thể khoảng trắng, kể cả ký tự xuống dòng"


@phep_kiem("6.3 duoc_goi NHẤT QUÁN với khai: biến thể hoa/khoảng trắng đều TỪ CHỐI")
def kiem_duoc_goi_nhat_quan():
    cs = chinh_sach_mau()
    mo_cong(cs)
    ai_do = nguoi((VAI_BIEN_TAP,))
    bang(cs.duoc_goi(ai_do, CC_GHI)[0] is True, "tiền đề sai: tên chuẩn phải đi qua")
    for xau in (
        CC_GHI.upper(),
        CC_GHI.capitalize(),
        " " + CC_GHI,
        CC_GHI + " ",
        " " + CC_GHI + " ",
        CC_GHI + "\n",
        "\t" + CC_GHI,
    ):
        duoc, _ = cs.duoc_goi(ai_do, xau)
        bang(
            duoc is False,
            "khai từ chối %r nhưng duoc_goi lại CHO QUA — không nhất quán giữa "
            "hai đường là một lỗi vượt quyền: chặn 'crm.ghi' mà lọt 'CRM.GHI' "
            "thì coi như không chặn" % (xau,),
        )
    return "7 biến thể; khai chặn thì gọi cũng chặn"


@phep_kiem("6.4 Tên VAI: hai lớp (ChinhSach và DanhTinh) cùng một luật")
def kiem_ten_vai_nhat_quan():
    cs = chinh_sach_mau()
    for xau in ("BIEN-TAP", "Bien-Tap", " bien-tap", "bien-tap ", "bien tap"):
        nem(
            LoiChinhSach,
            lambda x=xau: cs.khai_vai(x, doc=[CC_DOC]),
            "ChinhSach nhận tên vai %r" % (xau,),
        )
        nem(
            LoiDanhTinh,
            lambda x=xau: DanhTinh(ma=MA_BIA, vai=(x,), nguon=NGUON_BIA),
            "DanhTinh nhận tên vai %r trong khi ChinhSach từ chối — hai lớp lệch "
            "luật thì một bên cấp, một bên không nhận, và quyền rơi vào khe giữa"
            % (xau,),
        )
    return "5 biến thể × 2 lớp, cùng một câu trả lời"


@phep_kiem("6.5 Khai vai với tên công cụ lệch hoa/thường thì NỔ, không cấp âm thầm")
def kiem_khai_vai_ten_lech():
    cs = chinh_sach_mau()
    nem(
        LoiChinhSach,
        lambda: cs.khai_vai("vai-lech", doc=[CC_DOC.upper()]),
        "cấp được quyền trên tên công cụ viết hoa — một quyền treo lơ lửng không "
        "khớp công cụ nào, và quản trị tin rằng mình đã cấp",
    )
    return "quyền gõ lệch không trở thành quyền câm"


# ══════════════════════════════════════════════════════════════════════════
# Nhóm 7 — BIÊN VÀ RANH GIỚI TẦNG
# ══════════════════════════════════════════════════════════════════════════


@phep_kiem("7.1 duoc_goi LUÔN trả lý do khác rỗng, kể cả khi CHO PHÉP")
def kiem_luon_co_ly_do():
    cs = chinh_sach_mau()
    mo_cong(cs)
    cac_ca = [
        (nguoi((VAI_DOC,)), CC_DOC),
        (nguoi((VAI_BIEN_TAP,)), CC_GHI),
        (nguoi((VAI_DOC,)), CC_GHI),
        (nguoi(("vai-la",)), CC_DOC),
        (None, CC_DOC),
        (nguoi((VAI_DOC,)), CC_CHUA_KHAI),
    ]
    for ai_do, ten_cc in cac_ca:
        duoc, ly_do = cs.duoc_goi(ai_do, ten_cc)
        bang(isinstance(duoc, bool), "kết quả không phải bool: %r" % (duoc,))
        bang(
            isinstance(ly_do, str) and len(ly_do.strip()) > 10,
            "lý do rỗng hoặc cụt cho ca (%r, %r): %r — một dòng nhật ký chỉ ghi "
            "'thành công' không trả lời được câu hỏi đầu tiên sau sự cố"
            % (ai_do, ten_cc, ly_do),
        )
        bang(
            ly_do.startswith("cho phép") if duoc else ly_do.startswith("từ chối"),
            "lý do %r không khớp quyết định %r" % (ly_do, duoc),
        )
    return "6 ca, cả cho phép lẫn từ chối"


@phep_kiem("7.2 Nhiều vai: chỉ cần MỘT vai đủ quyền là qua, không cần tất cả")
def kiem_nhieu_vai():
    cs = chinh_sach_mau()
    mo_cong(cs)
    ai_do = nguoi(("vai-la-hoan-toan", VAI_BIEN_TAP, "vai-la-nua"))
    bang(cs.duoc_goi(ai_do, CC_GHI)[0] is True, "vai lạ đi kèm làm mất quyền ghi")
    chi_vai_la = nguoi(("vai-la-hoan-toan", "vai-la-nua"))
    bang(
        cs.duoc_goi(chi_vai_la, CC_GHI)[0] is False,
        "toàn vai lạ mà vẫn qua — phép hợp tập đang cộng cả vai không tồn tại",
    )
    return "hợp tập đúng chiều, không nới thêm"


@phep_kiem("7.3 la_cong_cu_ghi và mo_ta trung thực với sổ công cụ")
def kiem_tra_cuu():
    cs = chinh_sach_mau()
    bang(cs.la_cong_cu_ghi(CC_GHI) is True, "công cụ GHI bị báo là đọc")
    bang(cs.la_cong_cu_ghi(CC_DOC) is False, "công cụ ĐỌC bị báo là ghi")
    bang(
        cs.la_cong_cu_ghi(CC_CHUA_KHAI) is False,
        "công cụ CHƯA KHAI bị báo là ghi — nhưng nguy hiểm hơn là nếu nó báo "
        "False vì 'không biết' thì lời gọi có thể đi nhầm sang nhánh chỉ đọc",
    )
    bang(cs.mo_ta(CC_CHUA_KHAI) is None, "mo_ta bịa ra mô tả cho công cụ chưa khai")
    mt = cs.mo_ta(CC_GHI)
    bang(isinstance(mt, MoTaCongCu) and mt.loai == GHI and mt.la_ghi is True, "mô tả sai")
    bang(cs.mo_ta(CC_DOC).loai == DOC, "loại công cụ đọc sai")
    return "đã khai / chưa khai / đọc / ghi"


@phep_kiem("7.4 Nhánh 'có ĐỌC mà không có GHI' KHÔNG tới được qua API công khai")
def kiem_nhanh_chet():
    # `duoc_goi` có một nhánh nói riêng ca "vai chỉ có quyền ĐỌC, không có quyền
    # GHI". Để tới được nhánh ấy, một công cụ GHI phải nằm trong danh sách doc=
    # của một vai. Đo xem có đường nào làm được thế không.
    cs = ChinhSach()
    cs.khai_cong_cu(CC_GHI, ghi=True)
    nem(
        LoiChinhSach,
        lambda: cs.khai_vai(VAI_DOC, doc=[CC_GHI]),
        "đường 1 mở: cấp thẳng công cụ GHI qua doc=",
    )
    cs2 = ChinhSach()
    cs2.khai_cong_cu(CC_DOC, ghi=False)
    cs2.khai_vai(VAI_DOC, doc=[CC_DOC])
    nem(
        LoiChinhSach,
        lambda: cs2.khai_cong_cu(CC_DOC, ghi=True),
        "đường 2 mở: cấp lúc còn là ĐỌC rồi nâng lên GHI",
    )
    # Cả hai đường đều bị chặn ⇒ nhánh ấy là MÃ CHẾT. Không phải lỗ hổng, nhưng
    # là một thông điệp lỗi được viết rất kỹ mà không ai gặp bao giờ.
    cs3 = ChinhSach()
    cs3.khai_cong_cu(CC_GHI, ghi=True)
    cs3.khai_vai(VAI_DOC, ghi=[CC_GHI])
    mo_cong(cs3)
    _, ly_do = cs3.duoc_goi(nguoi(("vai-khac",)), CC_GHI)
    bang(
        "chỉ có quyền ĐỌC" not in ly_do,
        "tới được nhánh tưởng là chết — cập nhật ca kiểm này",
    )
    return "mã chết: 2 đường vào đều bị chặn từ lúc khai"


@phep_kiem("7.5 Ranh giới tầng: lớp quyền KHÔNG kiểm hạn danh tính (dinh_tuyen kiểm)")
def kiem_ranh_gioi_han_danh_tinh():
    cs = chinh_sach_mau()
    mo_cong(cs)
    het_han = nguoi((VAI_BIEN_TAP,), het_han=time.time() - 3600)
    bang(het_han.con_hieu_luc() is False, "tiền đề sai: danh tính này chưa hết hạn")
    duoc, _ = cs.duoc_goi(het_han, CC_GHI)
    # ĐẶC TẢ HIỆN TRẠNG. `nhan/dinh_tuyen.py` gọi `con_hieu_luc()` TRƯỚC
    # `duoc_goi()`, nên trên đường gọi thật danh tính hết hạn không tới được đây.
    # Ghi lại để lần sửa sau là một thay đổi có ý thức: mô-đun này tự nhận "lớp
    # quyền không được TIN rằng lớp trên đã kiểm" cho ca None, nhưng lại TIN cho
    # ca hết hạn. Không nhất quán về chiều sâu phòng thủ, chưa phải lỗ hổng.
    bang(
        duoc is True,
        "hiện trạng đã đổi: lớp quyền nay có kiểm hạn danh tính — tin tốt, cập "
        "nhật ca kiểm này và bỏ ghi chú về ranh giới tầng",
    )
    return "quyền chỉ trả lời 'được làm gì', hạn là việc của dinh_tuyen"


@phep_kiem("7.6 Chính sách này KHÔNG có ký tự đại diện dưới bất kỳ dạng nào")
def kiem_khong_dau_sao_o_dau_ca():
    cs = chinh_sach_mau()
    mo_cong(cs)
    ai_do = nguoi((VAI_BIEN_TAP,))
    for xau in ("*", "crm.*", "*.*", CC_DOC[:4] + "*"):
        bang(
            cs.duoc_goi(ai_do, xau)[0] is False,
            "gọi được bằng ký tự đại diện %r" % (xau,),
        )
    nem(LoiChinhSach, lambda: cs.khai_cong_cu("crm.*"), "khai được công cụ có dấu sao")
    return "không khai được, không gọi được"


@phep_kiem("7.7 hoan_nguyen_khai_cong_cu KHÔNG được thành đường hạ quyền âm thầm")
def kiem_hoan_nguyen_khai_cong_cu():
    # Hàm này thêm 26/09/2026 cho `dinh_tuyen.Nhan.dang_ky` (đăng ký hỏng nửa
    # chừng thì hoàn nguyên). Nó GỠ một công cụ khỏi sổ, nên nó cũng là đường
    # duy nhất trong lớp này có thể làm một dòng cấp quyền trỏ vào hư không.
    # Hai giới hạn nó tự khai phải có phép kiểm, nếu không thì chúng chỉ là chú
    # thích.
    cs = chinh_sach_mau()

    # 1. Đang có vai được cấp thì TỪ CHỐI gỡ — cả phía ĐỌC lẫn phía GHI.
    nem(
        LoiChinhSach,
        lambda: cs.hoan_nguyen_khai_cong_cu(CC_DOC),
        "gỡ được %r trong khi vai %r đang được cấp nó. Dòng cấp quyền ấy thành "
        "trỏ vào hư không, và lần khai_vai sau mới nổ — xa nguyên nhân."
        % (CC_DOC, VAI_DOC),
    )
    nem(
        LoiChinhSach,
        lambda: cs.hoan_nguyen_khai_cong_cu(CC_GHI),
        "gỡ được công cụ GHI %r trong khi vai %r đang được cấp nó" % (CC_GHI, VAI_BIEN_TAP),
    )
    bang(
        CC_DOC in cs.cong_cu_da_khai() and CC_GHI in cs.cong_cu_da_khai(),
        "từ chối gỡ mà vẫn gỡ mất: %r" % (cs.cong_cu_da_khai(),),
    )
    # Và quyền phải còn nguyên sau lần từ chối — một lần nổ giữa chừng không
    # được để lại sổ méo.
    bang(cs.duoc_goi(nguoi((VAI_DOC,)), CC_DOC)[0], "quyền ĐỌC mất sau lần gỡ bị từ chối")

    # 2. Chưa vai nào cấp thì gỡ được, và gỡ đúng một cái.
    cs.khai_cong_cu("crm.moi_khai", ghi=False, mo_ta="chưa vai nào được cấp")
    bang(cs.hoan_nguyen_khai_cong_cu("crm.moi_khai") is True, "gỡ phải trả True")
    bang(
        "crm.moi_khai" not in cs.cong_cu_da_khai(),
        "gỡ xong mà vẫn còn trong sổ: %r" % (cs.cong_cu_da_khai(),),
    )
    bang(
        sorted(cs.cong_cu_da_khai()) == sorted([CC_DOC, CC_DOC_2, CC_GHI]),
        "gỡ quá tay sang công cụ khác: %r" % (cs.cong_cu_da_khai(),),
    )

    # 3. Không có gì để gỡ thì trả False, KHÔNG nổ: chỗ gọi là một khối dọn dẹp,
    #    và một khối dọn dẹp tự ném lỗi sẽ che mất lỗi GỐC.
    bang(
        cs.hoan_nguyen_khai_cong_cu(CC_CHUA_KHAI) is False,
        "gỡ thứ không có phải trả False, không được nổ",
    )
    return "từ chối khi đang được cấp · gỡ đúng một cái · vắng thì False"


CAC_PHEP_KIEM = [
    kiem_cong_cu_chua_khai,
    kiem_vai_chua_khai,
    kiem_vai_rong,
    kiem_danh_tinh_none,
    kiem_chinh_sach_trong,
    kiem_ky_tu_dai_dien,
    kiem_go_nham_ten_cong_cu,
    kiem_cong_mac_dinh_dong,
    kiem_cong_dong_chan_ghi,
    kiem_cong_dong_khong_chan_doc,
    kiem_ly_do_dung_cho,
    kiem_cong_mo,
    kiem_doc_khong_keo_theo_ghi,
    kiem_khai_lech_loai,
    kiem_cong_dao_chieu,
    kiem_mo_phai_co_ly_do,
    kiem_dung_cong_ghi_vo_danh,
    kiem_cong_duoc_tiem,
    kiem_tom_tat,
    kiem_khong_ro_ri_danh_sach_phep,
    kiem_khong_ro_ri_so_dang_ky,
    kiem_tap_con_khop_duoc_goi,
    kiem_danh_sach_theo_thoi_diem,
    kiem_danh_tinh_bat_bien,
    kiem_khai_lai_doi_loai,
    kiem_khai_lai_doi_mo_ta,
    kiem_khai_lai_vai_thu_hoi,
    kiem_khai_lai_vai_mo_rong,
    kiem_ten_cong_cu_hoa,
    kiem_ten_cong_cu_khoang_trang,
    kiem_duoc_goi_nhat_quan,
    kiem_ten_vai_nhat_quan,
    kiem_khai_vai_ten_lech,
    kiem_luon_co_ly_do,
    kiem_nhieu_vai,
    kiem_tra_cuu,
    kiem_nhanh_chet,
    kiem_ranh_gioi_han_danh_tinh,
    kiem_khong_dau_sao_o_dau_ca,
    kiem_hoan_nguyen_khai_cong_cu,
]

# KHÔNG CÒN CA ĐỎ CÓ CHỦ Ý — 26/09/2026. Cả hai ca từng nằm ở đây đã được vá
# trong `nhan/quyen.py`, và bảng này để RỖNG chứ không xoá đi: rỗng thì mọi ca
# đỏ từ nay đều là ca "NGOÀI DỰ KIẾN" và được in kèm lời nhắc đọc kỹ, còn xoá
# bảng đi thì nhánh phân loại ấy biến mất cùng.
#
# Hai ca đã vá, ghi lại để người sau nhận ra nếu chúng đỏ lại:
#   · 3.3 — `CongGhi.__init__` nhận mo=True mà không đòi ly_do/nguoi_mo, trong
#     khi `CongGhi.mo()` thì đòi. Cổng GHI toàn nhân mở được không dấu vết.
#     Nay hàm dựng nổ y như `mo()`, và bài kiểm đòi đúng tiếng nổ ấy.
#   · 5.3 — `khai_vai` dùng setdefault().update() nên chỉ CỘNG DỒN, không thu
#     hồi được quyền. Nay khai_vai KHAI BÁO trạng thái cuối.
CA_DO_CO_Y = {}


def main():
    print("=" * 78)
    print("BÀI TỰ KIỂM — nhan/quyen.py (ai được gọi công cụ nào)")
    print("Python {}.{}.{}".format(*sys.version_info[:3]))
    print("KHÔNG cần mạng, KHÔNG đọc biến môi trường, KHÔNG chạm đĩa.")
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
        print("Nghĩa là gì: danh sách trắng đúng là danh sách trắng — công cụ chưa khai,")
        print("vai chưa khai, vai rỗng và danh tính None đều bị từ chối; cổng ghi chặn đúng")
        print("công cụ ghi và KHÔNG chặn nhầm công cụ chỉ đọc; cổng đi được cả hai chiều;")
        print("danh sách trả về là bản sao nên không sửa ngược được chính sách; và tên công")
        print("cụ/tên vai bị xử lý nhất quán giữa lúc khai và lúc gọi.")
        print()
        print("Nghĩa là gì KHÔNG: bài này KHÔNG kiểm nhật ký, KHÔNG kiểm hạn mức, KHÔNG kiểm")
        print("xác thực, KHÔNG kiểm bảy bước của nhan/dinh_tuyen.py. Câu công bố")
        print('\"một chủ thể, một phép thử quyền, một dòng nhật ký\" mới được đo đúng vế GIỮA.')
    else:
        print("KẾT QUẢ: {}/{} ĐẠT, {} HỎNG.".format(so_dat, len(_KET_QUA), so_hong))
        print()
        print("Các phép kiểm hỏng:")
        for ten, dat, ghi_chu in _KET_QUA:
            if not dat:
                co_y = CA_DO_CO_Y.get(ten)
                print("  - {}: {}".format(ten, ghi_chu))
                if co_y:
                    print("    ĐỎ CỐ Ý — lỗi trong nhan/quyen.py, không phải trong bài kiểm:")
                    print("    {}".format(co_y))
        ngoai_y = [t for t, d, _ in _KET_QUA if not d and t not in CA_DO_CO_Y]
        print()
        if ngoai_y:
            print("CÓ {} CA ĐỎ NGOÀI DỰ KIẾN — đọc phần trên trước khi làm gì khác:".format(len(ngoai_y)))
            for t in ngoai_y:
                print("  · {}".format(t))
        else:
            print("Mọi ca đỏ đều nằm trong danh sách ĐỎ CỐ Ý ở cuối tệp này. Bài kiểm KHÔNG")
            print("tự sửa mã nguồn — người điều phối quyết định sửa thế nào. Mã thoát 1 là")
            print("đúng: cổng CI phải đỏ cho tới khi lỗi được xử hoặc được ghi nhận là chấp")
            print("nhận có ý thức.")
    print("=" * 78)
    return 0 if tat_ca_dat else 1


if __name__ == "__main__":
    sys.exit(main())
