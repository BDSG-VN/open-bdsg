#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Con số thực — đo số tham số đang thật sự chạy, không đọc số ai viết tay.

===============================================================================
VÌ SAO CÓ TỆP NÀY
===============================================================================
Ngày 01/10/2026 BDSG bỏ cách nói "mô hình 30 tỷ tham số". Lý do không phải là
khiêm tốn: **30 tỷ là một cái đích, còn con số đang chạy là một sự thật**, và
hai thứ ấy không được viết cùng một chỗ bằng cùng một giọng.

Cách chống tái phạm không phải là sửa câu chữ, vì câu chữ sẽ lại lệch ở bản
cập nhật sau. Cách chống là **không ai được viết con số bằng tay**: tệp này
đếm từ `parameters()` của mô hình, hoặc từ tệp trọng số `.pt`, rồi phát ra một
JSON. Trang web, README và thẻ mô hình đọc JSON ấy. Muốn đổi con số thì phải
đổi mô hình.

Ba trường bắt buộc đi cùng nhau trong mọi bản phát:
  - `tham_so`        : đếm được, không tính ra
  - `muc_tieu`       : "sinh-van" hay "quyet-dinh-co-kieu" — hai mục tiêu này
                       KHÔNG so được với nhau bằng số tham số
  - `dung_duoc`      : mô hình này đã đạt cổng nghiệm thu chưa. Một bản
                       26,88 triệu tham số quá khớp 5,2 lần vẫn là 26,88 triệu
                       tham số — con số đúng, kết luận sai. Thiếu trường này
                       thì con số thật vẫn dựng nên một lời khai sai.

Chạy:
    python3 mo-hinh/con_so_thuc.py                      # mọi cấu hình trong huan-luyen/cau-hinh
    python3 mo-hinh/con_so_thuc.py --trong-so duong/dan.pt
    python3 mo-hinh/con_so_thuc.py --ra cong/con-so-thuc.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

GOC = Path(__file__).resolve().parent.parent


def _nap_mo_dun():
    """Nạp mo-hinh/ theo đường dẫn: tên thư mục có dấu gạch ngang nên không import thường được."""
    import importlib.util
    import types

    pkg = types.ModuleType("mohinh")
    pkg.__path__ = [str(GOC / "mo-hinh")]
    sys.modules["mohinh"] = pkg

    def nap(ten: str, duong: Path):
        sp = importlib.util.spec_from_file_location(ten, duong)
        m = importlib.util.module_from_spec(sp)
        sys.modules[ten] = m
        sp.loader.exec_module(m)
        return m

    ch = nap("mohinh.cau_hinh", GOC / "mo-hinh" / "cau_hinh.py")
    kt = nap("mohinh.kien_truc", GOC / "mo-hinh" / "kien_truc.py")
    dq = nap("mohinh.dau_quyet_dinh", GOC / "mo-hinh" / "dau_quyet_dinh.py")
    return ch, kt, dq


def do_mot_cau_hinh(duong: Path) -> Dict[str, Any]:
    """Dựng mô hình từ một tệp cấu hình rồi ĐẾM, không tính."""
    import torch  # noqa: F401  (cần cho việc dựng)

    ch, kt, dq = _nap_mo_dun()
    j = json.loads(duong.read_text(encoding="utf-8"))
    b = j.pop("bdsg", {}) or {}
    muc_tieu = b.get("muc_tieu", "sinh-van")

    truong_cfg = {k: v for k, v in j.items()}
    cfg = ch.CauHinhBDSG(**truong_cfg, bdsg_ten=b.get("ten", duong.stem))

    if muc_tieu == "quyet-dinh-co-kieu":
        khai = [
            dq.KhaiDau(ma=d["ma"], loai=d["loai"], nhan=d.get("nhan", []))
            for d in b.get("dau", [])
        ]
        m = dq.BDSGChoQuyetDinh(cfg, khai)
        tham_so_dau: Optional[int] = m.dem_tham_so_dau()
        lech_hieu_chuan = [ma for ma, _ in m.kiem_hieu_chuan()]
    else:
        m = kt.dung_mo_hinh(cfg)
        tham_so_dau = None
        lech_hieu_chuan = []

    return {
        "ten": b.get("ten", duong.stem),
        "tep_cau_hinh": str(duong.relative_to(GOC)),
        "muc_tieu": muc_tieu,
        "tham_so": m.dem_tham_so(),
        "tham_so_hoc_duoc": m.dem_tham_so(chi_hoc_duoc=True),
        "tham_so_dau_ra": tham_so_dau,
        "hinh_dang": {
            "hidden_size": cfg.hidden_size,
            "num_hidden_layers": cfg.num_hidden_layers,
            "vocab_size": cfg.vocab_size,
            "max_position_embeddings": cfg.max_position_embeddings,
        },
        "trong_so_fp32_MiB": round(m.dem_tham_so() * 4 / 2 ** 20, 2),
        "dau_lech_hieu_chuan": lech_hieu_chuan,
        # Cấu hình thường chỉ là kiến trúc, nên `dung_duoc` là null. NHƯNG một
        # cấu hình mô tả bản trọng số ĐÃ huấn luyện thật thì được khai tường
        # minh `dung_duoc` + `vi_sao` trong khối `bdsg` — đó là cách duy nhất
        # để con số quan trọng nhất (số tham số của bản đã huấn luyện) thôi bị
        # gõ tay trong tài liệu.
        "dung_duoc": b.get("dung_duoc"),
        "vi_sao": b.get(
            "vi_sao",
            "đây là số của KIẾN TRÚC; chưa nói gì về việc đã huấn luyện hay đã đạt nghiệm thu",
        ),
        "ngu_lieu_token": b.get("ngu_lieu_token"),
    }


def do_tep_trong_so(duong: Path) -> Dict[str, Any]:
    """Đếm tham số từ một tệp .pt — đếm tensor thật, không dựng lại kiến trúc."""
    import torch

    goi = torch.load(duong, map_location="cpu", weights_only=False)
    tt = goi.get("state_dict", goi) if isinstance(goi, dict) else goi
    if not isinstance(tt, dict):
        raise SystemExit(f"  không đọc được state_dict từ {duong}")

    tensors = {k: v for k, v in tt.items() if hasattr(v, "numel")}
    # Trọng số buộc chung (tie_word_embeddings) chỉ được đếm MỘT lần. Đếm theo
    # id() của storage, vì hai khoá khác nhau có thể trỏ cùng một vùng nhớ —
    # đếm hai lần sẽ thổi con số lên và đó đúng là kiểu sai mà tệp này tồn tại
    # để chặn.
    da_thay = set()
    tong = 0
    for v in tensors.values():
        try:
            khoa = v.untyped_storage().data_ptr()
        except Exception:
            khoa = id(v)
        if khoa in da_thay:
            continue
        da_thay.add(khoa)
        tong += int(v.numel())

    sieu = goi if isinstance(goi, dict) else {}
    return {
        "ten": sieu.get("bdsg_ten") or duong.stem,
        "tep_trong_so": str(duong),
        "muc_tieu": sieu.get("muc_tieu", "chưa ghi trong tệp trọng số"),
        "tham_so": tong,
        "so_tensor": len(tensors),
        "so_vung_nho_phan_biet": len(da_thay),
        "trong_so_fp32_MiB": round(tong * 4 / 2 ** 20, 2),
        "dung_duoc": sieu.get("dung_duoc"),
        "vi_sao": sieu.get(
            "vi_sao",
            "tệp trọng số không tự khai đã đạt nghiệm thu chưa — phải điền khi huấn luyện",
        ),
    }



# ═══════════════════════════════════════════════════════════════════════════
# GHI BẢNG VÀO TÀI LIỆU
# ═══════════════════════════════════════════════════════════════════════════
# Không tài liệu nào của BDSG được gõ số tham số bằng tay. Hàm dưới đây ghi
# bảng vào giữa hai dấu mốc trong tệp Markdown; ngoài hai dấu mốc ấy thì nó
# không sửa gì. Chạy lại được nhiều lần, kết quả như nhau (idempotent).

MOC_BAT_DAU = "<!-- BAT-DAU-CON-SO-THUC"
MOC_KET_THUC = "<!-- KET-THUC-CON-SO-THUC -->"


def dung_bang(muc: List[Dict[str, Any]]) -> str:
    """Bảng Markdown từ kết quả đo. Không nhận số từ bất kỳ đâu khác."""
    hang = [
        "| mô hình | mục tiêu | tham số (đếm thật) | fp32 | dùng được? |",
        "|---|---|---:|---:|---|",
    ]
    for m in sorted(muc, key=lambda x: (x.get("muc_tieu", ""), x.get("tham_so", 0))):
        if "loi" in m:
            hang.append(
                f"| `{m.get('tep_cau_hinh', '?')}` | — | **lỗi đo** | — | {m['loi'][:60]} |"
            )
            continue
        dd = m.get("dung_duoc")
        nhan_dd = {
            None: "chưa huấn luyện — đây là số của kiến trúc",
            True: "đã đạt cổng nghiệm thu",
            False: "**chưa đạt** cổng nghiệm thu",
        }.get(dd, str(dd))
        ts = m.get("tham_so", 0)
        # Số hàng nghìn dùng dấu chấm, số thập phân dùng dấu phẩy — quy ước
        # tiếng Việt. Trộn hai dấu trong cùng một bảng làm "138.03 MiB" đọc
        # thành một trăm ba mươi tám nghìn.
        mib = f"{m.get('trong_so_fp32_MiB', 0):,.2f}".replace(",", "\u00a0").replace(".", ",")
        hang.append(
            f"| `{m.get('ten', '?')}` | {m.get('muc_tieu', '?')} | "
            + f"**{ts:,}**".replace(",", ".")
            + f" | {mib} MiB | {nhan_dd} |"
        )
    return "\n".join(hang)


def ghi_vao_tai_lieu(duong: Path, muc: List[Dict[str, Any]], do_luc: str) -> str:
    """Thay phần giữa hai dấu mốc. Trả về trạng thái: ghi / khong-co-moc / khong-doi."""
    if not duong.exists():
        return "khong-co-tep"
    van = duong.read_text(encoding="utf-8")
    i = van.find(MOC_BAT_DAU)
    j = van.find(MOC_KET_THUC)
    if i < 0 or j < 0 or j < i:
        return "khong-co-moc"
    # Giữ trọn dòng dấu mốc mở (nó có chú thích "DUNG SUA BANG TAY").
    het_moc = van.find("-->", i)
    if het_moc < 0 or het_moc > j:
        return "khong-co-moc"

    # Bảng là HÀM THUẦN của các con số — KHÔNG chèn dấu thời gian vào đây. Chèn
    # vào thì mỗi lần chạy lại sinh một thay đổi giả trong git dù không con số
    # nào đổi, và người xem diff sẽ học cách bỏ qua tệp này. Bản ghi phép đo
    # (kèm `do_luc`) nằm ở cong/con-so-thuc.json.
    than = (
        "\n\n" + dung_bang(muc) + "\n\n"
        + "<sub>Bảng này do máy ghi từ "
        + "[`cong/con-so-thuc.json`](cong/con-so-thuc.json) bằng "
        + "`python3 mo-hinh/con_so_thuc.py --cap-nhat-tai-lieu`. "
        + "Ngày đo ở trường `do_luc` trong tệp ấy. "
        + "Sửa bảng bằng tay sẽ bị ghi đè ở lần chạy sau.</sub>\n\n"
    )
    moi = van[: het_moc + 3] + than + van[j:]
    if moi == van:
        return "khong-doi"
    duong.write_text(moi, encoding="utf-8")
    return "ghi"


def main() -> int:
    ap = argparse.ArgumentParser(description="Đo số tham số đang thật sự chạy.")
    ap.add_argument("--trong-so", type=Path, help="đếm từ một tệp .pt")
    ap.add_argument("--ra", type=Path, help="ghi JSON ra tệp (mặc định in ra màn hình)")
    ap.add_argument(
        "--cap-nhat-tai-lieu",
        action="store_true",
        help="ghi bảng vào README.md và MODEL-CARD.md giữa hai dấu mốc BAT-DAU/KET-THUC-CON-SO-THUC",
    )
    ns = ap.parse_args()

    muc: List[Dict[str, Any]] = []
    if ns.trong_so:
        muc.append(do_tep_trong_so(ns.trong_so))
    else:
        thu_muc = GOC / "huan-luyen" / "cau-hinh"
        for f in sorted(thu_muc.glob("*.json")):
            try:
                muc.append(do_mot_cau_hinh(f))
            except Exception as e:  # noqa: BLE001
                muc.append({"tep_cau_hinh": str(f.relative_to(GOC)), "loi": str(e)})

    ra = {
        "do_luc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cach_do": "đếm từ parameters() / tensor thật, KHÔNG đọc số viết tay",
        "luat": (
            "Không tài liệu nào của BDSG được viết số tham số bằng tay. "
            "README, thẻ mô hình và trang web đọc tệp này."
        ),
        "muc": muc,
    }
    van = json.dumps(ra, ensure_ascii=False, indent=2)
    if ns.ra:
        ns.ra.parent.mkdir(parents=True, exist_ok=True)
        ns.ra.write_text(van + "\n", encoding="utf-8")
        print(f"  đã ghi {ns.ra}  ({len(muc)} mục)")
        for m in muc:
            if "loi" in m:
                print(f"    LỖI {m['tep_cau_hinh']}: {m['loi']}")
            else:
                print(f"    {m['ten']:24s} {m['muc_tieu']:22s} {m['tham_so']:>12,}")
    else:
        print(van)

    if ns.cap_nhat_tai_lieu:
        print("  cập nhật tài liệu:")
        loi = 0
        for ten in ("README.md", "MODEL-CARD.md"):
            tt = ghi_vao_tai_lieu(GOC / ten, muc, ra["do_luc"])
            print(f"    {ten:16s} {tt}")
            if tt in ("khong-co-moc", "khong-co-tep"):
                loi += 1
        if loi:
            # Fail-closed: thiếu dấu mốc nghĩa là tài liệu ĐANG gõ số bằng tay,
            # tức đúng thứ tệp này tồn tại để chặn. Không được im lặng bỏ qua.
            print(
                f"    LỖI: {loi} tệp không có dấu mốc — tài liệu đó vẫn đang gõ số bằng tay"
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
