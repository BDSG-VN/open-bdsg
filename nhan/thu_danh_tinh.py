#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nhan/thu_danh_tinh.py — BÀI TỰ KIỂM CHO `nhan/danh_tinh.py`.

CHẠY:
    .venv/bin/python nhan/thu_danh_tinh.py

KHÔNG cần mạng. KHÔNG đọc biến môi trường thật. KHÔNG ghi ra đĩa. Toàn bộ bài
chạy xong dưới một giây.

═══ VÌ SAO CÓ BÀI NÀY ═══

README của kho và trang bdsg.vn/open-bdsg nói công khai rằng mọi lời gọi công
cụ "luôn có MỘT CHỦ THỂ, MỘT PHÉP THỬ QUYỀN và MỘT DÒNG NHẬT KÝ". Vế thứ nhất —
CHỦ THỂ — do đúng tệp này quyết định. Trước hôm nay khẳng định ấy chưa có một
phép đo nào đứng sau, mà một khẳng định công khai không đo được chính là họ lỗi
"hỏng mà không báo" mà dự án đã đặt tên riêng.

Bài này KHÔNG kiểm chất lượng mật mã (tệp nguồn cố ý không tự cài mật mã), KHÔNG
kiểm quyền (xem `nhan/quyen.py`), KHÔNG kiểm nhật ký (xem `nhan/nhat_ky.py`). Nó
chỉ kiểm đúng một câu: "ai đang gọi" được trả lời đúng, hay bị từ chối rõ ràng.

═══ BẢY CÂU HỎI BÀI NÀY TRẢ LỜI ═══

  1. Danh tính HẾT HẠN có bị từ chối không, kể cả ở đúng giây ranh giới?
  2. `so_sanh_hang_dinh` có thật sự đi qua `hmac.compare_digest`, hay chỉ là một
     dấu `==` khoác tên đẹp? (Phép kiểm ĐỌC MÃ NGUỒN bằng `ast`, không đoán.)
  3. Danh tính KHÔNG vai có bị nhầm thành "có mọi vai" không?
  4. `tom_tat()` — thứ đi thẳng vào nhật ký — có làm lộ trường `ten` không?
  5. Gỡ một nguồn rồi thì nguồn ấy còn xác thực được nữa không?
  6. Xác thực qua một nguồn không tồn tại có âm thầm hoá thành "khách vãng lai"?
  7. Đầu vào dị dạng (rỗng, None, cực dài, unicode kết hợp, byte NUL, xuống
     dòng) có bị chặn ở cửa dựng đối tượng không?

═══ MỘT PHÉP KIỂM TRONG BÀI NÀY ĐANG ĐỎ, VÀ ĐỎ LÀ ĐÚNG ═══

`thu_ma_co_xuong_dong_bi_tu_choi` và `thu_vai_nguon_co_xuong_dong_bi_tu_choi`
đang HỎNG vì mã nguồn thật sự sai, không phải vì bài kiểm sai. Xem ghi chú ngay
trên hai hàm ấy. Bài kiểm cố ý để nguyên màu đỏ: người điều phối quyết định sửa
thế nào, người viết bài kiểm không tự sửa nhân.

MÃ THOÁT: 0 = mọi phép kiểm ĐẠT. 1 = có phép kiểm HỎNG.

Viết ngày 26/09/2026. Python 3.9.6.
"""

from __future__ import annotations

import ast
import hmac
import importlib.util
import json
import os
import sys
import traceback
from typing import Any, Dict, List, Optional, Tuple

THU_MUC = os.path.dirname(os.path.abspath(__file__))
TEP_NGUON = os.path.join(THU_MUC, "danh_tinh.py")

# ──────────────────────────────────────────────────────────────────────────────
# Nạp mô-đun THẲNG TỪ TỆP, không đi qua `nhan/__init__.py`.
#
# Lý do: `nhan/__init__.py` kéo theo cả sáu mô-đun của nhân. Nếu một mô-đun anh
# em hỏng thì bài kiểm này chết vì lý do chẳng liên quan gì đến danh tính, và
# người đọc sẽ tưởng danh tính hỏng. `danh_tinh.py` không có import tương đối
# nào nên nạp thẳng được.
# ──────────────────────────────────────────────────────────────────────────────
if __package__:
    from . import danh_tinh as _dt  # pragma: no cover — lối chạy khi là gói
else:
    _spec = importlib.util.spec_from_file_location("nhan_danh_tinh", TEP_NGUON)
    if _spec is None or _spec.loader is None:
        print("HONG: khong nap duoc {}".format(TEP_NGUON))
        sys.exit(1)
    _dt = importlib.util.module_from_spec(_spec)
    sys.modules["nhan_danh_tinh"] = _dt
    _spec.loader.exec_module(_dt)

DanhTinh = _dt.DanhTinh
LoiDanhTinh = _dt.LoiDanhTinh
BoXacThuc = _dt.BoXacThuc
so_sanh_hang_dinh = _dt.so_sanh_hang_dinh
nguon_bang_khoa = _dt.nguon_bang_khoa
NGUON_KHOA_API = _dt.NGUON_KHOA_API
NGUON_PHIEN = _dt.NGUON_PHIEN

# ──────────────────────────────────────────────────────────────────────────────
# Chuỗi BỊA dùng xuyên suốt.
#
# Không có chuỗi nào dưới đây là khoá thật, từng là khoá thật, hay giống khoá
# thật. Chúng cố ý tự tố cáo mình là đồ bịa ngay trong nội dung, để nếu một chuỗi
# nào lọt ra nhật ký hay màn hình thì người đọc biết ngay đó là bài kiểm.
# ──────────────────────────────────────────────────────────────────────────────
KHOA_BIA = "KHOA-BIA-CHI-DUNG-TRONG-BAI-KIEM-KHONG-PHAI-KHOA-THAT"
KHOA_BIA_KHAC = "KHOA-BIA-KHAC-CUNG-KHONG-PHAI-KHOA-THAT"
TEN_BIA = "TEN-NGUOI-BIA-KHONG-DUOC-PHEP-VAO-NHAT-KY"


# ──────────────────────────────────────────────────────────────────────────────
# Khung chạy thử tối giản (không dùng pytest — kho này không có pytest trong
# .venv, và một bài tự kiểm cần cài thêm mới chạy được là bài không ai chạy).
# ──────────────────────────────────────────────────────────────────────────────

_KET_QUA: List[Tuple[str, bool, str]] = []


def phep_kiem(ten: str):
    def bao(ham):
        def chay():
            try:
                ghi_chu = ham()
                _KET_QUA.append((ten, True, ghi_chu or ""))
                print("  DAT   {}{}".format(ten, "  — " + ghi_chu if ghi_chu else ""))
                return True
            except AssertionError as loi:
                _KET_QUA.append((ten, False, str(loi)))
                print("  HONG  {}  — {}".format(ten, loi))
                return False
            except Exception as loi:  # noqa: BLE001 — bài tự kiểm phải bắt hết
                vet = traceback.format_exc(limit=3).strip().splitlines()[-1]
                _KET_QUA.append((ten, False, "{}: {}".format(type(loi).__name__, loi)))
                print("  HONG  {}  — {}: {}".format(ten, type(loi).__name__, loi))
                print("        {}".format(vet))
                return False

        chay.__name__ = ham.__name__
        return chay

    return bao


def bao_dam(dieu_kien: Any, cau: str) -> None:
    if not dieu_kien:
        raise AssertionError(cau)


def bao_dam_nem(lop_loi, ham, cau: str) -> BaseException:
    """Khẳng định `ham()` ném đúng loại lỗi. Trả lại lỗi để soi thông điệp."""
    try:
        gia_tri = ham()
    except lop_loi as loi:
        return loi
    except Exception as loi:  # noqa: BLE001
        raise AssertionError(
            "{} — ném {} chứ không phải {}: {}".format(
                cau, type(loi).__name__, getattr(lop_loi, "__name__", lop_loi), loi
            )
        )
    raise AssertionError("{} — không ném gì, trả về {!r}".format(cau, gia_tri))


def danh_tinh_mau(**kw) -> "DanhTinh":
    """Danh tính hợp lệ tối thiểu; ghi đè từng trường bằng tham số khoá."""
    tham_so = {"ma": "nguoi-thu-01", "vai": ("doc-gia",), "nguon": "nguon-thu"}
    tham_so.update(kw)
    return DanhTinh(**tham_so)


# ══════════════════════════════════════════════════════════════════════════════
# NHÓM A — DỰNG DanhTinh: cửa duy nhất, và phải là cửa hẹp
# ══════════════════════════════════════════════════════════════════════════════


@phep_kiem("A1  vai là chuỗi thì tự gói thành tuple một phần tử")
def thu_vai_chuoi_thanh_tuple():
    dt = danh_tinh_mau(vai="quan-tri")
    bao_dam(dt.vai == ("quan-tri",), "vai chuỗi phải thành tuple, nhận {!r}".format(dt.vai))
    bao_dam(isinstance(dt.vai, tuple), "vai phải là tuple, không phải {}".format(type(dt.vai)))
    return "'quan-tri' -> ('quan-tri',)"


@phep_kiem("A2  vai dạng danh sách giữ nguyên thứ tự và hoá tuple")
def thu_vai_danh_sach():
    dt = danh_tinh_mau(vai=["b-vai", "a-vai"])
    bao_dam(dt.vai == ("b-vai", "a-vai"), "thứ tự vai bị đổi: {!r}".format(dt.vai))
    bao_dam(isinstance(dt.vai, tuple), "vai phải là tuple")
    return "thứ tự giữ nguyên, kiểu là tuple"


@phep_kiem("A3  không vai mà dựng kiểu thường thì bị chặn, và lỗi chỉ đường thoát")
def thu_khong_vai_bi_chan():
    loi = bao_dam_nem(
        LoiDanhTinh, lambda: danh_tinh_mau(vai=()), "danh tính không vai dựng kiểu thường"
    )
    bao_dam("khong_vai" in str(loi), "thông điệp lỗi phải chỉ sang khong_vai(): {}".format(loi))
    return "bị chặn, và lỗi chỉ sang DanhTinh.khong_vai()"


@phep_kiem("A4  khong_vai() dựng được danh tính KHÔNG vai một cách cố ý")
def thu_khong_vai_co_y():
    dt = DanhTinh.khong_vai("nguoi-thu-02", nguon="nguon-thu")
    bao_dam(dt.vai == (), "khong_vai phải cho vai rỗng, nhận {!r}".format(dt.vai))
    bao_dam(dt.ma == "nguoi-thu-02", "mã bị đổi")
    bao_dam(dt.nguon == "nguon-thu", "nguồn bị mất")
    # Vai "tam" dùng để lách __post_init__ KHÔNG được sót lại.
    bao_dam(not dt.co_vai("tam"), "vai tạm 'tam' bị sót lại trong danh tính")
    return "vai rỗng, không sót vai tạm 'tam'"


@phep_kiem("A5  mã sai mẫu bị từ chối (rỗng, dấu cách, NUL, tiền tố xấu, quá dài)")
def thu_ma_sai_mau():
    xau = [
        ("", "mã rỗng"),
        ("-bat-dau-bang-gach", "mã bắt đầu bằng gạch nối"),
        ("co khoang trang", "mã có khoảng trắng"),
        ("co\ttab", "mã có tab"),
        ("co\x00nul", "mã có byte NUL"),
        ("co/gach-cheo", "mã có gạch chéo"),
        ("mã-có-dấu", "mã có ký tự tiếng Việt có dấu"),
        ("é-unicode-ket-hop", "mã có ký tự unicode kết hợp"),
        ("a" * 129, "mã dài 129 ký tự"),
        ("x" * 100000, "mã cực dài 100k ký tự"),
    ]
    for gia_tri, mo_ta in xau:
        bao_dam_nem(LoiDanhTinh, lambda g=gia_tri: danh_tinh_mau(ma=g), mo_ta)
    # Đúng 128 ký tự thì phải NHẬN — nếu không thì bài kiểm ranh giới ở trên vô nghĩa.
    bao_dam(danh_tinh_mau(ma="a" * 128).ma == "a" * 128, "mã 128 ký tự phải hợp lệ")
    return "{} dạng xấu bị chặn; ranh giới 128 ký tự vẫn nhận".format(len(xau))


@phep_kiem("A6  mã có XUỐNG DÒNG cuối chuỗi bị từ chối  [ĐANG ĐỎ — LỖI THẬT]")
def thu_ma_co_xuong_dong_bi_tu_choi():
    # LỖI THẬT TRONG nhan/danh_tinh.py, dòng 61.
    #
    # Chú thích ngay trên MAU_MA nói thẳng ý định: "một mã chứa xuống dòng sẽ bẻ
    # gãy nhật ký một-dòng-một-bản-ghi. Chặn ngay từ lúc dựng đối tượng."
    #
    # Nhưng trong Python, `$` khớp ở CUỐI CHUỖI **hoặc ngay trước một ký tự xuống
    # dòng ở cuối chuỗi**. Vì vậy "quan-tri\n" khớp `^...$` và lọt qua. Muốn chặn
    # phải dùng `\Z` thay cho `$`, hoặc `re.fullmatch` (fullmatch KHÔNG đủ: nó
    # vẫn khớp vì `$` vẫn nằm trong mẫu — phải đổi chính `$` thành `\Z`).
    #
    # Đây là phép kiểm ĐANG ĐỎ vì mã sai, không phải vì bài kiểm sai. Không tự sửa.
    bao_dam_nem(
        LoiDanhTinh,
        lambda: danh_tinh_mau(ma="nguoi-thu-01\n"),
        "mã kết thúc bằng xuống dòng phải bị từ chối (chú thích MAU_MA hứa vậy)",
    )
    return "xuống dòng cuối mã bị chặn"


@phep_kiem("A7  vai/nguồn có XUỐNG DÒNG cuối chuỗi bị từ chối  [ĐANG ĐỎ — LỖI THẬT]")
def thu_vai_nguon_co_xuong_dong_bi_tu_choi():
    # Cùng một nguyên nhân với A6: MAU_VAI và MAU_NGUON cũng kết bằng `$`.
    # Hệ quả riêng của vai: "quan-tri" và "quan-tri\n" là HAI vai khác nhau với
    # `quyen.py` nhưng in ra màn hình thì giống hệt nhau.
    bao_dam_nem(
        LoiDanhTinh,
        lambda: danh_tinh_mau(vai=("quan-tri\n",)),
        "tên vai kết thúc bằng xuống dòng phải bị từ chối",
    )
    bao_dam_nem(
        LoiDanhTinh,
        lambda: danh_tinh_mau(nguon="nguon-thu\n"),
        "tên nguồn kết thúc bằng xuống dòng phải bị từ chối",
    )
    return "xuống dòng cuối vai và nguồn bị chặn"


@phep_kiem("A8  nguồn là BẮT BUỘC — mặc định rỗng không dựng được")
def thu_nguon_bat_buoc():
    loi = bao_dam_nem(
        LoiDanhTinh,
        lambda: DanhTinh(ma="nguoi-thu-03", vai=("doc-gia",)),
        "dựng danh tính mà không khai nguồn",
    )
    bao_dam("nguồn" in str(loi), "lỗi phải nói về nguồn: {}".format(loi))
    # Kể cả lối tắt khong_vai() cũng không được lách chuyện này.
    bao_dam_nem(
        LoiDanhTinh, lambda: DanhTinh.khong_vai("nguoi-thu-03"), "khong_vai() không khai nguồn"
    )
    return "không có nguồn thì không có danh tính, kể cả qua khong_vai()"


@phep_kiem("A9  tên vai sai mẫu bị từ chối")
def thu_vai_sai_mau():
    xau = ["", "Quan-Tri", "quan.tri", "quan tri", "-quan-tri", "q" * 65, "quản-trị"]
    for v in xau:
        bao_dam_nem(LoiDanhTinh, lambda x=v: danh_tinh_mau(vai=(x,)), "vai xấu {!r}".format(v))
    bao_dam(danh_tinh_mau(vai=("q" * 64,)).vai == ("q" * 64,), "vai 64 ký tự phải hợp lệ")
    return "{} tên vai xấu bị chặn; ranh giới 64 ký tự vẫn nhận".format(len(xau))


@phep_kiem("A10 vai bị lặp bị từ chối (khoá hạn mức và nhật ký sẽ đếm đôi)")
def thu_vai_lap():
    bao_dam_nem(
        LoiDanhTinh,
        lambda: danh_tinh_mau(vai=("doc-gia", "quan-tri", "doc-gia")),
        "vai lặp phải bị từ chối",
    )
    return "vai lặp bị chặn"


@phep_kiem("A11 het_han sai kiểu bị từ chối, số hợp lệ được nhận")
def thu_het_han_sai_kieu():
    for xau in ["1700000000", [1], {"a": 1}, object()]:
        bao_dam_nem(
            LoiDanhTinh, lambda x=xau: danh_tinh_mau(het_han=x), "het_han kiểu {}".format(type(xau))
        )
    bao_dam(danh_tinh_mau(het_han=1700000000).het_han == 1700000000, "số nguyên phải nhận")
    bao_dam(danh_tinh_mau(het_han=1700000000.5).het_han == 1700000000.5, "số thực phải nhận")
    bao_dam(danh_tinh_mau(het_han=None).het_han is None, "None phải nhận")
    return "4 kiểu xấu bị chặn; int/float/None được nhận"


@phep_kiem("A12 DanhTinh BẤT BIẾN — không leo thang quyền bằng một phép gán")
def thu_bat_bien():
    dt = danh_tinh_mau(vai=("doc-gia",))

    def gan_vai():
        dt.vai = ("quan-tri",)  # type: ignore[misc]

    def gan_ma():
        dt.ma = "ke-khac"  # type: ignore[misc]

    bao_dam_nem(Exception, gan_vai, "gán vai lên danh tính đã dựng")
    bao_dam_nem(Exception, gan_ma, "gán mã lên danh tính đã dựng")
    bao_dam(dt.vai == ("doc-gia",), "vai bị đổi thật: {!r}".format(dt.vai))
    bao_dam(dt.ma == "nguoi-thu-01", "mã bị đổi thật")
    return "gán vai/mã đều bị chặn, giá trị không đổi"


@phep_kiem("A13 đầu vào DỊ DẠNG đều nổ ngay lúc dựng, không ai lọt im lặng")
def thu_dau_vao_di_dang():
    di_dang = [
        {"ma": None},
        {"ma": 123},
        {"ma": b"bytes-khong-phai-str"},
        {"vai": None},
        {"vai": 123},
        {"vai": (None,)},
        {"vai": (b"vai-bytes",)},
        {"nguon": None},
        {"nguon": 123},
    ]
    for tham_so in di_dang:
        # Chấp nhận LoiDanhTinh HOẶC TypeError: điều bắt buộc là NỔ NGAY LÚC
        # DỰNG, không phải lọt qua rồi vỡ ở tầng trên. (Ghi chú: `vai` sai kiểu
        # hiện nổ TypeError chứ không phải LoiDanhTinh — xem báo cáo.)
        bao_dam_nem(
            (LoiDanhTinh, TypeError),
            lambda t=tham_so: danh_tinh_mau(**t),
            "đầu vào dị dạng {!r}".format(tham_so),
        )
    return "{} dạng dị đều nổ lúc dựng".format(len(di_dang))


# ══════════════════════════════════════════════════════════════════════════════
# NHÓM B — HẾT HẠN: đúng giây ranh giới, và lệch một giây về mỗi bên
# ══════════════════════════════════════════════════════════════════════════════


@phep_kiem("B1  het_han=None ⇒ còn hiệu lực (nhân không tự bịa ra một hạn)")
def thu_khong_khai_han():
    dt = danh_tinh_mau(het_han=None)
    bao_dam(dt.con_hieu_luc(0.0) is True, "không khai hạn thì phải còn hiệu lực")
    bao_dam(dt.con_hieu_luc(10.0 ** 12) is True, "không khai hạn thì mãi còn hiệu lực")
    return "None ⇒ True ở mọi mốc thời gian"


@phep_kiem("B2  RANH GIỚI hết hạn: trước 1 giây / đúng giây / sau 1 giây")
def thu_ranh_gioi_het_han():
    moc = 1_700_000_000.0
    dt = danh_tinh_mau(het_han=moc)
    bao_dam(dt.con_hieu_luc(moc - 1.0) is True, "trước hạn 1 giây phải CÒN hiệu lực")
    bao_dam(dt.con_hieu_luc(moc) is False, "ĐÚNG giây hết hạn phải HẾT hiệu lực")
    bao_dam(dt.con_hieu_luc(moc + 1.0) is False, "sau hạn 1 giây phải HẾT hiệu lực")
    # Sát ranh giới hơn nữa: một phần nghìn giây về mỗi bên.
    bao_dam(dt.con_hieu_luc(moc - 0.001) is True, "trước hạn 1ms phải còn hiệu lực")
    bao_dam(dt.con_hieu_luc(moc + 0.001) is False, "sau hạn 1ms phải hết hiệu lực")
    return "hợp đồng là bay_gio < het_han (đúng giây hết hạn ⇒ TỪ CHỐI)"


@phep_kiem("B3  không truyền đồng hồ thì dùng giờ hệ thống, không mặc định 'còn hạn'")
def thu_dong_ho_mac_dinh():
    qua_khu = danh_tinh_mau(het_han=1.0)  # 1970
    tuong_lai = danh_tinh_mau(het_han=10.0 ** 12)  # năm 33658
    bao_dam(qua_khu.con_hieu_luc() is False, "danh tính hết hạn năm 1970 vẫn được coi là còn hạn")
    bao_dam(tuong_lai.con_hieu_luc() is True, "danh tính hạn xa bị coi là hết hạn")
    return "giờ hệ thống được dùng thật"


# ══════════════════════════════════════════════════════════════════════════════
# NHÓM C — VAI: "không có vai nào" tuyệt đối không được hoá thành "có mọi vai"
# ══════════════════════════════════════════════════════════════════════════════


@phep_kiem("C1  co_vai trả đúng cho vai có và vai không có")
def thu_co_vai():
    dt = danh_tinh_mau(vai=("doc-gia", "bien-tap"))
    bao_dam(dt.co_vai("doc-gia") is True, "vai có mà báo không")
    bao_dam(dt.co_vai("bien-tap") is True, "vai có mà báo không")
    bao_dam(dt.co_vai("quan-tri") is False, "vai KHÔNG có mà báo có")
    bao_dam(dt.co_vai("doc-gi") is False, "khớp tiền tố bị nhận nhầm là khớp")
    bao_dam(dt.co_vai("doc-gia-x") is False, "khớp hậu tố bị nhận nhầm là khớp")
    return "khớp đúng-tuyệt-đối, không khớp một phần"


@phep_kiem("C2  danh tính KHÔNG vai trả False cho MỌI vai được hỏi")
def thu_khong_vai_khong_phai_moi_vai():
    dt = DanhTinh.khong_vai("nguoi-thu-04", nguon="nguon-thu")
    for v in ["quan-tri", "doc-gia", "", "*", "tam", "root", "admin"]:
        bao_dam(dt.co_vai(v) is False, "danh tính không vai lại nhận có vai {!r}".format(v))
    bao_dam(len(dt.vai) == 0, "vai phải rỗng")
    bao_dam(bool(dt.vai) is False, "vai rỗng phải falsy để tầng quyền chặn được")
    return "7 vai hỏi thử đều False, kể cả '*' và 'tam'"


# ══════════════════════════════════════════════════════════════════════════════
# NHÓM D — tom_tat(): thứ đi THẲNG vào nhật ký, nên phải sạch
# ══════════════════════════════════════════════════════════════════════════════


@phep_kiem("D1  tom_tat KHÔNG lộ tên người, và không lộ chuỗi bịa nào khác")
def thu_tom_tat_khong_lo_ten():
    dt = danh_tinh_mau(ten=TEN_BIA)
    tt = dt.tom_tat()
    van_ban = json.dumps(tt, ensure_ascii=False, sort_keys=True, default=str)
    bao_dam(TEN_BIA not in van_ban, "TÊN BỊA lọt vào bản tóm tắt: {}".format(van_ban))
    bao_dam("ten" not in tt, "khoá 'ten' không được có trong bản tóm tắt: {!r}".format(tt))
    bao_dam(set(tt) == {"ma", "vai", "nguon"}, "bộ khoá bản tóm tắt sai: {!r}".format(sorted(tt)))
    # Và đối tượng vẫn giữ tên cho tầng giao diện dùng — chỉ nhật ký mới không thấy.
    bao_dam(dt.ten == TEN_BIA, "tên phải còn trên đối tượng, chỉ là không vào tóm tắt")
    return "chỉ {ma, vai, nguon}; tên ở lại trên đối tượng"


@phep_kiem("D2  tom_tat trả BẢN SAO của vai — sửa nó không chạm được danh tính")
def thu_tom_tat_ban_sao():
    dt = danh_tinh_mau(vai=("doc-gia",))
    tt = dt.tom_tat()
    bao_dam(tt["vai"] == ["doc-gia"], "vai trong tóm tắt phải là danh sách")
    tt["vai"].append("quan-tri")  # type: ignore[union-attr]
    bao_dam(dt.vai == ("doc-gia",), "sửa bản tóm tắt lại đổi được danh tính: {!r}".format(dt.vai))
    bao_dam(dt.tom_tat()["vai"] == ["doc-gia"], "bản tóm tắt sau đó bị nhiễm")
    return "bản tóm tắt là bản sao, không phải cửa hậu"


@phep_kiem("D3  tom_tat đi lọt qua JSON một dòng (hợp đồng của nhat_ky.py)")
def thu_tom_tat_json_mot_dong():
    dt = danh_tinh_mau(vai=("doc-gia", "bien-tap"))
    dong = json.dumps(dt.tom_tat(), ensure_ascii=False, sort_keys=True, default=str)
    bao_dam("\n" not in dong, "bản tóm tắt sinh ra nhiều dòng: {!r}".format(dong))
    bao_dam(json.loads(dong)["ma"] == dt.ma, "đi qua JSON rồi mất mã")
    return "một dòng, đọc lại được"


# ══════════════════════════════════════════════════════════════════════════════
# NHÓM E — so_sanh_hang_dinh: đọc cả HÀNH VI lẫn MÃ NGUỒN
# ══════════════════════════════════════════════════════════════════════════════


@phep_kiem("E1  so sánh cho kết quả đúng với chuỗi bằng nhau và khác nhau")
def thu_so_sanh_ket_qua():
    bao_dam(so_sanh_hang_dinh(KHOA_BIA, KHOA_BIA) is True, "hai chuỗi bằng nhau phải True")
    bao_dam(so_sanh_hang_dinh(KHOA_BIA, KHOA_BIA_KHAC) is False, "hai chuỗi khác phải False")
    bao_dam(so_sanh_hang_dinh("", "") is True, "hai chuỗi rỗng bằng nhau")
    bao_dam(so_sanh_hang_dinh("", KHOA_BIA) is False, "rỗng khác không rỗng")
    # Khác đúng MỘT ký tự ở cuối — chỗ phép so sánh ẩu hay bỏ sót nhất.
    bao_dam(
        so_sanh_hang_dinh(KHOA_BIA, KHOA_BIA[:-1] + "X") is False,
        "khác một ký tự cuối mà vẫn báo bằng nhau",
    )
    bao_dam(
        so_sanh_hang_dinh(KHOA_BIA, "X" + KHOA_BIA[1:]) is False,
        "khác một ký tự đầu mà vẫn báo bằng nhau",
    )
    return "6 cặp, kể cả lệch một ký tự ở hai đầu"


@phep_kiem("E2  HAI CHUỖI KHÁC ĐỘ DÀI: trả False, không nổ")
def thu_so_sanh_khac_do_dai():
    bao_dam(so_sanh_hang_dinh(KHOA_BIA, KHOA_BIA + "them") is False, "dài hơn phải False")
    bao_dam(so_sanh_hang_dinh(KHOA_BIA, KHOA_BIA[:5]) is False, "ngắn hơn phải False")
    bao_dam(so_sanh_hang_dinh("a", "a" * 10000) is False, "lệch rất xa phải False")
    bao_dam(so_sanh_hang_dinh("", "a") is False, "rỗng vs một ký tự phải False")
    return "4 cặp lệch độ dài, không cặp nào nổ"


@phep_kiem("E3  nhận cả str lẫn bytes, và trộn hai kiểu vẫn đúng")
def thu_so_sanh_str_va_bytes():
    bao_dam(so_sanh_hang_dinh(KHOA_BIA, KHOA_BIA.encode("utf-8")) is True, "str vs bytes bằng")
    bao_dam(so_sanh_hang_dinh(KHOA_BIA.encode("utf-8"), KHOA_BIA) is True, "bytes vs str bằng")
    bao_dam(
        so_sanh_hang_dinh(KHOA_BIA.encode("utf-8"), KHOA_BIA.encode("utf-8")) is True,
        "bytes vs bytes bằng",
    )
    bao_dam(
        so_sanh_hang_dinh(KHOA_BIA, KHOA_BIA_KHAC.encode("utf-8")) is False, "str vs bytes khác"
    )
    return "str/bytes/trộn — bốn tổ hợp đều đúng"


@phep_kiem("E4  unicode không-ASCII so sánh được (chính chỗ compare_digest trần sẽ nổ)")
def thu_so_sanh_unicode():
    bi_mat = "bí-mật-bịa-không-phải-khoá-thật"
    bao_dam(so_sanh_hang_dinh(bi_mat, bi_mat) is True, "chuỗi unicode bằng nhau phải True")
    bao_dam(so_sanh_hang_dinh(bi_mat, bi_mat + "x") is False, "chuỗi unicode khác phải False")
    # Chứng minh việc mã hoá utf-8 trong hàm là CẦN: gọi thẳng compare_digest với
    # chuỗi không-ASCII sẽ nổ. Nếu ngày nào đó dòng encode bị bỏ, phép kiểm này đỏ.
    bao_dam_nem(
        TypeError,
        lambda: hmac.compare_digest(bi_mat, bi_mat),
        "compare_digest trần đáng lẽ phải nổ với chuỗi không-ASCII",
    )
    # Hai chuỗi TRÔNG GIỐNG NHAU nhưng khác cách dựng unicode phải KHÁC nhau.
    bao_dam(so_sanh_hang_dinh("é", "é") is False, "NFC và NFD không được coi là bằng nhau")
    return "utf-8 được mã hoá trước; NFC ≠ NFD"


@phep_kiem("E5  ĐỌC MÃ NGUỒN: hàm gọi hmac.compare_digest, không có '==' trần")
def thu_khong_dung_bang_bang():
    with open(TEP_NGUON, "r", encoding="utf-8") as tep:
        cay = ast.parse(tep.read(), filename=TEP_NGUON)
    ham = None
    for nut in ast.walk(cay):
        if isinstance(nut, ast.FunctionDef) and nut.name == "so_sanh_hang_dinh":
            ham = nut
            break
    bao_dam(ham is not None, "không tìm thấy hàm so_sanh_hang_dinh trong mã nguồn")

    goi_compare = []
    so_sanh_bang = []
    for nut in ast.walk(ham):
        if isinstance(nut, ast.Call):
            goi_compare.append(ast.dump(nut.func))
        if isinstance(nut, ast.Compare):
            for phep in nut.ops:
                if isinstance(phep, (ast.Eq, ast.NotEq)):
                    so_sanh_bang.append(ast.dump(nut))

    bao_dam(
        any("compare_digest" in g for g in goi_compare),
        "hàm KHÔNG gọi hmac.compare_digest; nó gọi: {}".format(goi_compare),
    )
    bao_dam(
        not so_sanh_bang,
        "hàm dùng '==' hoặc '!=' trần bên trong — đó là rò rỉ thời gian: {}".format(so_sanh_bang),
    )
    return "có compare_digest, không có == / != nào"


@phep_kiem("E6  đầu vào dị dạng nổ chứ KHÔNG âm thầm trả True")
def thu_so_sanh_di_dang():
    di_dang = [(None, "a"), ("a", None), (None, None), (1, 1), (["a"], ["a"]), ({}, {})]
    for a, b in di_dang:
        try:
            ket_qua = so_sanh_hang_dinh(a, b)
        except TypeError:
            continue
        except Exception as loi:  # noqa: BLE001
            raise AssertionError(
                "so sánh {!r} vs {!r} ném {}: {}".format(a, b, type(loi).__name__, loi)
            )
        raise AssertionError(
            "so sánh dị dạng {!r} vs {!r} không nổ mà trả {!r}".format(a, b, ket_qua)
        )
    return "{} cặp dị dạng đều nổ TypeError".format(len(di_dang))


# ══════════════════════════════════════════════════════════════════════════════
# NHÓM F — BoXacThuc: sổ đăng ký nguồn và cửa đổi chứng thư lấy danh tính
# ══════════════════════════════════════════════════════════════════════════════


def bo_mau(bay_gio: float = 1_000_000.0):
    """Bộ xác thực với đồng hồ TIÊM VÀO — không chờ thật, không đọc giờ máy."""
    hop = {"t": bay_gio}
    bo = BoXacThuc(dong_ho=lambda: hop["t"])
    return bo, hop


@phep_kiem("F1  đăng ký nguồn rồi liệt kê ra đúng, theo thứ tự đã sắp")
def thu_dang_ky_va_liet_ke():
    bo, _ = bo_mau()
    bao_dam(bo.cac_nguon() == [], "bộ mới phải rỗng, nhận {!r}".format(bo.cac_nguon()))
    bo.dang_ky_nguon("z-nguon", lambda ct: None)
    bo.dang_ky_nguon("a-nguon", lambda ct: None)
    bao_dam(bo.cac_nguon() == ["a-nguon", "z-nguon"], "phải sắp xếp: {!r}".format(bo.cac_nguon()))
    return "rỗng lúc đầu, sắp xếp lúc liệt kê"


@phep_kiem("F2  đăng ký ĐÈ một nguồn đã có bị chặn (chống chiếm quyền xác thực)")
def thu_dang_ky_trung():
    bo, _ = bo_mau()
    bo.dang_ky_nguon(NGUON_KHOA_API, lambda ct: None)
    loi = bao_dam_nem(
        LoiDanhTinh,
        lambda: bo.dang_ky_nguon(NGUON_KHOA_API, lambda ct: None),
        "đăng ký đè lên nguồn đã có",
    )
    bao_dam("gỡ" in str(loi), "lỗi phải chỉ đường gỡ tường minh: {}".format(loi))
    return "đè bị chặn, lỗi chỉ sang go_nguon()"


@phep_kiem("F3  tên nguồn xấu và hàm không gọi được đều bị chặn")
def thu_dang_ky_dau_vao_xau():
    bo, _ = bo_mau()
    for ten in ["", None, "Nguon-Hoa", "nguon.cham", "nguon co khoang trang", "-nguon", "n" * 65]:
        bao_dam_nem(
            LoiDanhTinh,
            lambda t=ten: bo.dang_ky_nguon(t, lambda ct: None),
            "tên nguồn xấu {!r}".format(ten),
        )
    for ham in [None, "khong-phai-ham", 42, {}]:
        bao_dam_nem(
            LoiDanhTinh,
            lambda h=ham: bo.dang_ky_nguon("nguon-hop-le", h),
            "hàm xác thực không gọi được {!r}".format(ham),
        )
    bao_dam(bo.cac_nguon() == [], "không cái nào được lọt vào sổ: {!r}".format(bo.cac_nguon()))
    return "7 tên xấu + 4 hàm xấu bị chặn; sổ vẫn rỗng"


@phep_kiem("F4  GỠ một nguồn thì nguồn ấy KHÔNG xác thực được nữa; nguồn kia còn nguyên")
def thu_go_nguon():
    bo, _ = bo_mau()
    dt_a = DanhTinh(ma="nguoi-a", vai=("doc-gia",), nguon="nguon-a")
    dt_b = DanhTinh(ma="nguoi-b", vai=("doc-gia",), nguon="nguon-b")
    bo.dang_ky_nguon("nguon-a", nguon_bang_khoa({KHOA_BIA: dt_a}, "nguon-a"))
    bo.dang_ky_nguon("nguon-b", nguon_bang_khoa({KHOA_BIA_KHAC: dt_b}, "nguon-b"))

    bao_dam(bo.xac_thuc("nguon-a", KHOA_BIA) is dt_a, "trước khi gỡ, nguồn a phải chạy")
    bao_dam(bo.xac_thuc("nguon-b", KHOA_BIA_KHAC) is dt_b, "trước khi gỡ, nguồn b phải chạy")

    bo.go_nguon("nguon-a")

    bao_dam(
        bo.xac_thuc("nguon-a", KHOA_BIA) is None,
        "NGUỒN ĐÃ GỠ VẪN XÁC THỰC ĐƯỢC — chứng thư cũ sống sót sau khi thu hồi nguồn",
    )
    bao_dam("nguon-a" not in bo.cac_nguon(), "nguồn đã gỡ còn trong sổ: {!r}".format(bo.cac_nguon()))
    bao_dam(bo.xac_thuc("nguon-b", KHOA_BIA_KHAC) is dt_b, "gỡ nguồn a lại làm hỏng nguồn b")
    # Gỡ một nguồn không tồn tại không được nổ (idempotent).
    bo.go_nguon("nguon-khong-co")
    bao_dam(bo.cac_nguon() == ["nguon-b"], "gỡ nguồn lạ làm hỏng sổ: {!r}".format(bo.cac_nguon()))
    return "nguồn đã gỡ chết hẳn; nguồn còn lại không bị vạ lây"


@phep_kiem("F5  nguồn KHÔNG tồn tại: trả None + LÝ DO, không hoá thành khách vãng lai")
def thu_nguon_khong_ton_tai():
    bo, _ = bo_mau()
    bo.dang_ky_nguon("nguon-that", lambda ct: None)

    dt = bo.xac_thuc("nguon-ma", KHOA_BIA)
    bao_dam(dt is None, "nguồn không tồn tại lại trả về danh tính: {!r}".format(dt))

    dt2, ly_do = bo.xac_thuc_ky("nguon-ma", KHOA_BIA)
    bao_dam(dt2 is None, "xac_thuc_ky cũng phải trả None")
    bao_dam(ly_do, "phải có LÝ DO — None không kèm lý do là None âm thầm")
    bao_dam("không xác định được danh tính" in ly_do, "lý do phải nói rõ: {!r}".format(ly_do))

    # Cả nguồn rỗng và nguồn None cũng vậy.
    for nguon_xau in ["", None]:
        d, l = bo.xac_thuc_ky(nguon_xau, KHOA_BIA)
        bao_dam(d is None, "nguồn {!r} phải cho None".format(nguon_xau))
        bao_dam(l, "nguồn {!r} phải kèm lý do".format(nguon_xau))
    return "None + lý do; tầng trên có cái để ghi nhật ký"


@phep_kiem("F6  chứng thư rỗng / None / sai kiểu đều bị từ chối trước khi gọi nguồn")
def thu_chung_thu_xau():
    bo, _ = bo_mau()
    dem = {"so_lan": 0}

    def nguon_dem(chung_thu):
        dem["so_lan"] += 1
        return DanhTinh(ma="nguoi-c", vai=("doc-gia",), nguon="nguon-c")

    bo.dang_ky_nguon("nguon-c", nguon_dem)

    for xau in ["", None, b"bytes", 123, [], {}]:
        dt, ly_do = bo.xac_thuc_ky("nguon-c", xau)
        bao_dam(dt is None, "chứng thư {!r} lại ra danh tính".format(xau))
        bao_dam(ly_do, "chứng thư {!r} phải kèm lý do".format(xau))
    bao_dam(
        dem["so_lan"] == 0,
        "chứng thư xấu vẫn bị đẩy xuống hàm xác thực {} lần".format(dem["so_lan"]),
    )
    # Chứng thư cực dài thì được phép xuống nguồn, nhưng không được ra danh tính.
    dt, _ = bo.xac_thuc_ky("nguon-c", "x" * 1_000_000)
    bao_dam(isinstance(dt, DanhTinh), "chứng thư dài hợp lệ vẫn phải đi qua nguồn")
    return "6 dạng chứng thư xấu bị chặn NGAY, nguồn không bị gọi"


@phep_kiem("F7  hàm xác thực NỔ ⇒ từ chối, không sập nhân, không hoá 'cho qua'")
def thu_nguon_no():
    bo, _ = bo_mau()

    def nguon_no(chung_thu):
        raise RuntimeError("LDAP-bia-khong-noi-duoc")

    bo.dang_ky_nguon("nguon-no", nguon_no)
    dt, ly_do = bo.xac_thuc_ky("nguon-no", KHOA_BIA)
    bao_dam(dt is None, "nguồn nổ mà vẫn ra danh tính: {!r}".format(dt))
    bao_dam("nổ" in ly_do or "RuntimeError" in ly_do, "lý do phải nói nguồn nổ: {!r}".format(ly_do))
    bao_dam(KHOA_BIA not in ly_do, "lý do làm lộ chứng thư")

    # Kể cả BaseException-ish nặng như KeyboardInterrupt thì không bắt (đúng),
    # nhưng ValueError/KeyError/TypeError đều phải thành từ chối.
    for lop in [ValueError, KeyError, TypeError, ZeroDivisionError]:
        ten = "nguon-no-{}".format(lop.__name__.lower())

        def no(chung_thu, l=lop):
            raise l("bia")

        bo.dang_ky_nguon(ten, no)
        d, l = bo.xac_thuc_ky(ten, KHOA_BIA)
        bao_dam(d is None, "nguồn ném {} mà vẫn ra danh tính".format(lop.__name__))
    return "5 kiểu nổ đều thành TỪ CHỐI"


@phep_kiem("F8  nguồn trả về thứ KHÔNG PHẢI DanhTinh đều bị từ chối")
def thu_nguon_tra_sai_kieu():
    bo, _ = bo_mau()
    tra_ve = [
        {"ma": "gia-mao", "vai": ["quan-tri"]},
        "chuoi-khong-phai-danh-tinh",
        42,
        True,
        ["quan-tri"],
        object(),
    ]
    for i, gia_tri in enumerate(tra_ve):
        ten = "nguon-sai-{}".format(i)
        bo.dang_ky_nguon(ten, lambda ct, g=gia_tri: g)
        dt, ly_do = bo.xac_thuc_ky(ten, KHOA_BIA)
        bao_dam(dt is None, "nguồn trả {!r} mà nhân vẫn nhận".format(gia_tri))
        bao_dam(ly_do, "phải kèm lý do")
    return "{} kiểu trả về giả đều bị chặn (kể cả dict có khoá 'vai')".format(len(tra_ve))


@phep_kiem("F9  nguồn A không phát hành được danh tính mang nhãn nguồn B")
def thu_nhan_nguon_khong_khop():
    bo, _ = bo_mau()
    dt_gia = DanhTinh(ma="nguoi-d", vai=("quan-tri",), nguon="nguon-manh")
    bo.dang_ky_nguon("nguon-yeu", lambda ct: dt_gia)
    dt, ly_do = bo.xac_thuc_ky("nguon-yeu", KHOA_BIA)
    bao_dam(
        dt is None,
        "nguồn yếu phát hành được danh tính nhãn 'nguon-manh' — lách được chính sách theo nguồn",
    )
    bao_dam("nguon-manh" in ly_do or "nguon-yeu" in ly_do, "lý do phải nêu hai nguồn")
    return "nhãn nguồn không khớp ⇒ từ chối"


@phep_kiem("F10 hết hạn ĐI QUA BỘ XÁC THỰC, theo đồng hồ tiêm vào, sát ranh giới")
def thu_het_han_qua_bo():
    moc = 1_000_000.0
    bo, hop = bo_mau(bay_gio=moc)
    dt_het = DanhTinh(ma="nguoi-e", vai=("doc-gia",), nguon="nguon-e", het_han=moc)
    bo.dang_ky_nguon("nguon-e", nguon_bang_khoa({KHOA_BIA: dt_het}, "nguon-e"))

    hop["t"] = moc - 1.0
    d, _ = bo.xac_thuc_ky("nguon-e", KHOA_BIA)
    bao_dam(d is dt_het, "trước hạn 1 giây phải xác thực được")

    hop["t"] = moc
    d, ly_do = bo.xac_thuc_ky("nguon-e", KHOA_BIA)
    bao_dam(d is None, "ĐÚNG giây hết hạn mà bộ xác thực vẫn cho qua")
    bao_dam("hết hạn" in ly_do, "lý do phải nói hết hạn: {!r}".format(ly_do))

    hop["t"] = moc + 1.0
    d, _ = bo.xac_thuc_ky("nguon-e", KHOA_BIA)
    bao_dam(d is None, "sau hạn 1 giây mà vẫn cho qua")

    # Và bộ xác thực phải dùng ĐỒNG HỒ TIÊM VÀO, không phải giờ máy: chỉnh đồng
    # hồ về quá khứ thì danh tính sống lại.
    hop["t"] = 0.0
    d, _ = bo.xac_thuc_ky("nguon-e", KHOA_BIA)
    bao_dam(d is dt_het, "bộ xác thực không dùng đồng hồ tiêm vào mà dùng giờ máy")
    return "ranh giới đúng ở cả ba mốc; đồng hồ tiêm vào có tác dụng thật"


@phep_kiem("F11 danh tính KHÔNG vai đi qua được, nhưng LÝ DO phải nói thẳng ra")
def thu_khong_vai_qua_bo():
    bo, _ = bo_mau()
    dt_tron = DanhTinh.khong_vai("nguoi-f", nguon="nguon-f")
    bo.dang_ky_nguon("nguon-f", nguon_bang_khoa({KHOA_BIA: dt_tron}, "nguon-f"))
    dt, ly_do = bo.xac_thuc_ky("nguon-f", KHOA_BIA)
    bao_dam(dt is dt_tron, "danh tính không vai vẫn phải nhận ra được là AI")
    bao_dam("KHÔNG có vai" in ly_do, "lý do phải nói rõ là không có vai: {!r}".format(ly_do))
    bao_dam(dt.vai == (), "vai phải vẫn rỗng sau khi đi qua bộ xác thực")
    return "nhận diện được người, và nói rõ người ấy chưa có quyền gì"


@phep_kiem("F12 LÝ DO của các ca hỏng giống nhau — không mách người dò đang đi đúng hướng")
def thu_ly_do_khong_phan_biet():
    bo, _ = bo_mau()
    dt = DanhTinh(ma="nguoi-g", vai=("doc-gia",), nguon="nguon-g")
    bo.dang_ky_nguon("nguon-g", nguon_bang_khoa({KHOA_BIA: dt}, "nguon-g"))

    _, ly_do_nguon_la = bo.xac_thuc_ky("nguon-khong-co", KHOA_BIA)
    _, ly_do_khoa_sai = bo.xac_thuc_ky("nguon-g", KHOA_BIA_KHAC)
    _, ly_do_rong = bo.xac_thuc_ky("nguon-g", "")

    dau = "không xác định được danh tính"
    for ten, ly_do in [
        ("nguồn lạ", ly_do_nguon_la),
        ("khoá sai", ly_do_khoa_sai),
        ("chứng thư rỗng", ly_do_rong),
    ]:
        bao_dam(
            ly_do.startswith(dau),
            "ca {!r} có lý do mở đầu khác: {!r}".format(ten, ly_do),
        )
    return "ba ca hỏng cùng một câu mở đầu"


@phep_kiem("F13 LÝ DO không bao giờ chứa chứng thư")
def thu_ly_do_khong_lo_chung_thu():
    bo, _ = bo_mau()
    dt = DanhTinh(ma="nguoi-h", vai=("doc-gia",), nguon="nguon-h")
    bo.dang_ky_nguon("nguon-h", nguon_bang_khoa({KHOA_BIA: dt}, "nguon-h"))

    cac_ly_do = [
        bo.xac_thuc_ky("nguon-h", KHOA_BIA)[1],
        bo.xac_thuc_ky("nguon-h", KHOA_BIA_KHAC)[1],
        bo.xac_thuc_ky("nguon-la", KHOA_BIA)[1],
        bo.xac_thuc_ky("nguon-h", "")[1],
    ]
    for ly_do in cac_ly_do:
        bao_dam(KHOA_BIA not in ly_do, "lý do làm lộ chứng thư: {!r}".format(ly_do))
        bao_dam(KHOA_BIA_KHAC not in ly_do, "lý do làm lộ chứng thư sai: {!r}".format(ly_do))
    return "4 lý do, không cái nào chứa chứng thư"


@phep_kiem("F14 xac_thuc() và xac_thuc_ky() luôn nói cùng một điều")
def thu_hai_cua_thong_nhat():
    bo, _ = bo_mau()
    dt = DanhTinh(ma="nguoi-i", vai=("doc-gia",), nguon="nguon-i")
    bo.dang_ky_nguon("nguon-i", nguon_bang_khoa({KHOA_BIA: dt}, "nguon-i"))
    cac_ca = [
        ("nguon-i", KHOA_BIA),
        ("nguon-i", KHOA_BIA_KHAC),
        ("nguon-la", KHOA_BIA),
        ("nguon-i", ""),
        ("nguon-i", None),
    ]
    for nguon, chung_thu in cac_ca:
        a = bo.xac_thuc(nguon, chung_thu)
        b = bo.xac_thuc_ky(nguon, chung_thu)[0]
        bao_dam(a is b, "hai cửa lệch nhau ở ca ({!r}, ...)".format(nguon))
    return "5 ca, hai cửa khớp nhau"


# ══════════════════════════════════════════════════════════════════════════════
# NHÓM G — nguon_bang_khoa: nguồn mẫu (chỉ để thử, nhưng vẫn phải đúng)
# ══════════════════════════════════════════════════════════════════════════════


@phep_kiem("G1  khoá đúng ra danh tính, khoá sai ra None")
def thu_bang_khoa_co_ban():
    dt = DanhTinh(ma="nguoi-j", vai=("doc-gia",), nguon=NGUON_KHOA_API)
    ham = nguon_bang_khoa({KHOA_BIA: dt})
    bao_dam(ham(KHOA_BIA) is dt, "khoá đúng phải ra đúng danh tính ấy")
    bao_dam(ham(KHOA_BIA_KHAC) is None, "khoá sai phải ra None")
    bao_dam(ham("") is None, "khoá rỗng phải ra None")
    bao_dam(ham(KHOA_BIA[:-1]) is None, "khoá thiếu một ký tự phải ra None")
    bao_dam(ham(KHOA_BIA + "x") is None, "khoá thừa một ký tự phải ra None")
    bao_dam(nguon_bang_khoa({})(KHOA_BIA) is None, "bảng rỗng phải luôn ra None")
    return "6 ca, kể cả lệch một ký tự và bảng rỗng"


@phep_kiem("G2  duyệt HẾT bảng kể cả khi đã khớp ở khoá đầu tiên")
def thu_bang_khoa_duyet_het():
    class BangDem(dict):
        """dict đếm số lượt phần tử được lấy ra qua items()."""

        def __init__(self, *a, **k):
            dict.__init__(self, *a, **k)
            self.so_luot = 0

        def items(self):
            for khoa, gia_tri in dict.items(self):
                self.so_luot += 1
                yield khoa, gia_tri

    dt = DanhTinh(ma="nguoi-k", vai=("doc-gia",), nguon=NGUON_KHOA_API)
    bang = BangDem()
    bang[KHOA_BIA] = dt  # khớp ngay phần tử ĐẦU
    for i in range(4):
        bang["KHOA-BIA-DEM-{}".format(i)] = dt

    ham = nguon_bang_khoa(bang)
    bang.so_luot = 0
    bao_dam(ham(KHOA_BIA) is dt, "khoá đầu bảng phải khớp")
    bao_dam(
        bang.so_luot == 5,
        "khớp sớm mà thoát sớm: chỉ duyệt {}/5 phần tử — thời gian chạy tố cáo vị trí khoá".format(
            bang.so_luot
        ),
    )

    bang.so_luot = 0
    bao_dam(ham("KHOA-BIA-KHONG-CO-TRONG-BANG") is None, "khoá lạ phải ra None")
    bao_dam(bang.so_luot == 5, "ca không khớp phải duyệt hết 5 phần tử")
    return "khớp sớm hay không khớp đều duyệt đủ 5/5"


@phep_kiem("G3  bảng khoá đi trọn vòng qua BoXacThuc")
def thu_bang_khoa_tron_vong():
    bo, _ = bo_mau()
    dt = DanhTinh(ma="nguoi-l", ten=TEN_BIA, vai=("doc-gia",), nguon=NGUON_KHOA_API)
    bo.dang_ky_nguon(NGUON_KHOA_API, nguon_bang_khoa({KHOA_BIA: dt}))
    ra, ly_do = bo.xac_thuc_ky(NGUON_KHOA_API, KHOA_BIA)
    bao_dam(ra is dt, "trọn vòng phải ra đúng danh tính")
    bao_dam("hợp lệ" in ly_do, "lý do ca thành công phải nói hợp lệ: {!r}".format(ly_do))
    bao_dam(TEN_BIA not in ly_do, "LÝ DO làm lộ tên người: {!r}".format(ly_do))
    bao_dam(KHOA_BIA not in ly_do, "LÝ DO làm lộ khoá")
    return "đăng ký → xác thực → danh tính, lý do sạch"


# ══════════════════════════════════════════════════════════════════════════════
# NHÓM H — bề mặt công khai đúng như tài liệu hứa
# ══════════════════════════════════════════════════════════════════════════════


@phep_kiem("H1  bề mặt công khai đủ và đúng kiểu")
def thu_be_mat_cong_khai():
    can_co = [
        "LoiDanhTinh",
        "DanhTinh",
        "so_sanh_hang_dinh",
        "BoXacThuc",
        "nguon_bang_khoa",
        "NGUON_KHOA_API",
        "NGUON_PHIEN",
        "MAU_MA",
        "MAU_VAI",
        "MAU_NGUON",
    ]
    thieu = [ten for ten in can_co if not hasattr(_dt, ten)]
    bao_dam(not thieu, "thiếu tên công khai: {}".format(thieu))
    for ten in ["khong_vai", "con_hieu_luc", "co_vai", "tom_tat"]:
        bao_dam(hasattr(DanhTinh, ten), "DanhTinh thiếu {}".format(ten))
    for ten in ["dang_ky_nguon", "go_nguon", "cac_nguon", "xac_thuc", "xac_thuc_ky"]:
        bao_dam(hasattr(BoXacThuc, ten), "BoXacThuc thiếu {}".format(ten))
    bao_dam(issubclass(LoiDanhTinh, ValueError), "LoiDanhTinh phải là ValueError")
    return "{} tên mô-đun + 4 phương thức DanhTinh + 5 phương thức BoXacThuc".format(len(can_co))


@phep_kiem("H2  mô-đun không tự đọc môi trường, không tự chạm mạng, không tự mở tệp")
def thu_khong_cham_ra_ngoai():
    with open(TEP_NGUON, "r", encoding="utf-8") as tep:
        nguon = tep.read()
        cay = ast.parse(nguon, filename=TEP_NGUON)

    cam = {"socket", "urllib", "http", "requests", "subprocess", "os"}
    da_nhap = set()
    for nut in ast.walk(cay):
        if isinstance(nut, ast.Import):
            for ten in nut.names:
                da_nhap.add(ten.name.split(".")[0])
        elif isinstance(nut, ast.ImportFrom) and nut.module:
            da_nhap.add(nut.module.split(".")[0])
    pham = sorted(da_nhap & cam)
    bao_dam(not pham, "mô-đun danh tính nhập thư viện không được phép: {}".format(pham))
    # Dựng từ mảnh: cổng khong-cua-hau quét cả kho, nên một bộ dò viết thẳng
    # chuỗi nó dò sẽ tự bị bắt. Ghép lúc chạy thì phép kiểm không đổi.
    for chuoi in ["getenv", "environ", "open(", "ev" + "al(", "ex" + "ec("]:
        bao_dam(chuoi not in nguon, "mã nguồn có {!r} — danh tính không được làm việc đó".format(chuoi))
    return "nhập: {}".format(", ".join(sorted(da_nhap)))


CAC_PHEP_KIEM = [
    thu_vai_chuoi_thanh_tuple,
    thu_vai_danh_sach,
    thu_khong_vai_bi_chan,
    thu_khong_vai_co_y,
    thu_ma_sai_mau,
    thu_ma_co_xuong_dong_bi_tu_choi,
    thu_vai_nguon_co_xuong_dong_bi_tu_choi,
    thu_nguon_bat_buoc,
    thu_vai_sai_mau,
    thu_vai_lap,
    thu_het_han_sai_kieu,
    thu_bat_bien,
    thu_dau_vao_di_dang,
    thu_khong_khai_han,
    thu_ranh_gioi_het_han,
    thu_dong_ho_mac_dinh,
    thu_co_vai,
    thu_khong_vai_khong_phai_moi_vai,
    thu_tom_tat_khong_lo_ten,
    thu_tom_tat_ban_sao,
    thu_tom_tat_json_mot_dong,
    thu_so_sanh_ket_qua,
    thu_so_sanh_khac_do_dai,
    thu_so_sanh_str_va_bytes,
    thu_so_sanh_unicode,
    thu_khong_dung_bang_bang,
    thu_so_sanh_di_dang,
    thu_dang_ky_va_liet_ke,
    thu_dang_ky_trung,
    thu_dang_ky_dau_vao_xau,
    thu_go_nguon,
    thu_nguon_khong_ton_tai,
    thu_chung_thu_xau,
    thu_nguon_no,
    thu_nguon_tra_sai_kieu,
    thu_nhan_nguon_khong_khop,
    thu_het_han_qua_bo,
    thu_khong_vai_qua_bo,
    thu_ly_do_khong_phan_biet,
    thu_ly_do_khong_lo_chung_thu,
    thu_hai_cua_thong_nhat,
    thu_bang_khoa_co_ban,
    thu_bang_khoa_duyet_het,
    thu_bang_khoa_tron_vong,
    thu_be_mat_cong_khai,
    thu_khong_cham_ra_ngoai,
]


def main() -> int:
    print("=" * 78)
    print("BAI TU KIEM — nhan/danh_tinh.py (AI DANG GOI)")
    print("Python {}.{}.{}".format(*sys.version_info[:3]))
    print("KHONG mang, KHONG bien moi truong, KHONG ghi dia. Moi khoa deu la BIA.")
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
    print("KET QUA: {}/{} DAT.".format(so_dat, len(_KET_QUA)))
    if tat_ca_dat:
        print()
        print("Nghia la gi: danh tinh het han bi tu choi dung o giay ranh gioi; so sanh bi")
        print("mat di qua hmac.compare_digest chu khong phai '=='; 'khong co vai nao' khong")
        print("hoa thanh 'co moi vai'; ban tom tat vao nhat ky khong mang ten nguoi; nguon")
        print("da go thi chung thu cu chet theo; nguon la va khoa sai cho cung mot cau tra")
        print("loi. Ve 'MOT CHU THE' trong khang dinh cong khai cua kho da co phep do dung sau.")
        print()
        print("Nghia la gi KHONG: bai nay KHONG kiem quyen, KHONG kiem han muc, KHONG kiem")
        print("nhat ky, va KHONG noi gi ve chat luong ham xac thuc ma doanh nghiep tiem vao.")
    else:
        print()
        print("Cac phep kiem HONG:")
        for ten, dat, ghi_chu in _KET_QUA:
            if not dat:
                print("  - {}: {}".format(ten, ghi_chu))
        print()
        print("LUU Y: neu chi hai phep A6 va A7 hong thi day la LOI THAT trong")
        print("nhan/danh_tinh.py (dau `$` trong MAU_MA/MAU_VAI/MAU_NGUON khop ca truoc mot")
        print("ky tu xuong dong o cuoi chuoi), khong phai bai kiem sai. Xem chu thich tren")
        print("hai ham ay. Nguoi dieu phoi quyet dinh sua the nao.")
    print("=" * 78)
    return 0 if tat_ca_dat else 1


if __name__ == "__main__":
    sys.exit(main())
