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
        # Cấu hình chỉ là kiến trúc. Nó KHÔNG nói mô hình đã huấn luyện xong
        # hay đã đạt cổng nghiệm thu — nên trường này luôn là null ở đây, và
        # chỉ tệp trọng số mới điền được nó.
        "dung_duoc": None,
        "vi_sao": "đây là số của KIẾN TRÚC; chưa nói gì về việc đã huấn luyện hay đã đạt nghiệm thu",
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Đo số tham số đang thật sự chạy.")
    ap.add_argument("--trong-so", type=Path, help="đếm từ một tệp .pt")
    ap.add_argument("--ra", type=Path, help="ghi JSON ra tệp (mặc định in ra màn hình)")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
