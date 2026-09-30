# -*- coding: utf-8 -*-
"""Sổ ghi lĩnh vực — nạp và KIỂM mọi bản khai `linh-vuc.json`.

Bộ kiểm này dùng lại **chính** khuôn tên của `nhan/quyen.py` thay vì chép lại. Chép
lại thì hai bản sẽ lệch nhau ở lần sửa đầu tiên, và lúc ấy một mô-đun sẽ qua được
cổng nhưng bị nhân từ chối lúc chạy — hỏng mà không báo.

Chạy:
    python3 linh-vuc/so_ghi.py          # kiểm mọi bản khai, in bảng
    python3 linh-vuc/so_ghi.py --json   # in sổ ghi dạng JSON
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

GOC = Path(__file__).resolve().parent.parent


def _nap_quyen():
    """Nạp `nhan.quyen` NHƯ MỘT GÓI.

    Không nạp bằng `spec_from_file_location` trỏ thẳng vào quyen.py: tệp ấy có
    `from .danh_tinh import DanhTinh`, và nạp lẻ một tệp thì import tương đối
    không có gói cha nên nổ `ImportError`. Đã trúng lỗi này 01/10/2026.
    """
    if str(GOC) not in sys.path:
        sys.path.insert(0, str(GOC))
    from nhan import quyen  # noqa: PLC0415 — cố ý nạp muộn, sau khi sửa sys.path

    return quyen


LOAI_HOP_LE = {"tep-tinh", "spa-tinh", "proxy"}
# Hai truong nay do MAY do, nguoi khai vao la sai — xem linh-vuc/luoc-do.md.
TRUONG_CAM = ("trang_thai", "bang_chung")


class LoiBanKhai(ValueError):
    pass


def _ten_ngan(tep: Path) -> str:
    """Đường dẫn gọn để in ra, KHÔNG nổ khi tệp nằm ngoài gốc kho.

    `Path.relative_to` ném ValueError cho tệp ngoài gốc. Bài thử nộp bản khai từ
    một thư mục tạm, nên bản đầu của hàm này làm `nap()` nổ ngay ở bản khai đầu
    tiên — và vì nổ sớm nên MỌI phép kiểm va chạm giữa các lĩnh vực chưa từng
    chạy lần nào. Bài thử ngược đã bắt được điều đó ngày 01/10/2026.
    """
    try:
        return str(tep.relative_to(GOC))
    except ValueError:
        return str(tep)


@dataclass
class LinhVuc:
    ma: str
    ten: str
    tom_tat: str
    bieu_tuong: Dict[str, str]
    duong_dan: str
    loai: str
    cong_cu: List[str]
    quyen_can: List[str]
    ghi_chu: str = ""
    tep: str = ""


def _doi_chieu(j: Dict[str, Any], tep: Path, quyen) -> LinhVuc:
    def can(k: str, kieu):
        if k not in j:
            raise LoiBanKhai(f"{tep}: thiếu trường bắt buộc `{k}`")
        if not isinstance(j[k], kieu):
            raise LoiBanKhai(f"{tep}: `{k}` phải là {kieu.__name__}, đang là {type(j[k]).__name__}")
        return j[k]

    for c in TRUONG_CAM:
        if c in j:
            raise LoiBanKhai(
                f"{tep}: KHÔNG được khai `{c}` — trường này do linh-vuc/do_trang_thai.py "
                f"ĐO và ghi ra cong/trang-thai-linh-vuc.json. Một mô-đun tự khai 'chạy được' "
                f"thì lời khai ấy đúng vào ngày viết và sai dần sau đó mà không ai được báo."
            )

    ma = can("ma", str)
    # Ma linh vuc chinh la TIEN TO cong cu, nen no phai hop le theo dung khuon
    # ma nhan dung cho phan dau cua `namespace.tool`.
    if not quyen.MAU_TEN_DAY_DU.match(f"{ma}.x"):
        raise LoiBanKhai(
            f"{tep}: `ma` = {ma!r} không hợp khuôn tiền tố công cụ của nhan/quyen.py"
        )

    dd = can("duong_dan", str)
    if not dd.startswith("/") or dd.endswith("/") or "//" in dd or len(dd) < 2:
        raise LoiBanKhai(f"{tep}: `duong_dan` = {dd!r} phải bắt đầu bằng '/', không kết thúc bằng '/'")

    loai = can("loai", str)
    if loai not in LOAI_HOP_LE:
        raise LoiBanKhai(f"{tep}: `loai` = {loai!r} không thuộc {sorted(LOAI_HOP_LE)}")

    cc = can("cong_cu", list)
    if not cc:
        raise LoiBanKhai(f"{tep}: `cong_cu` rỗng — một lĩnh vực không có công cụ nào thì nhân không lái được nó")
    for t in cc:
        if not isinstance(t, str) or not quyen.MAU_TEN_DAY_DU.match(t):
            raise LoiBanKhai(f"{tep}: công cụ {t!r} không hợp khuôn `namespace.tool` của nhan/quyen.py")
        if not t.startswith(f"{ma}."):
            raise LoiBanKhai(
                f"{tep}: công cụ {t!r} phải mang tiền tố {ma!r}. Không ép tiền tố thì hai "
                f"lĩnh vực đặt trùng tên công cụ và chính sách quyền sẽ trỏ nhầm."
            )

    qc = can("quyen_can", list)
    hop = {quyen.DOC, quyen.GHI}
    la = set(qc) - hop
    if la:
        raise LoiBanKhai(f"{tep}: `quyen_can` có giá trị lạ {sorted(la)}; chỉ nhận {sorted(hop)}")

    bt = can("bieu_tuong", dict)
    if not (isinstance(bt.get("chu"), str) and len(bt["chu"]) == 1):
        raise LoiBanKhai(f"{tep}: `bieu_tuong.chu` phải là đúng MỘT ký tự")
    mau = bt.get("mau", "")
    if not (isinstance(mau, str) and len(mau) == 7 and mau[0] == "#"):
        raise LoiBanKhai(f"{tep}: `bieu_tuong.mau` phải dạng #RRGGBB, đang là {mau!r}")

    return LinhVuc(
        ma=ma, ten=can("ten", str), tom_tat=can("tom_tat", str), bieu_tuong=bt,
        duong_dan=dd, loai=loai, cong_cu=cc, quyen_can=qc,
        ghi_chu=j.get("ghi_chu", ""), tep=_ten_ngan(tep),
    )


def nap(goc: Path = None) -> List[LinhVuc]:
    """Nạp mọi bản khai. Ném LoiBanKhai ngay ở bản khai sai đầu tiên (fail-closed)."""
    goc = goc or (GOC / "linh-vuc")
    quyen = _nap_quyen()
    ds: List[LinhVuc] = []
    for tep in sorted(goc.glob("*/linh-vuc.json")):
        ds.append(_doi_chieu(json.loads(tep.read_text(encoding="utf-8")), tep, quyen))

    # ── Va cham giua cac linh vuc ────────────────────────────────────────────
    thay_ma: Dict[str, str] = {}
    for lv in ds:
        if lv.ma in thay_ma:
            raise LoiBanKhai(f"mã {lv.ma!r} bị khai hai lần: {thay_ma[lv.ma]} và {lv.tep}")
        thay_ma[lv.ma] = lv.tep

    # Va cham TIEN TO duong dan, khong chi va cham bang nhau. /tro-chuyen va
    # /tro-chuyen-cu khong bang nhau nhung may chu khop tien to se dan mot cai
    # vao cai kia. Du an nay da tra gia 4 lan cho dung ho loi ay.
    for i, a in enumerate(ds):
        for b in ds[i + 1:]:
            x, y = a.duong_dan, b.duong_dan
            if x == y:
                raise LoiBanKhai(f"đường dẫn {x!r} bị hai lĩnh vực dùng chung: {a.ma}, {b.ma}")
            if x.startswith(y + "/") or y.startswith(x + "/"):
                raise LoiBanKhai(
                    f"đường dẫn lồng nhau: {a.ma}={x!r} và {b.ma}={y!r}. "
                    f"Máy chủ khớp tiền tố sẽ dẫn một cái vào cái kia."
                )
            # Tien to chuoi (khong co dau '/' ngan cach) cung nguy hiem voi mot so
            # luat rewrite: /tro-chuyen va /tro-chuyen-cu.
            if x.startswith(y) or y.startswith(x):
                raise LoiBanKhai(
                    f"đường dẫn là tiền tố chuỗi của nhau: {a.ma}={x!r} và {b.ma}={y!r}. "
                    f"Đổi một trong hai; luật rewrite không anchor sẽ khớp nhầm."
                )

    thay_cc: Dict[str, str] = {}
    for lv in ds:
        for t in lv.cong_cu:
            if t in thay_cc:
                raise LoiBanKhai(f"công cụ {t!r} bị khai ở cả {thay_cc[t]} và {lv.ma}")
            thay_cc[t] = lv.ma
    return ds


def main() -> int:
    try:
        ds = nap()
    except LoiBanKhai as e:
        print(f"  HỎNG: {e}")
        return 1
    if "--json" in sys.argv:
        print(json.dumps([lv.__dict__ for lv in ds], ensure_ascii=False, indent=2))
        return 0
    print(f"  ĐẠT: {len(ds)} lĩnh vực, mọi bản khai hợp hợp đồng.")
    print(f"  {'mã':16s} {'đường dẫn':14s} {'loại':10s} {'quyền':10s} {'công cụ':8s} tên")
    for lv in ds:
        print(f"  {lv.ma:16s} {lv.duong_dan:14s} {lv.loai:10s} "
              f"{','.join(lv.quyen_can):10s} {len(lv.cong_cu):^8d} {lv.ten}")
    print(f"\n  Tổng công cụ MCP đã khai: {sum(len(lv.cong_cu) for lv in ds)}")
    print("  NHẮC: bảng này nói bản khai HỢP LỆ, không nói lĩnh vực CHẠY ĐƯỢC.")
    print("        Trạng thái chạy do linh-vuc/do_trang_thai.py đo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
