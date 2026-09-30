#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hop_dong.py — hop dong ma MOI trinh dieu khien cua Open BDSG phai theo.

=============================================================================
TEP NAY SINH RA DE GIAI QUYET CAI GI
=============================================================================
Do ngay 26/09/2026: he sinh thai BDSG co MUOI TAM nen tang dang song (do bang
HTTP that cung ngay). Da co MOT may chu MCP chay that, phuc vu CDP + metadata:
221 dong, 7 cong cu, noi JSON-RPC qua stdio. Ba gioi han cua no da do duoc, va
ca ba deu la ly do tep nay ton tai:

  (a) VAN CHUYEN LA SSH VAO MAY CHU SAN PHAM, khoa root ghi cung trong ma.
      Moi cong cu vi the la mot lenh tuy y tren he dang chay. Do khong phai
      trinh dieu khien; do la mot cua hau co giao dien dep.
  (b) BAY CONG CU, MOT LINH VUC, MOT TEP PHANG. Them mot nen tang thi phai sua
      chinh tep do. 18 nen tang se thanh 18 lan sua mot tep, hoac 18 tep chep
      qua chep lai.
  (c) KHONG CO LOP QUYEN, KHONG CO NHAT KY. Grep "quyen|auth|nhat_ky" tren tep
      do tra ve rong. Cau hoi "ai da lam gi" khong tra loi duoc.

Tep nay la CAI NHAN cua ba van de tren: mot hop dong hep, co the kiem bang may,
de moi nen tang duoc noi vao he theo cung MOT cach.

=============================================================================
BON QUYET DINH KIEN TRUC MA TEP NAY VIET THEO
=============================================================================
1. MCP LA RANH GIOI LOI GOI HE THONG.
   Khong phai REST, khong phai mot API cam trinh cam. MCP la thu mo hinh DA noi
   san, nen lay no lam ranh gioi thi moi client biet MCP deu la mot cai vo hop
   le. Mot cong cu MCP dong vai dung nhu mot loi goi he thong: co chu ky (khai
   bao tham so), co quyen, co the ghi nhat ky.

2. NHAN SO HUU DANH TINH, QUYEN, HAN MUC, NHAT KY. TRINH DIEU KHIEN THI KHONG.
   Day la luat quan trong nhat trong tep nay. Neu moi trinh dieu khien tu lam
   xac thuc thi 18 nen tang cho ra 18 mo hinh quyen khac nhau, va khong ai tra
   loi duoc "ai da lam gi". Trinh dieu khien biet dung MOT viec: doi mot loi goi
   cong cu thanh mot loi goi API cua nen tang no phu trach, roi tra ket qua ve.

3. MAC DINH CHI DOC. Cong cu co GHI phai khai TUONG MINH.
   Mot he dieu hanh cho moi tien trinh ghi vao moi thiet bi theo mac dinh thi
   khong phai he dieu hanh, do la mot trach nhiem phap ly. O tep nay luat ay
   hien ra o HAI cho, va hai cho ay khac nhau:
     - `KhaiBaoCongCu.ghi` mac dinh False  -> mot cong cu QUEN khai thi duoc coi
       la chi doc. Neu no thuc su ghi, do la loi cua NGUOI VIET trinh dieu
       khien, khong phai mot mac dinh nguy hiem cua he.
     - `TrinhDieuKhien(chi_doc=True)` mac dinh True -> mot trinh dieu khien
       duoc "gan" vao he o che do chi doc, y nhu mount mot he tep read-only.
       Muon ghi thi nguoi gan phai noi ra. Day KHONG phai phan quyen (trinh dieu
       khien khong biet ai goi); day la mot NANG LUC bi tat tu luc gan.

4. MO HINH CUC BO LA MAC DINH, BEN THU BA PHAI KHAI TUONG MINH.
   Quyet dinh nay khong cham vao tep nay nhieu, nhung no giai thich vi sao
   `http_chung.py` khong co gia tri mac dinh nao chua dia chi that: khong co
   duong lui im lang thi cung khong co dia chi doan mo.

=============================================================================
TEP NAY CO Y KHONG LAM GI
=============================================================================
  - KHONG xac thuc, KHONG kiem quyen theo nguoi dung, KHONG dem han muc,
    KHONG ghi nhat ky. Bon thu do thuoc ve NHAN (quyet dinh 2).
  - KHONG mo ket noi mang, KHONG doc tep cau hinh, KHONG doc bien moi truong.
  - KHONG phu thuoc thu vien ngoai. Chay duoc bang Python chuan.
  Muc tieu: tep nay nap duoc trong bat ky moi truong nao, ke ca luc chi muon
  kiem mot khai bao co hop le hay khong.

=============================================================================
PHU THUOC — DOC TRUOC KHI SUA
=============================================================================
NHAN CHUA TON TAI luc tep nay duoc viet (26/09/2026); mot nhom khac dang viet.
Gia dinh da thong nhat:
  - nhan co `nhan.dinh_tuyen.dang_ky(ten, td)`
  - moi trinh dieu khien khai `CONG_CU` + ham `goi(ten, tham_so)`
Vi nhan chua co, ham `dang_ky()` duoi day NHAN `nhan` LAM THAM SO thay vi
`import nhan`. Do la co y: tep nay phai chay duoc HOM NAY, va bai tu kiem phai
chay duoc ma khong can nhan. Khi nhan co that, doi mot dong o cho goi, khong
phai sua tep nay.

CHAY:
    .venv/bin/python trinh-dieu-khien/hop_dong.py      # in tom tat hop dong
    .venv/bin/python trinh-dieu-khien/thu_trinh_dieu_khien.py   # bai tu kiem
"""

from __future__ import annotations

import re
import sys

# =============================================================================
# HANG SO
# =============================================================================

# Mac dinh cua truong `ghi`. Viet thanh hang so co ten de khong ai doi no bang
# mot cu go nham ma khong thay trong ban khac biet.
MAC_DINH_GHI = False

# Mac dinh cua co `chi_doc` luc gan trinh dieu khien vao he (quyet dinh 3).
MAC_DINH_CHI_DOC = True

# Tran mac dinh cho tham so kieu chuoi va danh sach.
# VI SAO CO TRAN MAC DINH: mot tham so chuoi khong gioi han la mot lo thung ve
# bo nho va ve tien — noi dung do di thang vao mot loi goi API, va o phia con
# lai co the la mot mo hinh tinh tien theo token. Bat moi nguoi phai khai tran
# thi ho se quen; dat tran mac dinh roi cho ghi de thi khong ai quen duoc.
TOI_DA_KY_TU_MAC_DINH = 4096
TOI_DA_PHAN_TU_MAC_DINH = 256

# Cac kieu tham so duoc phep khai. Co y HEP.
# Danh sach nay khong phai JSON Schema day du, va do la chu y: JSON Schema day
# du thi khong kiem duoc bang mat, con cai gi khong kiem duoc bang mat thi som
# muon co nguoi khai mot luoc do nhan moi thu. `luoc_do_mcp()` ben duoi dich
# sang JSON Schema that cho MCP, nen phia ngoai van dung chuan.
KIEU_HOP_LE = {
    "chuoi": "string",
    "so_nguyen": "integer",
    "so_thuc": "number",
    "luan_ly": "boolean",
    "danh_sach": "array",
    "doi_tuong": "object",
}

# Cac khoa duoc phep trong mot khai bao tham so. Khoa la KHONG duoc bo qua im
# lang: go nham `bat_buot` thay vi `bat_buoc` se bien mot tham so bat buoc
# thanh tuy chon, va khong co gi bao. Day dung la ho loi "hong ma khong bao".
KHOA_THAM_SO_HOP_LE = {
    "kieu", "mo_ta", "bat_buoc", "mac_dinh",
    "toi_da_ky_tu", "toi_da_phan_tu", "gia_tri_cho_phep",
}

# Ten trinh dieu khien: chu thuong khong dau, so, gach ngang.
MAU_TEN_TRINH_DIEU_KHIEN = re.compile(r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$")

# Ten cong cu: chu thuong khong dau, so, gach duoi, gach ngang. Toi da 64.
# VI SAO HEP DEN THE: mot cai ten nay se di qua ba cho khac nhau — danh sach
# cong cu MCP, chu ky ham cua mot API kieu OpenAI (llm.bdsg.vn la API tuong
# thich OpenAI), va mot dong nhat ky ma nguoi phai doc duoc. Tap ky tu hep nhat
# trong ba cho ay la [a-zA-Z0-9_-] va do dai 64. Chon truoc tap hep nhat thi
# khong phai doi ten ve sau; doi ten mot cong cu la doi luon moi luat quyen da
# viet theo ten do.
MAU_TEN_CONG_CU = re.compile(r"^[a-z][a-z0-9_-]{0,62}[a-z0-9]$")
DAI_TOI_DA_TEN_CONG_CU = 64

# Dau noi giua ten trinh dieu khien va ten viec.
# VI SAO BAT BUOC TIEN TO: ten cong cu la KHONG GIAN TEN TOAN CUC o phia nhan —
# mo hinh chi thay mot danh sach phang. Neu moi trinh dieu khien tu dat ten tuy
# y thi hai nen tang deu co "tim_kiem" va nhan phai tu them tien to; luc do ten
# trong khai bao KHAC ten trong nhat ky KHAC ten trong luat quyen. Ba cai ten
# cho mot thu la ba co hoi lech nhau. Bat tien to ngay tu khai bao thi chi con
# MOT cai ten, tu dau den cuoi.
# Dung "__" chu khong dung "." vi dau cham khong nam trong tap ky tu hep nhat
# noi o tren.
DAU_NOI = "__"


# =============================================================================
# CAC LOAI LOI
# =============================================================================
# Bon lop loi, va ranh gioi giua chung la "AI sai":
#   LoiHopDong      — NGUOI VIET trinh dieu khien sai. Nem luc dang ky, truoc
#                     khi he chay. Khong bao gio den tay nguoi dung.
#   LoiThamSo       — NGUOI GOI (hoac mo hinh) dua tham so sai. Nhan nen tra ve
#                     nhu mot loi co the sua duoc.
#   LoiChuaCauHinh  — NGUOI VAN HANH chua khai bien moi truong. Khong phai loi
#                     cua ai dang goi, va TUYET DOI khong duoc doan bua cho qua.
#   LoiCongCu       — loi luc thuc thi (nen tang tu choi, mang hong, bi chan...).


class LoiHopDong(Exception):
    """Khai bao cua mot trinh dieu khien khong hop le.

    Nem luc dang ky, KHONG nem luc chay. Mot khai bao sai ma lot duoc vao he thi
    no chi no ra dung luc co nguoi goi — nghia la luc te nhat.
    """


class LoiCongCu(Exception):
    """Loi luc thuc thi mot cong cu.

    `ma` la ma may doc duoc; nhan dung no de ghi nhat ky va de quyet dinh co thu
    lai hay khong. Thong diep tieng Viet danh cho nguoi.
    """

    ma = "loi_cong_cu"

    def __init__(self, thong_diep, ma=None):
        super().__init__(thong_diep)
        if ma is not None:
            self.ma = ma


class LoiKhongCoCongCu(LoiCongCu):
    ma = "khong_co_cong_cu"


class LoiThamSo(LoiCongCu):
    ma = "tham_so_sai"


class LoiChuaCauHinh(LoiCongCu):
    """Thieu cau hinh (thuong la bien moi truong).

    CO Y la mot loai rieng: phan biet "chua cau hinh" voi "goi that bai" la
    phan biet giua mot viec nguoi van hanh phai lam va mot su co. Gop chung lai
    thi canh bao se keu nhu nhau va khong ai biet phai sua o dau.
    """

    ma = "chua_cau_hinh"


class LoiChiDoc(LoiCongCu):
    """Cong cu co GHI bi goi tren mot trinh dieu khien dang gan che do chi doc."""

    ma = "chi_doc"


class LoiBiChan(LoiCongCu):
    """Dia chi dich bi chan (xem http_chung.py)."""

    ma = "dia_chi_bi_chan"


# =============================================================================
# KHAI BAO MOT CONG CU
# =============================================================================


class KhaiBaoCongCu(object):
    """Mot dong trong danh sach cong cu ma trinh dieu khien cong bo.

    Bon truong, khong hon:
      ten      — ten day du, PHAI bat dau bang "<ten trinh dieu khien>__"
      mo_ta    — mot cau cho NGUOI va cho MO HINH doc. Khong duoc rong.
      tham_so  — luoc do tham so (xem KHOA_THAM_SO_HOP_LE)
      ghi      — cong cu nay co LAM THAY DOI trang thai o nen tang khong?
                 Mac dinh False (quyet dinh 3).

    CO Y KHONG CO: truong quyen, truong vai tro, truong han muc, truong "nguy
    hiem". Bon thu do thuoc ve nhan. Neu de o day, moi trinh dieu khien se dat
    ra mot thang bac quyen rieng va he lai co 18 mo hinh quyen — dung cai da
    hong ma hop dong nay sinh ra de sua.
    """

    __slots__ = ("ten", "mo_ta", "tham_so", "ghi")

    def __init__(self, ten, mo_ta, tham_so=None, ghi=MAC_DINH_GHI):
        self.ten = ten
        self.mo_ta = mo_ta
        self.tham_so = {} if tham_so is None else tham_so
        self.ghi = ghi

    def __repr__(self):
        return "<KhaiBaoCongCu {} ghi={}>".format(self.ten, self.ghi)

    # -- kiem chinh minh ---------------------------------------------------
    def kiem(self, tien_to=None):
        """Nem LoiHopDong neu khai bao nay sai. Tra ve None neu dat.

        `tien_to` la ten trinh dieu khien; neu co thi kiem luon tien to ten.
        """
        if not isinstance(self.ten, str) or not self.ten:
            raise LoiHopDong("cong cu thieu ten (hoac ten khong phai chuoi)")
        if len(self.ten) > DAI_TOI_DA_TEN_CONG_CU:
            raise LoiHopDong(
                "ten cong cu '{}' dai {} ky tu, vuot tran {}".format(
                    self.ten, len(self.ten), DAI_TOI_DA_TEN_CONG_CU))
        if not MAU_TEN_CONG_CU.match(self.ten):
            raise LoiHopDong(
                "ten cong cu '{}' khong hop le: chi cho chu thuong khong dau, so, "
                "'_' va '-'; phai bat dau bang chu va ket thuc bang chu hoac so. "
                "Xem MAU_TEN_CONG_CU de biet vi sao tap ky tu hep den the.".format(self.ten))
        if tien_to is not None:
            can_co = tien_to + DAU_NOI
            if not self.ten.startswith(can_co):
                raise LoiHopDong(
                    "ten cong cu '{}' phai bat dau bang '{}'. Ten cong cu la khong gian "
                    "ten TOAN CUC o phia nhan; khong co tien to thi hai nen tang se dung "
                    "chung mot ten va nhan phai tu doi ten — luc do ten trong khai bao, "
                    "ten trong nhat ky va ten trong luat quyen khong con la mot."
                    .format(self.ten, can_co))
            if len(self.ten) == len(can_co):
                raise LoiHopDong(
                    "ten cong cu '{}' chi co tien to, khong co phan viec".format(self.ten))

        if not isinstance(self.mo_ta, str) or not self.mo_ta.strip():
            raise LoiHopDong(
                "cong cu '{}' thieu mo ta. Mo ta khong phai trang tri: mo hinh chon cong "
                "cu bang chinh cau nay, va nguoi doc nhat ky cung doc chinh cau nay."
                .format(self.ten))

        if not isinstance(self.ghi, bool):
            raise LoiHopDong(
                "cong cu '{}' khai ghi={!r} khong phai kieu bool. Trong Python chuoi "
                "'false' la GIA TRI DUNG — nhan ca chuoi thi mot cong cu ghi co the tu "
                "xung la chi doc chi vi go nham kieu du lieu.".format(self.ten, self.ghi))

        if not isinstance(self.tham_so, dict):
            raise LoiHopDong(
                "cong cu '{}' khai tham_so khong phai tu dien".format(self.ten))

        for ten_ts, khai in self.tham_so.items():
            self._kiem_mot_tham_so(ten_ts, khai)

    def _kiem_mot_tham_so(self, ten_ts, khai):
        cho = "cong cu '{}', tham so '{}'".format(self.ten, ten_ts)
        if not isinstance(ten_ts, str) or not re.match(r"^[a-z][a-z0-9_]{0,39}$", ten_ts):
            raise LoiHopDong(
                "{}: ten tham so khong hop le (chu thuong khong dau, so, gach duoi, "
                "bat dau bang chu, toi da 40)".format(cho))
        if not isinstance(khai, dict):
            raise LoiHopDong("{}: khai bao phai la tu dien".format(cho))

        la = set(khai) - KHOA_THAM_SO_HOP_LE
        if la:
            raise LoiHopDong(
                "{}: khoa la {}. Khoa la bi tu choi chu khong bi bo qua — go nham "
                "'bat_buot' thay vi 'bat_buoc' se bien mot tham so bat buoc thanh tuy "
                "chon ma khong co gi bao.".format(cho, sorted(la)))

        kieu = khai.get("kieu")
        if kieu not in KIEU_HOP_LE:
            raise LoiHopDong(
                "{}: kieu {!r} khong hop le. Cac kieu duoc phep: {}".format(
                    cho, kieu, ", ".join(sorted(KIEU_HOP_LE))))

        mo_ta = khai.get("mo_ta")
        if not isinstance(mo_ta, str) or not mo_ta.strip():
            raise LoiHopDong("{}: thieu mo ta".format(cho))

        bat_buoc = khai.get("bat_buoc", False)
        if not isinstance(bat_buoc, bool):
            raise LoiHopDong("{}: bat_buoc phai la bool".format(cho))

        if "mac_dinh" in khai:
            if bat_buoc:
                raise LoiHopDong(
                    "{}: vua bat_buoc vua co mac_dinh — hai dieu nay mau thuan, va cai "
                    "nao thang thi tuy nguoi doc ma doan.".format(cho))
            hop, vi_sao = _hop_kieu(khai["mac_dinh"], kieu)
            if not hop:
                raise LoiHopDong("{}: gia tri mac_dinh {}".format(cho, vi_sao))

        for khoa_tran, kieu_can in (("toi_da_ky_tu", "chuoi"), ("toi_da_phan_tu", "danh_sach")):
            if khoa_tran in khai:
                if kieu != kieu_can:
                    raise LoiHopDong(
                        "{}: '{}' chi co nghia voi kieu '{}'".format(cho, khoa_tran, kieu_can))
                gt = khai[khoa_tran]
                if not isinstance(gt, int) or isinstance(gt, bool) or gt <= 0:
                    raise LoiHopDong("{}: '{}' phai la so nguyen duong".format(cho, khoa_tran))

        if "gia_tri_cho_phep" in khai:
            ds = khai["gia_tri_cho_phep"]
            if not isinstance(ds, (list, tuple)) or not ds:
                raise LoiHopDong("{}: gia_tri_cho_phep phai la danh sach khong rong".format(cho))
            for gt in ds:
                hop, vi_sao = _hop_kieu(gt, kieu)
                if not hop:
                    raise LoiHopDong(
                        "{}: gia tri cho phep {!r} {}".format(cho, gt, vi_sao))

    # -- doi sang JSON Schema cho MCP --------------------------------------
    def luoc_do_mcp(self):
        """Tra ve `inputSchema` kieu JSON Schema de nhan dua vao danh sach MCP.

        `additionalProperties: False` la co y, va no PHAI khop voi cach
        `kiem_tham_so()` tu choi khoa la. Neu luoc do noi "them gi cung duoc" ma
        ham kiem lai tu choi, thi mo hinh se hoc mot dang goi ma he khong nhan —
        va loi ay hien ra o phia nguoi dung chu khong phai o day.
        """
        thuoc_tinh = {}
        bat_buoc = []
        for ten_ts, khai in self.tham_so.items():
            muc = {"type": KIEU_HOP_LE[khai["kieu"]], "description": khai["mo_ta"]}
            if "gia_tri_cho_phep" in khai:
                muc["enum"] = list(khai["gia_tri_cho_phep"])
            if khai["kieu"] == "chuoi":
                muc["maxLength"] = khai.get("toi_da_ky_tu", TOI_DA_KY_TU_MAC_DINH)
            if khai["kieu"] == "danh_sach":
                muc["maxItems"] = khai.get("toi_da_phan_tu", TOI_DA_PHAN_TU_MAC_DINH)
            if "mac_dinh" in khai:
                muc["default"] = khai["mac_dinh"]
            thuoc_tinh[ten_ts] = muc
            if khai.get("bat_buoc", False):
                bat_buoc.append(ten_ts)
        luoc_do = {
            "type": "object",
            "properties": thuoc_tinh,
            "additionalProperties": False,
        }
        if bat_buoc:
            luoc_do["required"] = sorted(bat_buoc)
        return luoc_do


def _hop_kieu(gia_tri, kieu):
    """Tra (hop_le, giai_thich_neu_khong). Dung chung cho khai bao va cho loi goi.

    BAY NGON NGU, ghi ra day vi no da cai vao nhieu du an that: trong Python
    `isinstance(True, int)` la True — bool la mot lop con cua int. Neu khong loai
    bool ra thi `ghi=True` lot qua duoc mot tham so khai kieu so nguyen, va no se
    di tiep vao mot loi goi API duoi dang so 1.
    """
    if kieu == "luan_ly":
        if isinstance(gia_tri, bool):
            return True, ""
        return False, "phai la luan ly (True/False), nhan duoc {}".format(type(gia_tri).__name__)
    if kieu == "so_nguyen":
        if isinstance(gia_tri, int) and not isinstance(gia_tri, bool):
            return True, ""
        return False, "phai la so nguyen, nhan duoc {}".format(type(gia_tri).__name__)
    if kieu == "so_thuc":
        if isinstance(gia_tri, (int, float)) and not isinstance(gia_tri, bool):
            return True, ""
        return False, "phai la so, nhan duoc {}".format(type(gia_tri).__name__)
    if kieu == "chuoi":
        if isinstance(gia_tri, str):
            return True, ""
        return False, "phai la chuoi, nhan duoc {}".format(type(gia_tri).__name__)
    if kieu == "danh_sach":
        if isinstance(gia_tri, list):
            return True, ""
        return False, "phai la danh sach, nhan duoc {}".format(type(gia_tri).__name__)
    if kieu == "doi_tuong":
        if isinstance(gia_tri, dict):
            return True, ""
        return False, "phai la tu dien, nhan duoc {}".format(type(gia_tri).__name__)
    return False, "kieu khai bao {!r} khong hop le".format(kieu)


# =============================================================================
# KIEM THAM SO CUA MOT LOI GOI
# =============================================================================


def kiem_tham_so(khai, tham_so):
    """Kiem tham so mot loi goi theo khai bao. Tra ve tu dien MOI da dien mac dinh.

    Nem LoiThamSo neu sai. KHONG sua chua am tham, KHONG ep kieu: nhan chuoi "3"
    cho mot tham so so nguyen roi tu doi thanh 3 la day mot doan doan mo vao giua
    he, va doan mo thi khong ghi nhat ky duoc.

    Ham nay o hop dong chu khong o nhan, vi no la HAM THUAN TUY cua khai bao:
    khong biet ai goi, khong doc gi ben ngoai. Nhan van la noi GOI no.
    """
    if not isinstance(tham_so, dict):
        raise LoiThamSo("tham so phai la tu dien, nhan duoc {}".format(type(tham_so).__name__))

    la = set(tham_so) - set(khai.tham_so)
    if la:
        raise LoiThamSo(
            "cong cu '{}' khong nhan tham so {}. Tham so la bi TU CHOI chu khong bi bo "
            "qua: mot ten go nham bi bo qua se chay 'thanh cong' voi y nghia khac han y "
            "nguoi goi muon.".format(khai.ten, sorted(la)))

    ket_qua = {}
    for ten_ts, mo_ta_ts in khai.tham_so.items():
        kieu = mo_ta_ts["kieu"]
        if ten_ts not in tham_so:
            if mo_ta_ts.get("bat_buoc", False):
                raise LoiThamSo(
                    "cong cu '{}' thieu tham so bat buoc '{}' ({})".format(
                        khai.ten, ten_ts, mo_ta_ts["mo_ta"]))
            if "mac_dinh" in mo_ta_ts:
                ket_qua[ten_ts] = mo_ta_ts["mac_dinh"]
            continue

        gt = tham_so[ten_ts]
        hop, vi_sao = _hop_kieu(gt, kieu)
        if not hop:
            raise LoiThamSo("cong cu '{}', tham so '{}' {}".format(khai.ten, ten_ts, vi_sao))

        if kieu == "chuoi":
            tran = mo_ta_ts.get("toi_da_ky_tu", TOI_DA_KY_TU_MAC_DINH)
            if len(gt) > tran:
                raise LoiThamSo(
                    "cong cu '{}', tham so '{}' dai {} ky tu, vuot tran {}".format(
                        khai.ten, ten_ts, len(gt), tran))
        if kieu == "danh_sach":
            tran = mo_ta_ts.get("toi_da_phan_tu", TOI_DA_PHAN_TU_MAC_DINH)
            if len(gt) > tran:
                raise LoiThamSo(
                    "cong cu '{}', tham so '{}' co {} phan tu, vuot tran {}".format(
                        khai.ten, ten_ts, len(gt), tran))
        if "gia_tri_cho_phep" in mo_ta_ts and gt not in mo_ta_ts["gia_tri_cho_phep"]:
            raise LoiThamSo(
                "cong cu '{}', tham so '{}' = {!r} khong nam trong danh sach cho phep {}"
                .format(khai.ten, ten_ts, gt, list(mo_ta_ts["gia_tri_cho_phep"])))

        ket_qua[ten_ts] = gt

    return ket_qua


# =============================================================================
# LOP CO SO
# =============================================================================


class TrinhDieuKhien(object):
    """Lop co so cua moi trinh dieu khien.

    Lop con PHAI khai:
        ten      — chuoi, khop MAU_TEN_TRINH_DIEU_KHIEN
        CONG_CU  — danh sach KhaiBaoCongCu, khong rong
        goi(ten, tham_so) — thuc thi mot cong cu, tra ve du lieu (thuong la dict)

    Lop con KHONG DUOC lam ba viec (quyet dinh 2):
        1. tu xac thuc       2. tu ghi nhat ky       3. tu quyet dinh quyen
    Ly do va cach lam dung: xem README.md trong cung thu muc.

    `chi_doc` mac dinh True. Do la NANG LUC luc gan, khong phai phan quyen: trinh
    dieu khien khong biet ai dang goi va khong duoc phep biet.
    """

    ten = ""
    CONG_CU = ()

    def __init__(self, chi_doc=MAC_DINH_CHI_DOC):
        if not isinstance(chi_doc, bool):
            raise LoiHopDong(
                "chi_doc phai la bool, nhan duoc {!r}. Chuoi 'false' la gia tri DUNG "
                "trong Python — nhan ca chuoi thi mot lan go nham mo toang duong ghi."
                .format(chi_doc))
        self.chi_doc = chi_doc
        # Tra cuu O(1) theo ten, dung sau khi hop dong da duyet.
        self._theo_ten = {}
        for khai in self.CONG_CU:
            if isinstance(khai, KhaiBaoCongCu):
                self._theo_ten[khai.ten] = khai

    # -- tra cuu ------------------------------------------------------------
    def cong_cu(self, ten):
        """Tra ve KhaiBaoCongCu, nem LoiKhongCoCongCu neu khong co."""
        khai = self._theo_ten.get(ten)
        if khai is None:
            raise LoiKhongCoCongCu(
                "trinh dieu khien '{}' khong co cong cu '{}'. Cac cong cu co: {}".format(
                    self.ten, ten, ", ".join(sorted(self._theo_ten)) or "(khong co)"))
        return khai

    def la_ghi(self, ten):
        """Cong cu nay co ghi khong? Cong cu quen khai `ghi` -> False (chi doc)."""
        return self.cong_cu(ten).ghi

    def cong_cu_ghi(self):
        return sorted(k.ten for k in self.CONG_CU
                      if isinstance(k, KhaiBaoCongCu) and k.ghi)

    # -- cua vao chuan cho lop con -----------------------------------------
    def bat_dau_goi(self, ten, tham_so):
        """Ba viec mo dau ma MOI cong cu deu phai lam, gom vao mot cho.

        1. cong cu co ton tai khong               -> LoiKhongCoCongCu
        2. cong cu ghi tren ban gan chi doc       -> LoiChiDoc
        3. tham so co hop khai bao khong          -> LoiThamSo
        Tra ve tu dien tham so DA CHUAN HOA (da dien mac dinh).

        DAY KHONG PHAI XAC THUC. Ham nay khong biet ai goi, va co y khong biet.
        No chi tra loi duoc cau "loi goi nay co hop khai bao khong" va cau "ban
        gan nay co duoc phep ghi khong".

        Gom vao mot cho vi neu de moi trinh dieu khien tu lam ba buoc nay thi som
        muon co mot trinh dieu khien quen buoc 2 — va cai quen ay im lang.
        """
        khai = self.cong_cu(ten)
        if khai.ghi and self.chi_doc:
            raise LoiChiDoc(
                "cong cu '{}' co GHI, nhung trinh dieu khien '{}' dang duoc gan o che do "
                "chi doc. Muon ghi thi phia gan phai khai tuong minh chi_doc=False."
                .format(ten, self.ten))
        return kiem_tham_so(khai, tham_so)

    # -- lop con phai viet de ----------------------------------------------
    def goi(self, ten, tham_so):
        raise NotImplementedError(
            "trinh dieu khien '{}' chua viet de ham goi()".format(self.ten or type(self).__name__))

    # -- tien ich -----------------------------------------------------------
    def danh_sach_mcp(self):
        """Danh sach cong cu duoi dang nhan dua thang ra MCP.

        Co them truong `ghi` ngoai chuan MCP: nhan can biet cong cu nao la ghi de
        dinh tuyen qua cong ghi rieng (quyet dinh 3). Client khong hieu truong nay
        se bo qua no, khong hong gi.
        """
        return [
            {"name": k.ten, "description": k.mo_ta,
             "inputSchema": k.luoc_do_mcp(), "ghi": k.ghi}
            for k in self.CONG_CU
        ]

    def __repr__(self):
        return "<{} ten={} cong_cu={} chi_doc={}>".format(
            type(self).__name__, self.ten, len(self.CONG_CU), getattr(self, "chi_doc", "?"))


# =============================================================================
# KIEM HOP DONG
# =============================================================================


def kiem_hop_dong(td):
    """Kiem mot trinh dieu khien truoc khi cho no vao he.

    Nem LoiHopDong voi thong diep RO RANG neu khai sai. KHONG bo qua, KHONG canh
    bao roi chay tiep: mot trinh dieu khien khai sai ma van duoc dang ky thi loi
    chi lo ra luc co nguoi goi that.

    Tra ve mot tu dien tom tat de nhan ghi nhat ky luc dang ky:
        {"ten", "so_cong_cu", "cong_cu_doc", "cong_cu_ghi"}
    """
    if not isinstance(td, TrinhDieuKhien):
        raise LoiHopDong(
            "doi tuong {!r} khong ke thua TrinhDieuKhien. Neu ban CHAC la co ke thua thi "
            "nhieu kha nang hop_dong.py da bi nap HAI LAN duoi hai ten khac nhau trong "
            "sys.modules — luc do co hai lop TrinhDieuKhien khac nhau va isinstance sai. "
            "Xem phan nap mo-dun o dau vi_du_bo_nho.py.".format(td))

    # -- 1. ten trinh dieu khien -------------------------------------------
    ten = getattr(td, "ten", None)
    if not isinstance(ten, str) or not ten:
        raise LoiHopDong(
            "trinh dieu khien thieu thuoc tinh 'ten'. Ten nay di vao moi dong nhat ky va "
            "moi luat quyen; khong co ten thi khong ghi duoc 'ai da lam gi'.")
    if not MAU_TEN_TRINH_DIEU_KHIEN.match(ten):
        raise LoiHopDong(
            "ten trinh dieu khien '{}' khong hop le: chi cho chu thuong khong dau, so va "
            "gach ngang; dai 3..32; bat dau bang chu.".format(ten))

    # -- 2. goi() phai duoc viet de ----------------------------------------
    # So HAM cua lop chu khong goi thu: goi thu la chay ma la len may nguoi dang
    # dang ky, va mot ham goi() that co the cham vao mang.
    if type(td).goi is TrinhDieuKhien.goi:
        raise LoiHopDong(
            "trinh dieu khien '{}' chua viet de ham goi(). Co khai bao cong cu ma khong "
            "co cach thuc thi la mot danh sach cong cu ma noi nao cung hong.".format(ten))

    # -- 3. danh sach cong cu ----------------------------------------------
    cong_cu = getattr(td, "CONG_CU", None)
    if not isinstance(cong_cu, (list, tuple)):
        raise LoiHopDong(
            "trinh dieu khien '{}': CONG_CU phai la danh sach hoac tuple, nhan duoc {}"
            .format(ten, type(cong_cu).__name__))
    if len(cong_cu) == 0:
        raise LoiHopDong(
            "trinh dieu khien '{}' khong khai cong cu nao. Mot trinh dieu khien khong cong "
            "cu thi khong lam gi duoc, nhung van chiem mot ten trong he va van hien ra "
            "trong danh sach — ro rang hon la dung dang ky no.".format(ten))

    # -- 4. tung khai bao ---------------------------------------------------
    da_thay = {}
    for chi_so, khai in enumerate(cong_cu):
        if not isinstance(khai, KhaiBaoCongCu):
            raise LoiHopDong(
                "trinh dieu khien '{}': phan tu thu {} trong CONG_CU khong phai "
                "KhaiBaoCongCu ma la {}. Neu dang dung tu dien tho, boc lai bang "
                "KhaiBaoCongCu(...) de no duoc kiem.".format(ten, chi_so, type(khai).__name__))
        khai.kiem(tien_to=ten)

        # Trung ten: so theo chu thuong. Hai cong cu chi khac nhau o hoa/thuong
        # la mot cai bay cho nguoi doc nhat ky, va mot so client MCP cung khong
        # phan biet. Chan o day thi khong phai nho nua.
        khoa = khai.ten.lower()
        if khoa in da_thay:
            raise LoiHopDong(
                "trinh dieu khien '{}': hai cong cu cung ten '{}' (vi tri {} va {}). "
                "Cai sau se am tham che cai truoc trong bang tra cuu."
                .format(ten, khai.ten, da_thay[khoa], chi_so))
        da_thay[khoa] = chi_so

    doc = sorted(k.ten for k in cong_cu if not k.ghi)
    ghi = sorted(k.ten for k in cong_cu if k.ghi)
    return {"ten": ten, "so_cong_cu": len(cong_cu), "cong_cu_doc": doc, "cong_cu_ghi": ghi}


# =============================================================================
# DANG KY VAO NHAN
# =============================================================================


def dang_ky(nhan, td):
    """Kiem hop dong roi dang ky td vao nhan. Tra ve tom tat cua kiem_hop_dong().

    VI SAO `nhan` LA THAM SO chu khong phai `import nhan`:
      Luc viet tep nay (26/09/2026) nhan CHUA TON TAI — mot nhom khac dang viet.
      Mot `import` cung se lam ca thu muc nay khong nap duoc, va bai tu kiem
      khong chay duoc. Nhan tham so thi hop dong phu thuoc vao HINH DANG cua
      nhan (`nhan.dinh_tuyen.dang_ky`) chu khong phu thuoc vao su ton tai cua no.

    VI SAO KIEM TRUOC KHI DANG KY:
      Sau khi dang ky thi loi chi lo ra luc co nguoi goi. Truoc khi dang ky thi
      loi lo ra luc khoi dong, cho nguoi dang sua ma nhin thay.
    """
    tom_tat = kiem_hop_dong(td)
    dinh_tuyen = getattr(nhan, "dinh_tuyen", None)
    if dinh_tuyen is None or not hasattr(dinh_tuyen, "dang_ky"):
        raise LoiHopDong(
            "nhan khong co 'dinh_tuyen.dang_ky(ten, td)'. Day la hinh dang da thong nhat "
            "voi nhom viet nhan; neu hinh dang doi thi sua o DAY, mot cho.")
    dinh_tuyen.dang_ky(td.ten, td)
    return tom_tat


# =============================================================================
# CHAY TRUC TIEP: in tom tat hop dong
# =============================================================================


def _in_tom_tat():
    print("=" * 78)
    print("HOP DONG TRINH DIEU KHIEN — Open BDSG")
    print("=" * 78)
    print()
    print("MOT TRINH DIEU KHIEN PHAI CO:")
    print("  ten      : khop {}".format(MAU_TEN_TRINH_DIEU_KHIEN.pattern))
    print("  CONG_CU  : danh sach KhaiBaoCongCu, khong rong, ten khong trung,")
    print("             moi ten bat dau bang '<ten>{}'".format(DAU_NOI))
    print("  goi()    : viet de, tra ve du lieu; that bai thi nem LoiCongCu")
    print()
    print("MOT TRINH DIEU KHIEN KHONG DUOC:")
    print("  1. tu xac thuc     2. tu ghi nhat ky     3. tu quyet dinh quyen")
    print("  Ba thu do thuoc ve NHAN. Xem README.md cung thu muc.")
    print()
    print("MAC DINH AN TOAN:")
    print("  KhaiBaoCongCu.ghi        mac dinh {}".format(MAC_DINH_GHI))
    print("  TrinhDieuKhien(chi_doc)  mac dinh {}".format(MAC_DINH_CHI_DOC))
    print("  tham so chuoi            tran mac dinh {} ky tu".format(TOI_DA_KY_TU_MAC_DINH))
    print("  tham so danh sach        tran mac dinh {} phan tu".format(TOI_DA_PHAN_TU_MAC_DINH))
    print()
    print("KIEU THAM SO HOP LE: {}".format(", ".join(sorted(KIEU_HOP_LE))))
    print()
    print("Kiem mot trinh dieu khien: kiem_hop_dong(td) — nem LoiHopDong neu khai sai.")
    print("Bai tu kiem: .venv/bin/python trinh-dieu-khien/thu_trinh_dieu_khien.py")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(_in_tom_tat())
