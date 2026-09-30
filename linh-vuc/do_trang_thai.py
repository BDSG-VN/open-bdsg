#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đo trạng thái thật của từng lĩnh vực. Không đọc lời khai của ai.

Bảng điều khiển đọc tệp `cong/trang-thai-linh-vuc.json` mà tệp này ghi ra. Bản khai
`linh-vuc.json` KHÔNG được chứa `trang_thai` — `so_ghi.py` từ chối nếu có.

=============================================================================
PHÉP ĐO QUAN TRỌNG NHẤT: TÀI NGUYÊN CÓ GIẢI ĐƯỢC DƯỚI ĐƯỜNG DẪN KHÔNG
=============================================================================
Một ứng dụng một trang dựng với `base: "/"` mà phục vụ ở `/map5d/` sẽ xin
`/assets/index.js` thay vì `/map5d/assets/index.js`. Kết quả: tài nguyên 404,
JavaScript không chạy, **trang trắng — nhưng mã HTTP của trang vẫn là 200.**

Đo ngày 01/10/2026 trên chính hệ BDSG: 5/8 sản phẩm nhóm hệ điều hành đang tham
chiếu tài nguyên bằng đường dẫn tuyệt đối. Nếu gộp chúng dưới đường dẫn mà không
dựng lại thì cả 5 sẽ trắng trang và mọi phép kiểm mã HTTP đều báo lành.

Nên ở đây: lấy HTML về, bóc mọi `src=`/`href=` trỏ tới .js/.css, rồi **tải thật
từng cái** theo đúng cách trình duyệt sẽ giải đường dẫn.

Chạy:
    python3 linh-vuc/do_trang_thai.py                      # đo tại chỗ (tệp trên đĩa)
    python3 linh-vuc/do_trang_thai.py --goc https://vi-du.test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "linh-vuc"))

import so_ghi  # noqa: E402

MAU_TAI_NGUYEN = re.compile(
    r"""<(?:script|link)\b[^>]*?(?:src|href)\s*=\s*["']([^"']+\.(?:js|css))["']""",
    re.IGNORECASE,
)
HET_GIO = 12


def _tai(url: str) -> Dict[str, Any]:
    try:
        yc = urllib.request.Request(url, headers={"User-Agent": "open-bdsg-do-trang-thai"})
        with urllib.request.urlopen(yc, timeout=HET_GIO) as r:
            than = r.read()
            return {"ma": r.status, "so_byte": len(than), "than": than}
    except urllib.error.HTTPError as e:
        return {"ma": e.code, "so_byte": 0, "than": b"", "loi": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"ma": 0, "so_byte": 0, "than": b"", "loi": f"{type(e).__name__}: {e}"}


def do_mot(lv: so_ghi.LinhVuc, goc: Optional[str]) -> Dict[str, Any]:
    kq: Dict[str, Any] = {
        "ma": lv.ma, "ten": lv.ten, "duong_dan": lv.duong_dan, "loai": lv.loai,
        "trang_thai": "chua-do", "bang_chung": [], "canh_bao": [],
    }

    if goc is None:
        # Không có gốc để gọi thì KHÔNG đoán. "chua-do" là câu trả lời đúng.
        kq["bang_chung"].append("không truyền --goc nên chưa gọi thử lần nào")
        return kq

    url = goc.rstrip("/") + lv.duong_dan + "/"
    r = _tai(url)
    kq["bang_chung"].append(f"GET {url} → HTTP {r['ma']}, {r['so_byte']} byte")

    if r["ma"] != 200:
        kq["trang_thai"] = "hong"
        kq["bang_chung"].append(r.get("loi", ""))
        return kq

    if lv.loai == "proxy":
        # Voi proxy, trang gioi thieu 200 KHONG chung minh tien trinh phia sau song.
        kq["trang_thai"] = "mot-phan"
        kq["canh_bao"].append(
            "loại `proxy`: trang 200 chỉ chứng minh cửa mở, KHÔNG chứng minh tiến trình "
            "phía sau còn sống. Phải đo riêng điểm cuối của nó."
        )
        return kq

    try:
        html = r["than"].decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        html = ""

    tn = MAU_TAI_NGUYEN.findall(html)
    if not tn:
        # Trang tu chua (CSS/JS noi dong). Khong co gi de hong duoi duong dan.
        kq["trang_thai"] = "chay-duoc"
        kq["bang_chung"].append("0 tài nguyên ngoài — trang tự chứa, gộp dưới đường dẫn không đổi gì")
        return kq

    hong: List[str] = []
    for t in tn[:24]:
        # Giai dung nhu trinh duyet: tuyet doi thi tu goc, tuong doi thi tu URL trang.
        that = urljoin(url, t)
        if urlparse(that).netloc != urlparse(url).netloc:
            kq["canh_bao"].append(f"tài nguyên ngoài miền: {t}")
            continue
        rr = _tai(that)
        if rr["ma"] != 200:
            hong.append(f"{t} → HTTP {rr['ma']} (giải thành {that})")

    kq["bang_chung"].append(f"{len(tn)} tài nguyên khai trong HTML, đã tải thử {min(len(tn),24)}")
    if hong:
        kq["trang_thai"] = "trang-trang"
        kq["bang_chung"].extend(hong[:6])
        kq["canh_bao"].append(
            "Trang trả 200 nhưng tài nguyên 404 — đây là TRANG TRẮNG, và mọi phép kiểm "
            "chỉ nhìn mã HTTP đều báo lành. Dựng lại với base = " + lv.duong_dan + "/"
        )
    else:
        kq["trang_thai"] = "chay-duoc"
    return kq


def main() -> int:
    ap = argparse.ArgumentParser(description="Đo trạng thái thật của từng lĩnh vực.")
    ap.add_argument("--goc", help="gốc HTTP để gọi thử, ví dụ https://vi-du.test")
    ap.add_argument("--ra", type=Path, default=GOC / "cong" / "trang-thai-linh-vuc.json")
    ns = ap.parse_args()

    try:
        ds = so_ghi.nap()
    except so_ghi.LoiBanKhai as e:
        print(f"  HỎNG ở bản khai: {e}")
        return 1

    muc = [do_mot(lv, ns.goc) for lv in ds]
    ra = {
        "do_luc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "goc_da_goi": ns.goc,
        "cach_do": "gọi thật từng đường dẫn rồi TẢI THẬT từng tài nguyên .js/.css mà HTML khai",
        "luat": (
            "Bản khai linh-vuc.json KHÔNG được chứa trang_thai. Tệp này là nguồn duy nhất "
            "của trạng thái, và 'chua-do' là một câu trả lời hợp lệ — khác hẳn 'chay-duoc'."
        ),
        "muc": muc,
    }
    ns.ra.parent.mkdir(parents=True, exist_ok=True)
    ns.ra.write_text(json.dumps(ra, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    dem: Dict[str, int] = {}
    for m in muc:
        dem[m["trang_thai"]] = dem.get(m["trang_thai"], 0) + 1
    print(f"  đã ghi {ns.ra.relative_to(GOC) if ns.ra.is_relative_to(GOC) else ns.ra}")
    for m in muc:
        c = " ⚠" if m["canh_bao"] else ""
        print(f"    {m['ma']:16s} {m['duong_dan']:14s} {m['trang_thai']:12s}{c}")
    print("  tổng: " + " · ".join(f"{k}={v}" for k, v in sorted(dem.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
