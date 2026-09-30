# -*- coding: utf-8 -*-
"""Thử ngược sổ ghi lĩnh vực.

Một bộ kiểm chỉ đáng tin khi nó ĐỎ lúc mã hỏng. Bài thử này cố tình nộp những bản
khai sai và đòi `so_ghi.nap()` phải từ chối TỪNG cái. Nếu một ngày ai đó nới bộ
kiểm, bài này phải đỏ trước khi bản khai hỏng kia lọt vào kho.

Chạy:  python3 linh-vuc/thu_so_ghi.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "linh-vuc"))

import so_ghi  # noqa: E402

DAT = 0
TRUOT = 0


def hop_le(**doi):
    j = {
        "ma": "vi_du", "ten": "Ví dụ", "tom_tat": "Một lĩnh vực ví dụ.",
        "bieu_tuong": {"chu": "V", "mau": "#123456"},
        "duong_dan": "/vi-du", "loai": "tep-tinh",
        "cong_cu": ["vi_du.lam_gi_do"], "quyen_can": ["doc"],
    }
    j.update(doi)
    return j


def nop(*cac_ban_khai):
    """Ghi các bản khai vào một thư mục tạm rồi nạp."""
    with tempfile.TemporaryDirectory() as t:
        for i, j in enumerate(cac_ban_khai):
            d = Path(t) / f"lv{i}"
            d.mkdir()
            (d / "linh-vuc.json").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
        return so_ghi.nap(Path(t))


def phai_tu_choi(ten, *cac_ban_khai):
    global DAT, TRUOT
    try:
        nop(*cac_ban_khai)
    except so_ghi.LoiBanKhai as e:
        DAT += 1
        print(f"  ĐẠT  từ chối: {ten}")
        print(f"       → {str(e)[:96]}")
        return
    except Exception as e:  # noqa: BLE001
        TRUOT += 1
        print(f"  TRƯỢT {ten}: ném {type(e).__name__} thay vì LoiBanKhai — {e}")
        return
    TRUOT += 1
    print(f"  TRƯỢT {ten}: NHẬN bản khai sai mà không kêu")


def phai_nhan(ten, *cac_ban_khai):
    global DAT, TRUOT
    try:
        ds = nop(*cac_ban_khai)
    except Exception as e:  # noqa: BLE001
        TRUOT += 1
        print(f"  TRƯỢT {ten}: từ chối bản khai ĐÚNG — {e}")
        return
    DAT += 1
    print(f"  ĐẠT  nhận: {ten} ({len(ds)} lĩnh vực)")


print("══ BẢN KHAI ĐÚNG PHẢI ĐƯỢC NHẬN ═══════════════════════════════════════")
phai_nhan("bản khai tối thiểu hợp lệ", hop_le())

print("\n══ HAI TRƯỜNG MÁY ĐO, NGƯỜI KHAI VÀO LÀ SAI ═══════════════════════════")
phai_tu_choi("tự khai trang_thai", hop_le(trang_thai="chay-duoc"))
phai_tu_choi("tự khai bang_chung", hop_le(bang_chung="tôi thấy nó chạy"))

print("\n══ KHUÔN TÊN PHẢI THEO ĐÚNG nhan/quyen.py ═════════════════════════════")
phai_tu_choi("mã có gạch ngang", hop_le(ma="vi-du", cong_cu=["vi-du.x"]))
phai_tu_choi("mã bắt đầu bằng số", hop_le(ma="1vi_du", cong_cu=["1vi_du.x"]))
phai_tu_choi("công cụ không có tiền tố mã", hop_le(cong_cu=["khac.lam_gi_do"]))
phai_tu_choi("công cụ sai khuôn", hop_le(cong_cu=["vi_du.Lam-Gi"]))
phai_tu_choi("không có công cụ nào", hop_le(cong_cu=[]))

print("\n══ ĐƯỜNG DẪN ═════════════════════════════════════════════════════════")
phai_tu_choi("thiếu dấu / đầu", hop_le(duong_dan="vi-du"))
phai_tu_choi("có dấu / cuối", hop_le(duong_dan="/vi-du/"))
phai_tu_choi("hai lĩnh vực trùng đường dẫn",
             hop_le(), hop_le(ma="khac", duong_dan="/vi-du", cong_cu=["khac.x"]))
phai_tu_choi("đường dẫn LỒNG nhau (/a và /a/b)",
             hop_le(duong_dan="/a"), hop_le(ma="khac", duong_dan="/a/b", cong_cu=["khac.x"]))
phai_tu_choi("đường dẫn là TIỀN TỐ CHUỖI (/tro-chuyen và /tro-chuyen-cu)",
             hop_le(duong_dan="/tro-chuyen"),
             hop_le(ma="khac", duong_dan="/tro-chuyen-cu", cong_cu=["khac.x"]))

print("\n══ VA CHẠM KHÁC ══════════════════════════════════════════════════════")
phai_tu_choi("hai lĩnh vực trùng mã",
             hop_le(), hop_le(duong_dan="/khac"))
phai_tu_choi("hai lĩnh vực khai trùng tên công cụ",
             hop_le(), hop_le(ma="khac", duong_dan="/khac", cong_cu=["vi_du.lam_gi_do"]))

print("\n══ TRƯỜNG KHÁC ══════════════════════════════════════════════════════")
phai_tu_choi("loại lạ", hop_le(loai="tuy-y"))
phai_tu_choi("quyền lạ", hop_le(quyen_can=["xoa"]))
phai_tu_choi("biểu tượng nhiều hơn một ký tự", hop_le(bieu_tuong={"chu": "AB", "mau": "#123456"}))
phai_tu_choi("màu sai dạng", hop_le(bieu_tuong={"chu": "V", "mau": "xanh"}))
phai_tu_choi("thiếu trường bắt buộc", {k: v for k, v in hop_le().items() if k != "tom_tat"})

print("\n" + "═" * 72)
print(f"  ĐẠT {DAT} · TRƯỢT {TRUOT}")
if TRUOT:
    print("  KẾT LUẬN: bộ kiểm KHÔNG đáng tin — nó nhận bản khai sai.")
    raise SystemExit(1)
print("  KẾT LUẬN: bộ kiểm từ chối đúng mọi bản khai sai đã thử.")
print("  NHẮC: nó chỉ từ chối được thứ bài thử này biết cách nộp.")
raise SystemExit(0)
