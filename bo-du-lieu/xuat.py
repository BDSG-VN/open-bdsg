#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xuat.py - Xuat bo du lieu mo "Open BDSG" tu CSDL ra JSONL.

Doc truoc khi chay: README.md (thẻ dữ liệu) va luoc-do.md (lược đồ JSONL) cung thu muc.

NGUYEN TAC THIET KE - hong-thi-dong (fail-closed)
------------------------------------------------
Ho loi nguy hiem nhat trong mot duong ong du lieu khong phai loi lam chuong trinh chet,
ma la loi lam chuong trinh chay tiep voi ket qua sai. Vi vay script nay:

  1. KHONG co gia tri mac dinh nao chua thong tin may chu. Thieu bien moi truong thi dung,
     chu khong lang le noi vao mot CSDL doan duoc.
  2. Co DANH SACH TRANG nguon. Gap mot `nguon` la trong bang -> DUNG TOAN BO, khong bo qua
     im lang. Mot nguon moi xuat hien la su kien can nguoi xem xet, khong phai truong hop
     can xu ly tu dong.
  3. Kiem ten cot bang information_schema TRUOC khi truy van. Neu lieu do khong khop, bao
     ra danh sach cot that thay vi de PostgreSQL nem mot loi khong lien quan.
  4. Quet du lieu ca nhan CHAY TRUOC KHI GHI, tren ban ghi da dung xong. Vuot nguong ->
     KHONG ghi tep nao ca, ke ca cac lop da sach.
  5. In bao cao so do cuoi cung de doi chieu voi thẻ dữ liệu.

Cach chay:

    export BDSG_DSN_CHAT='postgresql://NGUOI:MATKHAU@MAY:CONG/bdsg_chat'
    export BDSG_DSN_BUSINESS='postgresql://NGUOI:MATKHAU@MAY:CONG/postgres'
    export BDSG_THU_MUC_XUAT='./xuat'
    python3 bo-du-lieu/xuat.py

Bien moi truong tuy chon:
    BDSG_TEN_MIEN_NOI_BO   Danh sach ten mien noi bo, ngan bang dau phay. Dung de do "URL
                           noi bo". Khong dat thi chi do duoc URL tro vao IP rieng / cong
                           tuong minh / duoi .local .internal .lan (xem mo ta o ham
                           `do_url_noi_bo`).
    BDSG_CHAN_KHI_LECH=1   Bien "lech so do tham chieu" tu CANH BAO thanh DUNG HAN (ma
                           thoat 2). NOI RO: phep doi chieu nay chay SAU khi ghi tep, nen
                           no KHONG ngan tep duoc ghi - no chi bat nguoi chay phai xem lai
                           roi tu xoa. Lop chan that su TRUOC khi ghi la quet du lieu ca
                           nhan (muc 4) va hai lan kiem danh sach trang.
    BDSG_NGAY_DO           Ghi de ngay do vao truong `ngay_do` (mac dinh: ngay chay).

Giay phep bo du lieu xuat ra: CC-BY-4.0.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from datetime import date

# ---------------------------------------------------------------------------
# 0. Trinh dieu khien CSDL
# ---------------------------------------------------------------------------
# Chap nhan ca psycopg (v3) lan psycopg2. Khong ep nguoi chay phai cai dung mot ban,
# nhung cung khong im lang khi khong co ban nao: bao ro phai cai gi.
try:  # pragma: no cover - phu thuoc moi truong
    import psycopg as _pg  # type: ignore

    _TEN_TRINH_DIEU_KHIEN = "psycopg (v3)"
except ImportError:  # pragma: no cover
    try:
        import psycopg2 as _pg  # type: ignore

        _TEN_TRINH_DIEU_KHIEN = "psycopg2"
    except ImportError:  # pragma: no cover
        _pg = None
        _TEN_TRINH_DIEU_KHIEN = ""


# ---------------------------------------------------------------------------
# 1. SO DO THAM CHIEU - do ngay 25/09/2026
# ---------------------------------------------------------------------------
# Day la so da do that tren CSDL ngay 25/09/2026, chep vao day de script tu doi chieu.
# Muc dich KHONG phai de ep du lieu khop so nay (du lieu nguon thay doi theo thoi gian la
# binh thuong), ma de lech thi CO NGUOI BIET. Mot truy van bi hong thuong tra ve it hon
# chu khong tra ve loi - neu khong doi chieu thi hong ay hoan toan im lang.
NGAY_DO_THAM_CHIEU = "2026-09-25"

SO_DO_THAM_CHIEU = {
    # bdsg_chat.doan_tri_thuc, sau khi loai 2 nguon may sinh
    "ho-so-niem-yet": 5192,
    "ho-so-dn": 6434,
    "wiki-crm": 107,
    # postgres.business.*
    "business-company-profiles": 5424,
    "business-capabilities": 11927,
}
TONG_LOP1_THAM_CHIEU = 11733       # 5192 + 6434 + 107
KY_TU_LOP1_THAM_CHIEU = 7_509_969  # do ngay 25/09/2026
RAC_WEB_LOP1_THAM_CHIEU = 110      # 110/5192 doan cua ho-so-niem-yet = 2,1%

# Bang goc doan_tri_thuc co 17.788 doan. 17.788 - 116 - 5.939 = 11.733.
TONG_BANG_GOC_THAM_CHIEU = 17788


# ---------------------------------------------------------------------------
# 2. DANH SACH TRANG NGUON
# ---------------------------------------------------------------------------
# Chi 3 gia tri `nguon` duoc phep ra khoi bang bdsg_chat.doan_tri_thuc.
NGUON_CHO_PHEP_LOP1 = frozenset({"ho-so-niem-yet", "ho-so-dn", "wiki-crm"})

# Hai nguon may sinh qua cong LiteLLM. Chung ton tai trong bang va BI LOAI CO CHU DICH:
#   - dau ra cua mo hinh ben thu ba: dieu khoan nha cung cap thuong cam dung de huan luyen
#     mo hinh canh tranh;
#   - 3.601 nao agent la cau hinh thuong mai cua BDSG.
# Liet ke ra day (thay vi chi loc ngam) de khi chung xuat hien thi script BIET day la
# truong hop da luong truoc, con moi thu khac la truong hop CHUA luong truoc -> dung.
NGUON_DA_BIET_LOAI_LOP1 = frozenset({"nao-agent", "bai-dang-bds"})

# `tin-tuc` va `bai-dang` KHONG nam trong bang nay (17.788 = 11.733 + 116 + 5.939, khong
# con cho cho nguon nao khac). Chung o nguon khac va script nay khong bao gio truy van toi.

NGUON_LOP2 = "business-company-profiles"
NGUON_LOP3 = "business-capabilities"

GIAY_PHEP = "CC-BY-4.0"


# ---------------------------------------------------------------------------
# 3. TEN COT - CHUA DOI CHIEU VOI LUOC DO THAT
# ---------------------------------------------------------------------------
# Noi thang: ten cot cua `doan_tri_thuc` va `company_sector_links` duoi day la DU DOAN,
# chua doi chieu voi lược đồ that ngay 25/09/2026. Cac cot cua company_profiles va
# capabilities thi co trong so do (is_published, products, province_id, summary, name,
# name_en, description).
#
# Vi the script GOI `kiem_cot()` truoc moi truy van: neu ten khong dung, no in ra danh
# sach cot THAT cua bang va dung. Sua lai o day roi chay lai - khong phai doan mo.
COT = {
    "doan_tri_thuc.khoa": "id",
    "doan_tri_thuc.nguon": "nguon",
    "doan_tri_thuc.noi_dung": "noi_dung",
    "company_profiles.khoa": "id",
    "company_profiles.ten": "name",
    "company_profiles.tom_tat": "summary",
    "company_profiles.san_pham": "products",
    "company_profiles.ma_tinh": "province_id",
    "company_profiles.da_xuat_ban": "is_published",
    "company_sector_links.cong_ty": "company_id",
    # CHU Y: `sector_id` la KHOA NGOAI (so hieu), KHONG phai ten nganh. Bang danh muc
    # nganh (noi giu cot ten) chua duoc doi chieu luoc do, nen chua khai o day va truy van
    # lop 2 chua JOIN sang no. `lay_lop2()` co mot buoc kiem DUNG HAN neu `nganh` ra toan
    # chu so - de khong ghi ra mot tep "hop le" ma noi dung la so hieu noi bo.
    "company_sector_links.nganh": "sector_id",
    "capabilities.khoa": "id",
    "capabilities.ten": "name",
    "capabilities.ten_en": "name_en",
}


class LoiDungHan(Exception):
    """Loi khien script dung han. Moi truong hop hong-thi-dong nem loi nay."""


# ---------------------------------------------------------------------------
# 4. BO DO DU LIEU CA NHAN
# ---------------------------------------------------------------------------
# Ket qua quet ngay 25/09/2026 tren 11.733 doan phat hanh duoc:
#   0 email - 0 so dien thoai - 0 URL noi bo
#   29 khop "ma so thue"   : phan lon la MST/so DKKD doanh nghiep (thong tin dang ky CONG
#                            KHAI o Viet Nam), lan vai duong tinh gia (ten lop CSS, truong
#                            `rev` trong JSON).
#   5  khop "dia chi IP"   : TAT CA la duong tinh gia - so tien kieu Viet Nam
#                            (120.086.720.000 dong).
# Hai con so 29 va 5 la ly do cac bo do duoi day duoc viet chat hon muc thong thuong.

RE_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# So dien thoai Viet Nam sau quy hoach dau so 2018: 10 chu so, bat dau `0` + dau so hop le
# [2,3,5,7,8,9] (02x co dinh; 03/05/07/08/09 di dong). Hoac dang +84/84 bo so 0 dau.
# Cho phep dau cach, cham, gach noi giua cac nhom - do la cach nguoi ta viet that.
#
# VI SAO PHAI RANG BUOC DAU SO, KHONG BAT "0 + 9 CHU SO":
# Ma so thue Viet Nam cung la 10 chu so bat dau bang `0` (vi du 0101234567). Mot bo do
# "0 + 9 chu so" se bat MOI ma so thue thanh so dien thoai. Vi nguong chan cua
# `dien_thoai` la 0, script se TU CHAN CHINH MINH tren 29 khop ma so thue hop phap da do
# ngay 25/09/2026 - va nguoi chay se bi day toi cho ha nguong, tuc la pha lop bao ve that.
# Rang buoc dau so loai duoc phan lon: `01xx` khong phai dau so hop le nao.
RE_DIEN_THOAI = re.compile(
    r"(?<![0-9])(?:\+?84[.\s\-]?|0)(?:[235789])(?:[.\s\-]?[0-9]){8}(?![0-9])"
)

# Tu ngu bao hieu day la ma so thue / so dang ky kinh doanh, khong phai so dien thoai.
RE_NGU_CANH_MST = re.compile(
    r"(?:mã\s*số\s*thuế|ma\s*so\s*thue|\bMST\b|\bĐKKD\b|\bDKKD\b|"
    r"đăng\s*ký\s*kinh\s*doanh|dang\s*ky\s*kinh\s*doanh|mã\s*số\s*doanh\s*nghiệp)",
    re.IGNORECASE,
)

# Bon nhom so ngan bang dau cham. CHUA phai IP - con phai qua `la_ip_that()`.
RE_UNG_VIEN_IP = re.compile(r"(?<![0-9.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![0-9])")

# Ma so thue Viet Nam: dung 10 chu so, hoac 10-3 (don vi truc thuoc).
# CO Y bat theo DINH DANG chu khong bat "day chu so dai": chinh kieu bat "day chu so dai"
# da tao ra duong tinh gia o ten lop CSS (`col-12-3849`) va o truong `rev` trong JSON
# (`3-a1f09c7e...`) trong lan quet 25/09/2026.
RE_MA_SO_THUE = re.compile(r"(?<![0-9\-])\d{10}(?:-\d{3})?(?![0-9\-])")

# Don vi tien te di ngay sau mot so - dau hieu manh cua "so tien", khong phai dia chi IP.
RE_DON_VI_TIEN = re.compile(r"^\s*(?:đồng|dong|vnđ|vnd|₫|tỷ|ty|triệu|trieu)\b", re.IGNORECASE)


def la_ip_that(nhom: tuple, van_ban: str, vi_tri_ket: int) -> bool:
    """Phan biet dia chi IPv4 that voi so tien viet kieu Viet Nam.

    Day la cai bay RIENG cua tieng Viet: nguoi Viet dung DAU CHAM lam dau phan cach hang
    nghin, nen `120.086.720.000 dong` nhin y het mot dia chi IPv4. Mot bo do viet cho
    tieng Anh khong luong truoc dieu nay. Ca 5 khop "dia chi IP" trong lan quet
    25/09/2026 deu la kieu nay.

    Ba luat phan biet, du de loai 5/5 ma khong phai tat lop kiem IP that:
      1. IPv4 hop le co moi nhom <= 255. Nhom `720` -> khong phai IP.
      2. IPv4 khong viet so 0 o dau nhom. Nhom `086` va `000` -> khong phai IP.
      3. So tien thuong di kem `dong` / `VND` / `₫` ngay sau.

    Luu y ve `000`: no BANG 0 nen KHONG vi pham luat 1 - no bi LUAT 2 loai (so 0 dung
    dau). Ghi ro vi tung viet nham cho nay: ke ca luat cung phai dung dung luat cua no,
    khong thi lan sau sua bo do se sua nham cai luat khong lien quan.
    """
    for phan in nhom:
        if len(phan) > 1 and phan[0] == "0":
            return False  # luat 2
        if int(phan) > 255:
            return False  # luat 1
    if RE_DON_VI_TIEN.match(van_ban[vi_tri_ket:vi_tri_ket + 12]):
        return False  # luat 3
    return True


def do_url_noi_bo(van_ban: str, ten_mien_noi_bo: frozenset) -> list:
    """Do URL tro vao ha tang noi bo.

    KHONG cai san ten mien nao cua BDSG trong ma nguon - ten may chu la thong tin ha tang,
    khong thuoc ve mot script phat hanh cong khai. Ten mien noi bo (neu can) truyen qua
    bien moi truong BDSG_TEN_MIEN_NOI_BO.

    Khi khong co danh sach ay, van con do duoc ba dau hieu KHONG phu thuoc ten mien:
      - may chu la dia chi IP rieng (10.x, 172.16-31.x, 192.168.x) hoac loopback;
      - duoi .local / .internal / .lan / .test;
      - co cong tuong minh trong URL - trang cong khai gan nhu khong bao gio viet so cong
        ra, con dia chi noi bo thi hay. (KHONG viet vi du so cong that o day: mot so cong
        cu the la thong tin ha tang, va tai lieu nay la tai lieu cong khai.)
    """
    ket_qua = []
    for khop in re.finditer(r"https?://([^/\s\"'<>)]+)", van_ban, re.IGNORECASE):
        may_chu = khop.group(1).lower()
        ten, _, cong = may_chu.partition(":")
        la_noi_bo = False
        if cong and cong.isdigit():
            la_noi_bo = True
        if ten in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            la_noi_bo = True
        if ten.endswith((".local", ".internal", ".lan", ".test")):
            la_noi_bo = True
        if re.match(r"^10\.|^192\.168\.|^172\.(1[6-9]|2\d|3[01])\.", ten):
            la_noi_bo = True
        for mien in ten_mien_noi_bo:
            if ten == mien or ten.endswith("." + mien):
                la_noi_bo = True
        if la_noi_bo:
            ket_qua.append(khop.group(0))
    return ket_qua


def quet_du_lieu_ca_nhan(van_ban: str, ten_mien_noi_bo: frozenset) -> dict:
    """Quet mot chuoi, tra ve dict {loai: [cac khop]}.

    Tra ve CAC KHOP chu khong chi dem, de bao cao noi duoc *cai gi* bi bat - mot con so
    "3 khop" khong giup ai quyet dinh duoc gi.
    """
    ip_that = []
    for khop in RE_UNG_VIEN_IP.finditer(van_ban):
        if la_ip_that(khop.groups(), van_ban, khop.end()):
            ip_that.append(khop.group(0))

    mst = [(k.start(), k.end(), k.group(0)) for k in RE_MA_SO_THUE.finditer(van_ban)]
    nhip_mst = {(a, b) for a, b, _ in mst}

    # Ngay ca khi da rang buoc dau so, mot ma so thue kieu 0312345678 van trung dang mot so
    # di dong that. Khong the phan biet bang rieng con so - phai nhin NGU CANH. Khop nao
    # trung y het mot khop ma so thue VA co tu "ma so thue"/"DKKD"/... dung truoc trong
    # vong 40 ky tu thi xep vao dien NHAP NHANG, bao cao chu khong chan.
    #
    # Chu y: chung KHONG bi bo di im lang. Chung duoc dem rieng va in ra trong bao cao, de
    # nguoi chay nhin thay va tu quyet. Bo qua im lang chinh la ho loi ma ca thiet ke nay
    # dung de chong.
    dien_thoai, nhap_nhang = [], []
    for k in RE_DIEN_THOAI.finditer(van_ban):
        truoc = van_ban[max(0, k.start() - 40):k.start()]
        if (k.start(), k.end()) in nhip_mst and RE_NGU_CANH_MST.search(truoc):
            nhap_nhang.append(k.group(0))
        else:
            dien_thoai.append(k.group(0))

    return {
        "email": RE_EMAIL.findall(van_ban),
        "dien_thoai": dien_thoai,
        "url_noi_bo": do_url_noi_bo(van_ban, ten_mien_noi_bo),
        "dia_chi_ip": ip_that,
        "ma_so_thue": [t for _, _, t in mst],
        "mst_trung_dang_dien_thoai": nhap_nhang,
    }


# Loai nao CHAN khong cho ghi tep, loai nao chi bao cao.
#
# `ma_so_thue` chi BAO CAO, khong chan: ma so thue va so dang ky kinh doanh cua doanh
# nghiep la THONG TIN DANG KY CONG KHAI o Viet Nam - tra duoc tren cong thong tin quoc gia
# ve dang ky doanh nghiep. Chung la dinh danh CUA PHAP NHAN, khong phai du lieu ca nhan cua
# the nhan. Nhung van dem va in ra de nguoi chay tu quyet.
#
# `dia_chi_ip` CHAN voi nguong 0: sau khi `la_ip_that()` da loai het so tien Viet Nam, thu
# con lai la IP that - va IP that trong ngu lieu phat hanh la ha tang bi lo.
#
# Luu y da biet: mot so dien thoai that (10 chu so) cung khop RE_MA_SO_THUE, nen con so
# `ma_so_thue` co the cao hon so ma so thue that. Khong sua vi khong dang: `ma_so_thue` chi
# de bao cao, con `dien_thoai` - lop CHAN that - van bat dung so dien thoai ay. Noi ra day
# de nguoi doc bao cao khong ngo con so `ma_so_thue` la con so sach.
NGUONG_CHAN = {
    "email": 0,
    "dien_thoai": 0,
    "url_noi_bo": 0,
    "dia_chi_ip": 0,
}
LOAI_CHI_BAO_CAO = ("ma_so_thue", "mst_trung_dang_dien_thoai")


# ---------------------------------------------------------------------------
# 5. BO DO RAC CAO WEB
# ---------------------------------------------------------------------------
# So do 25/09/2026: 110 doan dinh rac (menu web/CSS/JS/URL ngoai), 0,17 MB tren 7,16 MB
# = 2,3%; tap trung o ho-so-niem-yet (110/5.192 = 2,1%).
#
# Bo do nay GAN CO chu KHONG XOA. Ly do: bo loc lam sach tu dong chua duoc viet va chua
# duoc do do chinh xac. Gan co la noi that nhung gi da do; xoa di la quyet thay cho nguoi
# dung ha nguon bang mot cong cu chua ai kiem.
#
# Bo do nay la bo do CUA SCRIPT NAY, KHONG phai bo do da tao ra con so 110. Hai bo do khac
# nhau co the ra hai con so khac nhau - vi vay ham `bao_cao()` in ca hai de doi chieu, thay
# vi gia vo chung la mot.
DAU_HIEU_RAC_WEB = (
    re.compile(r"<\s*/?\s*(?:div|span|script|style|nav|ul|li|a)\b", re.IGNORECASE),
    re.compile(r"\{[^{}]*:[^{}]*;[^{}]*\}"),                       # khoi khai bao CSS
    re.compile(r"\b(?:function|var|const|let)\s+\w+\s*[=(]"),      # manh JavaScript
    re.compile(r"\b(?:class|id)\s*=\s*[\"']"),                     # thuoc tinh HTML
    re.compile(r"(?:Trang chủ|Giới thiệu|Liên hệ)\s*[|>/]\s*\S+"), # vet breadcrumb/menu
    re.compile(r"https?://\S+\s+https?://\S+"),                    # chum URL lien tiep
)


def co_rac_web(van_ban: str) -> bool:
    return any(m.search(van_ban) for m in DAU_HIEU_RAC_WEB)


# ---------------------------------------------------------------------------
# 6. Tien ich
# ---------------------------------------------------------------------------

def bien_moi_truong_bat_buoc(ten: str) -> str:
    """Doc bien moi truong bat buoc. KHONG co gia tri mac dinh - do la ca y do.

    Mot gia tri mac dinh kieu 'postgresql://localhost/mot_ten_doan_duoc' se khien script
    chay duoc tren may ai do va noi vao nham CSDL ma khong ai biet. Tha dung ngay.

    KHONG viet so cong that vao vi du: mot so cong cu the la thong tin ha tang, con tep
    nay la tep cong khai. (Cong `khong-ha-tang` mien tru dang 'localhost:<cong>' vi coi do
    la gia tri chung - nghia la no se KHONG bat duoc cho nay. Do la gioi han cua cong,
    khong phai giay phep de viet.)
    """
    gia_tri = os.environ.get(ten, "").strip()
    if not gia_tri:
        raise LoiDungHan(
            "Thieu bien moi truong bat buoc: {}.\n"
            "Script nay KHONG co gia tri mac dinh cho thong tin may chu. "
            "Dat bien roi chay lai.".format(ten)
        )
    return gia_tri


def chuan_hoa(chuoi) -> str:
    """Chuan hoa Unicode ve NFC va bo khoang trang thua.

    NFC vi tieng Viet co hai cach ma hoa cho cung mot chu (chu dung san vs chu + dau to
    hop). Hai cach ay TRONG GIONG HET NHAU tren man hinh nhung la hai chuoi byte khac
    nhau: `len()` khac nhau, so sanh bang cho ra False, va bo tu vung BPE se hoc hai kieu
    rieng biet cho cung mot tu. Chuan hoa mot lan o day de moi phep dem ve sau nhat quan.
    """
    if chuoi is None:
        return ""
    s = unicodedata.normalize("NFC", str(chuoi))
    return re.sub(r"[ \t]+", " ", s).strip()


def ket_noi(dsn: str):
    if _pg is None:
        raise LoiDungHan(
            "Chua cai trinh dieu khien PostgreSQL. Cai mot trong hai:\n"
            "    pip install psycopg[binary]     (psycopg v3)\n"
            "    pip install psycopg2-binary     (psycopg2)"
        )
    return _pg.connect(dsn)


def kiem_cot(cur, luoc_do: str, bang: str, cot_can) -> None:
    """Kiem ten cot bang information_schema TRUOC khi truy van.

    Vi sao khong cu chay truy van roi bat loi: thong bao loi cua PostgreSQL khi sai ten cot
    khong cho biet ten DUNG la gi. Kiem o day thi bao ra duoc danh sach cot THAT, nguoi
    chay sua mot dong hang so o muc 3 la xong - thay vi phai mo CSDL len do.
    """
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s",
        (luoc_do, bang),
    )
    co_that = {d[0] for d in cur.fetchall()}
    if not co_that:
        raise LoiDungHan(
            "Khong thay bang {}.{} trong CSDL dang noi toi. "
            "Kiem lai DSN va ten bang.".format(luoc_do, bang)
        )
    thieu = [c for c in cot_can if c not in co_that]
    if thieu:
        raise LoiDungHan(
            "Bang {}.{} khong co cac cot: {}\n"
            "Cot THAT cua bang nay: {}\n"
            "Sua hang so COT o muc 3 cua xuat.py cho khop roi chay lai.".format(
                luoc_do, bang, ", ".join(thieu), ", ".join(sorted(co_that))
            )
        )


def goi(khoa: str) -> str:
    return COT[khoa]


# ---------------------------------------------------------------------------
# 7. LOP 1 - tri-thuc-van-ban
# ---------------------------------------------------------------------------

def lay_lop1(conn, ngay_do: str) -> list:
    ban_ghi = []
    with conn.cursor() as cur:
        kiem_cot(
            cur, "public", "doan_tri_thuc",
            [goi("doan_tri_thuc.khoa"), goi("doan_tri_thuc.nguon"), goi("doan_tri_thuc.noi_dung")],
        )

        # BUOC HONG-THI-DONG: liet ke TAT CA gia tri `nguon` co trong bang truoc, roi moi
        # loc. Neu loc truoc bang `WHERE nguon = ANY(...)` thi mot nguon moi se bi bo qua
        # HOAN TOAN IM LANG - dung cai kieu hong ma khong bao.
        cur.execute(
            "SELECT {n}, COUNT(*) FROM doan_tri_thuc GROUP BY {n} ORDER BY {n}".format(
                n=goi("doan_tri_thuc.nguon")
            )
        )
        thong_ke = {(r[0] or ""): int(r[1]) for r in cur.fetchall()}

        da_biet = NGUON_CHO_PHEP_LOP1 | NGUON_DA_BIET_LOAI_LOP1
        la = sorted(set(thong_ke) - da_biet)
        if la:
            raise LoiDungHan(
                "DUNG. Gap gia tri `nguon` ngoai danh sach trang trong doan_tri_thuc: {}\n"
                "Danh sach trang (duoc phat hanh): {}\n"
                "Da biet va bi loai co chu dich : {}\n"
                "Mot nguon moi la su kien can NGUOI xem xet ve giay phep va quyen rieng tu, "
                "khong phai truong hop de script tu quyet. Khong ghi tep nao.".format(
                    ", ".join(la),
                    ", ".join(sorted(NGUON_CHO_PHEP_LOP1)),
                    ", ".join(sorted(NGUON_DA_BIET_LOAI_LOP1)),
                )
            )

        tong_bang = sum(thong_ke.values())
        if tong_bang != TONG_BANG_GOC_THAM_CHIEU:
            canh_bao(
                "doan_tri_thuc co {} dong, so do 25/09/2026 la {}.".format(
                    tong_bang, TONG_BANG_GOC_THAM_CHIEU
                )
            )

        cur.execute(
            "SELECT {k}, {n}, {c} FROM doan_tri_thuc "
            "WHERE {n} = ANY(%s) ORDER BY {n}, {k}".format(
                k=goi("doan_tri_thuc.khoa"),
                n=goi("doan_tri_thuc.nguon"),
                c=goi("doan_tri_thuc.noi_dung"),
            ),
            (sorted(NGUON_CHO_PHEP_LOP1),),
        )
        for i, (khoa, nguon, noi_dung) in enumerate(cur.fetchall(), 1):
            text = chuan_hoa(noi_dung)
            if not text:
                continue  # doan rong khong day duoc gi cho mo hinh
            rac = co_rac_web(text)
            ban_ghi.append({
                "ma": "tvb-{:06d}".format(i),
                "lop": "tri-thuc-van-ban",
                "nguon": nguon,
                "giay_phep": GIAY_PHEP,
                "ngay_do": ngay_do,
                # `trung-binh` khi co co rac; moi truong hop khac la `cao`. Gan CO HOC
                # theo luat o luoc-do.md muc 3, khong theo cam tinh.
                "muc_tin_cay": "trung-binh" if rac else "cao",
                "ngon_ngu": "vi",
                "text": text,
                "so_ky_tu": len(text),
                "co_rac_web": rac,
                "ma_nguon_goc": str(khoa) if khoa is not None else None,
            })
    return ban_ghi


# ---------------------------------------------------------------------------
# 8. LOP 2 - ho-so-cong-ty
# ---------------------------------------------------------------------------

def lay_lop2(conn, ngay_do: str) -> list:
    ban_ghi = []
    with conn.cursor() as cur:
        kiem_cot(cur, "business", "company_profiles", [
            goi("company_profiles.khoa"), goi("company_profiles.ten"),
            goi("company_profiles.tom_tat"), goi("company_profiles.san_pham"),
            goi("company_profiles.ma_tinh"), goi("company_profiles.da_xuat_ban"),
        ])
        kiem_cot(cur, "business", "company_sector_links", [
            goi("company_sector_links.cong_ty"), goi("company_sector_links.nganh"),
        ])

        # DIEU KIEN LOC = DUNG BA DIEU: da xuat ban ^ co nganh ^ co san pham.
        # So do 25/09/2026: 5.424 ban ghi thoa ca ba. Day la con so DUY NHAT duoc phep
        # dung khi noi "doanh nghiep theo nganh nghe, tinh, san pham dich vu".
        #
        # TINH KHONG NAM TRONG BO LOC. 5.952/6.672 ho so co province_id, va province_id
        # khong phai dieu kien - nen mot phan trong 5.424 ban ghi se co ma_tinh = null.
        # Phan ay bao nhieu: CHUA DO.
        cur.execute(
            "SELECT p.{k}, p.{t}, p.{tt}, p.{sp}, p.{mt}, "
            "       COALESCE(ARRAY_AGG(DISTINCT l.{ng}::text) "
            "                FILTER (WHERE l.{ng} IS NOT NULL), '{{}}') AS nganh "
            "FROM business.company_profiles p "
            "JOIN business.company_sector_links l ON l.{ct} = p.{k} "
            "WHERE p.{xb} IS TRUE "
            "  AND p.{sp} IS NOT NULL AND btrim(p.{sp}::text) <> '' "
            "GROUP BY p.{k}, p.{t}, p.{tt}, p.{sp}, p.{mt} "
            "ORDER BY p.{k}".format(
                k=goi("company_profiles.khoa"), t=goi("company_profiles.ten"),
                tt=goi("company_profiles.tom_tat"), sp=goi("company_profiles.san_pham"),
                mt=goi("company_profiles.ma_tinh"), xb=goi("company_profiles.da_xuat_ban"),
                ct=goi("company_sector_links.cong_ty"), ng=goi("company_sector_links.nganh"),
            )
        )
        for i, (khoa, ten, tom_tat, san_pham, ma_tinh, nganh) in enumerate(cur.fetchall(), 1):
            ten = chuan_hoa(ten)
            tom_tat = chuan_hoa(tom_tat)
            san_pham = chuan_hoa(san_pham)
            nganh_sach = [chuan_hoa(x) for x in (nganh or []) if chuan_hoa(x)]
            if not ten or not san_pham or not nganh_sach:
                continue

            phan = ["{}.".format(ten), "Ngành: {}.".format("; ".join(nganh_sach))]
            if tom_tat:
                phan.append("Tóm tắt: {}".format(tom_tat))
            phan.append("Sản phẩm, dịch vụ: {}".format(san_pham))
            text = chuan_hoa(" ".join(phan))

            ban_ghi.append({
                "ma": "hsc-{:06d}".format(i),
                "lop": "ho-so-cong-ty",
                "nguon": NGUON_LOP2,
                "giay_phep": GIAY_PHEP,
                "ngay_do": ngay_do,
                "muc_tin_cay": "cao",
                "ngon_ngu": "vi",
                "text": text,
                "ten_cong_ty": ten,
                "nganh": nganh_sach,
                "san_pham": san_pham,
                # Ghi null chu KHONG bo khoa, va ma_tinh luon la CHUOI ke ca khi goc la so:
                # mot truong luc la so luc la chuoi se lam buoc suy lược đồ cua
                # `datasets.load_dataset('json', ...)` hong giua chung, va loi bao ra khi ay
                # chang lien quan gi toi cai sai that.
                "tom_tat": tom_tat or None,
                "ma_tinh": str(ma_tinh) if ma_tinh is not None else None,
                "da_xuat_ban": True,
                "so_ky_tu": len(text),
            })
            _ = khoa

    # KIEM SAU CUNG CUA LOP 2: `nganh` phai la TEN NGANH, khong duoc la SO HIEU.
    #
    # `company_sector_links.sector_id` la KHOA NGOAI tro sang bang danh muc nganh. Luoc do
    # cua bang danh muc ay CHUA duoc doi chieu (xem muc 3), nen truy van tren KHONG join
    # sang no - no chi `sector_id::text`. Neu cu the ma ghi ra thi truong `nganh` se chua
    # "12", "47" thay vi "Xay dung dan dung", va truong `text` se day mo hinh doc so hieu
    # noi bo: "Cong ty X. Nganh: 12; 47."
    #
    # Day dung la kieu hong ma khong bao: tep JSONL van hop le, van nap duoc, so ban ghi
    # van khop 5.424 - chi co noi dung la vo nghia. Cho nen: gap gia tri toan chu so thi
    # DUNG, khong ghi tep nao.
    #
    # Cach sua khi chay that: them bang danh muc nganh vao hang so COT o muc 3, JOIN them
    # mot bang nua trong truy van tren va lay cot TEN. Chua lam vi chua doi chieu duoc ten
    # bang/ten cot that ngay 25/09/2026 - noi thang thay vi doan mo.
    so_hieu = sorted({x for b in ban_ghi for x in b["nganh"] if x.isdigit()})
    if so_hieu:
        raise LoiDungHan(
            "DUNG. Truong `nganh` cua lop 2 dang chua SO HIEU chu khong phai TEN NGANH.\n"
            "Vi du gap duoc: {}\n"
            "Nguyen nhan: truy van lay `company_sector_links.sector_id` (khoa ngoai) ma "
            "chua JOIN sang bang danh muc nganh de lay cot ten.\n"
            "Sua: khai bang danh muc nganh o hang so COT (muc 3 cua xuat.py), JOIN them "
            "trong `lay_lop2()` va lay cot TEN. Khong ghi tep nao.".format(
                ", ".join(so_hieu[:10])
            )
        )
    return ban_ghi


# ---------------------------------------------------------------------------
# 9. LOP 3 - nang-luc
# ---------------------------------------------------------------------------

def lay_lop3(conn, ngay_do: str) -> list:
    """Xuat danh muc nang luc.

    KHONG co truong `text`, va do la quyet dinh co ly do: mot danh muc 11.927 cai ten
    khong phai van xuoi. Do vao tien huan luyen la day mo hinh LAP DANH SACH - dung kieu
    hong lam diem danh gia dep len ma nang luc that di xuong. Khong co `text` thi bo nap
    tien huan luyen se LOI NGAY khi nap nham tep nay - loi vi thieu khoa bat buoc - thay vi
    am tham hoc sai. Mot loi on ao re hon mot loi im lang.

    COT `description` BI LOAI: 696.890 ky tu nhung chi 58 GIA TRI KHAC NHAU tren 11.927
    dong => la chuoi xuat xu do ETL lap lai, khong phai mo ta. Dem ky tu khong phai dem
    thong tin.
    """
    ban_ghi = []
    with conn.cursor() as cur:
        kiem_cot(cur, "business", "capabilities", [
            goi("capabilities.khoa"), goi("capabilities.ten"), goi("capabilities.ten_en"),
        ])
        cur.execute(
            "SELECT {k}, {t}, {te} FROM business.capabilities ORDER BY {k}".format(
                k=goi("capabilities.khoa"), t=goi("capabilities.ten"),
                te=goi("capabilities.ten_en"),
            )
        )
        for i, (khoa, ten, ten_en) in enumerate(cur.fetchall(), 1):
            ten = chuan_hoa(ten)
            ten_en = chuan_hoa(ten_en)
            if not ten:
                continue
            ban_ghi.append({
                "ma": "nlc-{:06d}".format(i),
                "lop": "nang-luc",
                "nguon": NGUON_LOP3,
                "giay_phep": GIAY_PHEP,
                "ngay_do": ngay_do,
                "muc_tin_cay": "cao",
                # Day la vat lieu SONG NGU duy nhat trong ca bo. Pham vi ngon ngu cua du an
                # la DUNG HAI, chot ngay 26/09/2026: tieng Viet (1) la chinh, tieng Anh (2)
                # la phu. Truong `ngon_ngu` ton tai de ti le ay DEM DUOC chu khong chi duoc
                # tuyen bo.
                #
                # Ham nay chi sinh dung hai gia tri: "vi+en" va "vi" (dong ngay duoi). Luoc
                # do o bo-du-lieu/luoc-do.md muc 5 dinh nghia dung ba: "vi", "vi+en" va
                # "en"; "en" chua co ban ghi nao o ban phat hanh nay.
                #
                # Chu thich cu o cho nay mo ta mot ngon ngu thu ba va mot gia tri enum cho
                # no. Ca hai da bi go khoi luoc do ngay 26/09/2026, nen chu thich ay khong
                # chi loi thoi ma SAI: no mo ta mot luoc do khong con ton tai, ngay tren
                # dong ma sinh gia tri. Chu thich sai nguy hon chu thich thieu, vi nguoi doc
                # tin no thay vi doc ma.
                "ngon_ngu": "vi+en" if ten_en else "vi",
                "ten": ten,
                "ten_en": ten_en or None,
                "so_ky_tu": len(ten) + len(ten_en),
            })
            _ = khoa
    return ban_ghi


# ---------------------------------------------------------------------------
# 10. Quet toan bo truoc khi ghi
# ---------------------------------------------------------------------------

def quet_toan_bo(cac_lop: dict, ten_mien_noi_bo: frozenset) -> dict:
    """Quet du lieu ca nhan tren MOI truong chuoi cua MOI ban ghi, o CA BA lop.

    Vi sao quet ca ba lop du so do 25/09/2026 chi co cho lop 1: ket qua quet cua lop 2 va
    lop 3 CHUA DO. Khong do thi khong duoc phep coi la sach.

    Vi sao quet MOI truong chuoi chu khong chi truong `text`: mot dia chi email lot vao
    `ten_cong_ty` thi van la mot dia chi email bi phat hanh.
    """
    tong = {loai: [] for loai in list(NGUONG_CHAN) + list(LOAI_CHI_BAO_CAO)}
    theo_lop = {}
    for ten_lop, ban_ghi in cac_lop.items():
        dem = {loai: 0 for loai in tong}
        for b in ban_ghi:
            for khoa, gia_tri in b.items():
                if khoa in ("ma", "nguon", "giay_phep", "ngay_do", "lop"):
                    continue
                if isinstance(gia_tri, str):
                    chuoi = gia_tri
                elif isinstance(gia_tri, list):
                    chuoi = " ".join(str(x) for x in gia_tri)
                else:
                    continue
                for loai, khop in quet_du_lieu_ca_nhan(chuoi, ten_mien_noi_bo).items():
                    if khop:
                        dem[loai] += len(khop)
                        if len(tong[loai]) < 20:   # giu vai vi du de bao cao noi duoc *cai gi*
                            tong[loai].extend(
                                "{}/{}:{}".format(ten_lop, b["ma"], k) for k in khop[:3]
                            )
        theo_lop[ten_lop] = dem
    return {"theo_lop": theo_lop, "vi_du": tong}


# ---------------------------------------------------------------------------
# 11. Ghi va bao cao
# ---------------------------------------------------------------------------

_CANH_BAO = []


def canh_bao(thong_diep: str) -> None:
    _CANH_BAO.append(thong_diep)
    print("CANH BAO: {}".format(thong_diep), file=sys.stderr)


def ghi_jsonl(duong_dan: str, ban_ghi: list) -> int:
    """Ghi JSONL, tra ve so byte that cua tep.

    `ensure_ascii=False`: tieng Viet giu nguyen chu co dau. Neu de mac dinh True thi moi
    chu co dau bi thoat thanh \\uXXXX, tep phinh len nhieu lan va moi phep dem ky tu ve sau
    deu sai.

    Ghi ra `.tmp` roi doi ten: neu chet giua chung thi khong de lai mot tep JSONL cut ma
    nguoi khac tuong la tep that.
    """
    tam = duong_dan + ".tmp"
    with open(tam, "w", encoding="utf-8", newline="\n") as f:
        for b in ban_ghi:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")
    os.replace(tam, duong_dan)
    return os.path.getsize(duong_dan)


def bao_cao(cac_lop: dict, kich_thuoc: dict, ket_qua_quet: dict) -> None:
    print("")
    print("=" * 72)
    print("BAO CAO SO DO - bo du lieu mo Open BDSG")
    print("=" * 72)

    tong_bg = tong_kt = tong_byte = 0
    print("")
    print("{:<26} {:>9} {:>14} {:>14}".format("TEP", "BAN GHI", "KY TU", "BYTE THAT"))
    print("-" * 72)
    for ten_lop, ban_ghi in cac_lop.items():
        kt = sum(b.get("so_ky_tu", 0) for b in ban_ghi)
        by = kich_thuoc.get(ten_lop, 0)
        tong_bg += len(ban_ghi)
        tong_kt += kt
        tong_byte += by
        print("{:<26} {:>9,} {:>14,} {:>14,}".format(ten_lop + ".jsonl", len(ban_ghi), kt, by))
    print("-" * 72)
    print("{:<26} {:>9,} {:>14,} {:>14,}".format("CONG", tong_bg, tong_kt, tong_byte))

    # "KY TU" va "BYTE THAT" khac nhau la BINH THUONG va can noi ro: chu tieng Viet co dau
    # ma hoa UTF-8 ton 2-3 byte. Moi con so "MB" trong thẻ dữ liệu la quy doi tu SO KY TU
    # (chia 1.048.576), khong phai dung luong tep. Dung so nay de sua lai thẻ dữ liệu neu
    # can, thay vi de hai con so mau thuan nhau ma khong ai giai thich.
    print("")
    print("Ghi chu: KY TU dem ky tu Unicode; BYTE THAT la dung luong tep UTF-8 tren dia.")
    print("         Hai con so khac nhau la dung - tieng Viet co dau ton 2-3 byte/ky tu.")

    print("")
    print("DOI CHIEU VOI SO DO THAM CHIEU NGAY {}".format(NGAY_DO_THAM_CHIEU))
    print("-" * 72)
    dem_nguon = {}
    for ban_ghi in cac_lop.values():
        for b in ban_ghi:
            dem_nguon[b["nguon"]] = dem_nguon.get(b["nguon"], 0) + 1
    for nguon in sorted(SO_DO_THAM_CHIEU):
        thuc = dem_nguon.get(nguon, 0)
        tham = SO_DO_THAM_CHIEU[nguon]
        lech = thuc - tham
        dau = "khop" if lech == 0 else "LECH {:+,}".format(lech)
        print("{:<30} thuc {:>8,}   tham chieu {:>8,}   {}".format(nguon, thuc, tham, dau))

    rac = sum(1 for b in cac_lop.get("tri-thuc-van-ban", []) if b.get("co_rac_web"))
    print("")
    print("Rac cao web (lop 1): bo do cua script dem {:,} doan; so do 25/09/2026 la {:,}.".format(
        rac, RAC_WEB_LOP1_THAM_CHIEU))
    print("  Hai con so nay do bang HAI BO DO KHAC NHAU nen lech la binh thuong.")
    print("  Con so 110 la so da do; con so tren la so cua bo do trong tep nay.")
    print("  Ban ghi dinh rac duoc GAN CO `co_rac_web`, KHONG bi xoa - bo loc lam sach")
    print("  chua duoc viet va chua duoc do do chinh xac.")

    print("")
    print("QUET DU LIEU CA NHAN (chay tren ca ba lop, truoc khi ghi)")
    print("-" * 72)
    for ten_lop, dem in ket_qua_quet["theo_lop"].items():
        phan = ["{}={}".format(k, v) for k, v in sorted(dem.items())]
        print("{:<26} {}".format(ten_lop, "  ".join(phan)))
    tong_mst = sum(d["ma_so_thue"] for d in ket_qua_quet["theo_lop"].values())
    if tong_mst:
        print("")
        print("  {} khop dang ma so thue. KHONG chan, va day la ly do:".format(tong_mst))
        print("  ma so thue / so DKKD cua doanh nghiep la THONG TIN DANG KY CONG KHAI o")
        print("  Viet Nam, la dinh danh CUA PHAP NHAN chu khong phai du lieu ca nhan cua")
        print("  the nhan. So do 25/09/2026 tren lop 1 la 29 khop.")
    tong_nn = sum(d["mst_trung_dang_dien_thoai"] for d in ket_qua_quet["theo_lop"].values())
    if tong_nn:
        print("")
        print("  {} khop NHAP NHANG: 10 chu so vua dung dang ma so thue vua dung dang so".format(tong_nn))
        print("  di dong, va co tu 'ma so thue'/'DKKD' dung truoc. Xep la ma so thue va")
        print("  KHONG chan, nhung in ra day de nguoi chay tu kiem - khong bo qua im lang.")

    print("")
    print("CHIA TAP HUAN LUYEN / KIEM TRA / THAM DINH")
    print("-" * 72)
    print("  KHONG kem theo ban phat hanh nay. Phep chia 16.151/835/802 da do la chia tren")
    print("  TOAN BO 17.788 doan cua bang goc, tuc CO CHUA 6.055 doan may sinh da bi loai.")
    print("  Ba con so ay KHONG ap dung duoc cho 11.733 doan phat hanh. Chia lai: CHUA LAM.")

    if _CANH_BAO:
        print("")
        print("CANH BAO ({}):".format(len(_CANH_BAO)))
        for c in _CANH_BAO:
            print("  - {}".format(c))
    print("=" * 72)


# ---------------------------------------------------------------------------
# 12. main
# ---------------------------------------------------------------------------

def main() -> int:
    print("Trinh dieu khien CSDL: {}".format(_TEN_TRINH_DIEU_KHIEN or "(chua cai)"))

    dsn_chat = bien_moi_truong_bat_buoc("BDSG_DSN_CHAT")
    dsn_business = bien_moi_truong_bat_buoc("BDSG_DSN_BUSINESS")
    thu_muc = bien_moi_truong_bat_buoc("BDSG_THU_MUC_XUAT")
    ngay_do = os.environ.get("BDSG_NGAY_DO", "").strip() or date.today().isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", ngay_do):
        raise LoiDungHan("BDSG_NGAY_DO phai dang YYYY-MM-DD, nhan duoc: {!r}".format(ngay_do))

    ten_mien_noi_bo = frozenset(
        t.strip().lower()
        for t in os.environ.get("BDSG_TEN_MIEN_NOI_BO", "").split(",")
        if t.strip()
    )
    if not ten_mien_noi_bo:
        canh_bao(
            "BDSG_TEN_MIEN_NOI_BO chua dat. Van do duoc URL tro vao IP rieng / cong tuong "
            "minh / duoi .local .internal .lan .test, nhung KHONG do duoc ten mien noi bo "
            "cu the. Dat bien nay de quet chat hon."
        )

    os.makedirs(thu_muc, exist_ok=True)

    cac_lop = {}
    print("Doc CSDL ngu lieu (BDSG_DSN_CHAT)...")
    with ket_noi(dsn_chat) as c1:
        cac_lop["tri-thuc-van-ban"] = lay_lop1(c1, ngay_do)
    print("  -> {:,} ban ghi".format(len(cac_lop["tri-thuc-van-ban"])))

    print("Doc CSDL business (BDSG_DSN_BUSINESS)...")
    with ket_noi(dsn_business) as c2:
        cac_lop["ho-so-cong-ty"] = lay_lop2(c2, ngay_do)
        print("  -> ho-so-cong-ty: {:,} ban ghi".format(len(cac_lop["ho-so-cong-ty"])))
        cac_lop["nang-luc"] = lay_lop3(c2, ngay_do)
        print("  -> nang-luc: {:,} ban ghi".format(len(cac_lop["nang-luc"])))

    # KIEM DANH SACH TRANG LAN HAI, tren ban ghi da dung xong. Lan dau kiem tren CSDL; lan
    # nay kiem tren thu SAP GHI RA DIA. Hai cho khac nhau, va cho thu hai moi la cho quan
    # trong: no bao dam khong co gi lot vao qua mot duong khac (loi lap trinh, noi nham lop).
    hop_le = NGUON_CHO_PHEP_LOP1 | {NGUON_LOP2, NGUON_LOP3}
    for ten_lop, ban_ghi in cac_lop.items():
        la = sorted({b["nguon"] for b in ban_ghi} - hop_le)
        if la:
            raise LoiDungHan(
                "DUNG. Lop {} chua `nguon` ngoai danh sach trang: {}. Khong ghi tep nao.".format(
                    ten_lop, ", ".join(la)
                )
            )

    # Kiem `ma` duy nhat tren toan bo - trung `ma` la loi im lang dien hinh: tep van hop le,
    # chi la khong truy nguoc duoc ban ghi nao ra ban ghi nao.
    tat_ca_ma = [b["ma"] for ban_ghi in cac_lop.values() for b in ban_ghi]
    if len(tat_ca_ma) != len(set(tat_ca_ma)):
        raise LoiDungHan("DUNG. Co `ma` bi trung trong bo du lieu. Khong ghi tep nao.")

    print("Quet du lieu ca nhan truoc khi ghi...")
    ket_qua_quet = quet_toan_bo(cac_lop, ten_mien_noi_bo)

    vi_pham = []
    for loai, nguong in NGUONG_CHAN.items():
        tong = sum(d[loai] for d in ket_qua_quet["theo_lop"].values())
        if tong > nguong:
            vi_pham.append((loai, tong, nguong))
    if vi_pham:
        print("", file=sys.stderr)
        print("DUNG - QUET DU LIEU CA NHAN VUOT NGUONG. KHONG GHI TEP NAO.", file=sys.stderr)
        for loai, tong, nguong in vi_pham:
            print("  {}: {} khop, nguong {}".format(loai, tong, nguong), file=sys.stderr)
            for v in ket_qua_quet["vi_du"][loai][:10]:
                print("      {}".format(v), file=sys.stderr)
        print("", file=sys.stderr)
        print("Neu day la duong tinh gia, SUA BO DO o muc 4 cua xuat.py va ghi lai ly do -",
              file=sys.stderr)
        print("dung ha nguong. So tien Viet Nam bi nham thanh IP la vi du da gap that:",
              file=sys.stderr)
        print("5/5 khop 'dia chi IP' ngay 25/09/2026 deu la so tien (xem ham la_ip_that).",
              file=sys.stderr)
        raise LoiDungHan("Quet du lieu ca nhan khong dat.")

    print("Quet dat. Bat dau ghi...")
    kich_thuoc = {}
    for ten_lop, ban_ghi in cac_lop.items():
        duong_dan = os.path.join(thu_muc, ten_lop + ".jsonl")
        kich_thuoc[ten_lop] = ghi_jsonl(duong_dan, ban_ghi)
        print("  ghi {}".format(duong_dan))

    lech = []
    dem_nguon = {}
    for ban_ghi in cac_lop.values():
        for b in ban_ghi:
            dem_nguon[b["nguon"]] = dem_nguon.get(b["nguon"], 0) + 1
    for nguon, tham in SO_DO_THAM_CHIEU.items():
        if dem_nguon.get(nguon, 0) != tham:
            lech.append("{}: thuc {:,} / tham chieu {:,}".format(
                nguon, dem_nguon.get(nguon, 0), tham))
    if lech:
        for l in lech:
            canh_bao("Lech so do tham chieu - {}".format(l))
        if os.environ.get("BDSG_CHAN_KHI_LECH") == "1":
            bao_cao(cac_lop, kich_thuoc, ket_qua_quet)
            raise LoiDungHan(
                "BDSG_CHAN_KHI_LECH=1 va so ban ghi lech so do tham chieu. "
                "Tep DA duoc ghi - kiem lai roi xoa neu can."
            )

    bao_cao(cac_lop, kich_thuoc, ket_qua_quet)
    print("")
    print("Xong. Cap nhat lai README.md neu cac con so o tren da doi so voi thẻ dữ liệu.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LoiDungHan as loi:
        print("", file=sys.stderr)
        print("LOI: {}".format(loi), file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print("Dung theo yeu cau nguoi dung.", file=sys.stderr)
        sys.exit(130)
