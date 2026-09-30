#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đo LỆCH giữa bản đang chạy và bản mã nguồn mở.

=============================================================================
VÌ SAO CÓ TỆP NÀY
=============================================================================
`bdsg.vn` không phải một bản đặc biệt — nó là **một thực thể** của chính kho này.
Nguyên tắc ấy chỉ có giá trị nếu có thứ **phát hiện được** khi hai bên lệch nhau.
Không có phép đo thì nguyên tắc chỉ là một câu trong README, và nó sẽ đúng vào
ngày viết rồi sai dần mà không ai được báo.

Lần chạy đầu tiên, 01/10/2026, tìm ra **8/8 mã màu trong kho lệch** với bản đang
phục vụ — vì chúng được đoán từ một ảnh chụp màn hình thay vì đọc từ sổ. Đó chính
là loại lệch mà tệp này tồn tại để bắt.

Nguồn sự thật phía đang chạy là `hst.js` — tệp mà mọi nền tảng BDSG nhúng để hiện
ô vuông chấm. Chính nó tự khai: *"SINH TỰ ĐỘNG từ hst/san-pham.json — ĐỪNG SỬA
TAY"*. Ở đây đọc `hst.js` chứ không đọc tệp nguồn, vì **bản đang phục vụ mới là
sự thật**; tệp nguồn có thể đã sửa mà chưa triển khai.

Chạy:
    python3 linh-vuc/do_lech.py                        # so với https://bdsg.vn
    python3 linh-vuc/do_lech.py --goc https://vi-du.vn
    python3 linh-vuc/do_lech.py --nhom "Hệ điều hành"

Thoát 0 khi không lệch, khác 0 khi có lệch. Fail-closed: không tải được `hst.js`
cũng là thoát khác 0 — "không đo được" không phải "không lệch".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "linh-vuc"))

import so_ghi  # noqa: E402

NHOM_MAC_DINH = "Hệ điều hành"


def doc_hst(goc: str) -> List[Dict[str, Any]]:
    url = goc.rstrip("/") + "/hst.js"
    yc = urllib.request.Request(url, headers={"User-Agent": "open-bdsg-do-lech"})
    with urllib.request.urlopen(yc, timeout=20) as r:
        van = r.read().decode("utf-8", "replace")

    i = van.find("var NHOM")
    if i < 0:
        raise SystemExit(f"  KHÔNG tìm thấy `var NHOM` trong {url} — hst.js đã đổi cấu trúc.")
    khoi = van[i: van.find("];", i) + 2]

    nhom: List[Dict[str, Any]] = []
    for m in re.finditer(r'\{\s*ten:\s*"([^"]+)",\s*sp:\s*\[(.*?)\]\s*,?\s*\}', khoi, re.S):
        sp = [
            {"ten": k.group(1), "url": k.group(2), "mo": k.group(3), "mau": k.group(4)}
            for k in re.finditer(
                r'\{\s*ten:\s*"([^"]+)"\s*,\s*url:\s*"([^"]+)"\s*,'
                r'\s*mo:\s*"([^"]*)"\s*,\s*mau:\s*"([^"]+)"\s*\}',
                m.group(2),
            )
        ]
        nhom.append({"ten": m.group(1), "sp": sp})
    if not nhom:
        raise SystemExit(f"  Đọc được `var NHOM` nhưng bóc ra 0 nhóm — khuôn bóc đã lỗi thời.")
    return nhom


def main() -> int:
    ap = argparse.ArgumentParser(description="Đo lệch giữa bản đang chạy và kho mã nguồn mở.")
    ap.add_argument("--goc", default="https://bdsg.vn")
    ap.add_argument("--nhom", default=NHOM_MAC_DINH)
    ns = ap.parse_args()

    try:
        ds = so_ghi.nap()
    except so_ghi.LoiBanKhai as e:
        print(f"  HỎNG ở bản khai: {e}")
        return 1

    nhom = doc_hst(ns.goc)
    chon = [n for n in nhom if n["ten"] == ns.nhom]
    if not chon:
        print(f"  KHÔNG có nhóm {ns.nhom!r}. Các nhóm đang phục vụ: "
              + ", ".join(repr(n['ten']) for n in nhom))
        return 1
    dang_chay = chon[0]["sp"]

    print(f"  Đang chạy : {ns.goc}/hst.js — {len(nhom)} nhóm, "
          f"{sum(len(n['sp']) for n in nhom)} sản phẩm")
    print(f"  Nhóm so   : {ns.nhom!r} ({len(dang_chay)} sản phẩm)")
    print(f"  Trong kho : {len(ds)} lĩnh vực\n")

    theo_url = {s["url"].rstrip("/"): s for s in dang_chay}
    lech: List[str] = []

    # Khoa noi la `nguon_bdsg` — mot TRUONG DU LIEU, khong phai mot quy uoc dat ten.
    trong_kho = {}
    for lv in ds:
        u = getattr(lv, "nguon_bdsg", None) or ""
        if not u:
            j = json.loads((GOC / lv.tep).read_text(encoding="utf-8"))
            u = (j.get("nguon_bdsg") or "").rstrip("/")
        if not u:
            lech.append(f"CHỈ TRONG KHO (không khai `nguon_bdsg`, không nối được): {lv.ma}")
            continue
        trong_kho[u] = lv

    for u, s in sorted(theo_url.items()):
        lv = trong_kho.get(u)
        if lv is None:
            lech.append(f"CHỈ TRÊN {ns.goc}: {s['ten']} ({u}) — kho chưa có lĩnh vực nào cho nó")
            continue
        if lv.ten != s["ten"]:
            lech.append(f"TÊN LỆCH   {u}: kho={lv.ten!r} ≠ đang chạy={s['ten']!r}")
        if lv.bieu_tuong.get("mau", "").lower() != s["mau"].lower():
            lech.append(f"MÀU LỆCH   {u}: kho={lv.bieu_tuong.get('mau')} ≠ đang chạy={s['mau']}")

    for u, lv in sorted(trong_kho.items()):
        if u not in theo_url:
            lech.append(f"CHỈ TRONG KHO: {lv.ma} → {u} — bản đang chạy không còn sản phẩm này")

    if not lech:
        print(f"  ĐẠT: {len(theo_url)} sản phẩm khớp hoàn toàn (tên, màu, địa chỉ nguồn).")
        print("  NHẮC: phép đo này so SỔ SẢN PHẨM, không so mã nguồn. Hai bên có thể cùng")
        print("        tên mà khác hẳn bên trong — đó là việc của các phép đo khác.")
        return 0

    print(f"  LỆCH {len(lech)} chỗ:")
    for d in lech:
        print(f"    {d}")
    print("\n  bdsg.vn là MỘT THỰC THỂ của kho này, không phải bản đặc biệt.")
    print("  Mỗi dòng trên là một chỗ hai bản đã rời nhau — sửa bên sai, đừng sửa phép đo.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
