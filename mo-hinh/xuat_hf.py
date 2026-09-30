#!/usr/bin/env python3
"""
XUAT MO HINH BDSG RA DINH DANG CONG CU SUY LUAN DOC DUOC.

═══ VI SAO TEP NAY TON TAI ═══

Muc tieu cua du an, dat ra ngay 26/09/2026: nguoi dung TAI MO HINH VE MAY CA NHAN
va chay duoc bang cong cu san co, khong can khoa API cua ben thu ba.

Giua mo hinh trong `kien_truc.py` va muc tieu ay co mot khoang trong. Cong cu suy
luan cuc bo pho bien nhat doc dinh dang GGUF, va bo chuyen doi sang GGUF KHONG doc
mot kien truc tuy y: no tra mot bang dang ky theo truong `architectures` trong
`config.json`, roi doi tung ten tensor theo ten ma kien truc do quy dinh. Mot kien
truc la se bi tu choi thang, khong chuyen duoc.

Nghia la: **neu khong co tep nay, mo hinh huan luyen xong van khong toi duoc may
nguoi dung.** Va cai hong ay chi lo ra o buoc cuoi cung, sau khi da tra tien GPU.

═══ DAY KHONG PHAI LA KHAI NHAN TAC GIA ═══

Truong `architectures` la khai bao ve CACH SAP XEP TRONG SO, khong phai khai bao ve
ai viet ma. No noi "trong so cua toi nam theo bo cuc da biet nay" de cong cu khac
doc duoc. Ma trong kho nay do BDSG viet; bo cuc trong so thi co y lam cho trung voi
mot bo cuc pho bien, vi do la dieu kien de nguoi dung chay duoc.

Doi lai, do la mot RANG BUOC THAT: moi lan ai do dinh them mot khoi "sang tao" vao
kien truc — mot kieu chuan hoa khac, mot cach ma hoa vi tri khac, mot cong phi tuyen
khac — hay hoi truoc: bo chuyen doi co doc duoc khong? Neu khong, cai gia khong phai
mot ham phai viet them, ma la nguoi dung cuoi khong chay duoc gi.

═══ BA CHO DE HONG AM THAM, DA KIEM O CUOI TEP ═══

1. TEN TENSOR. Sai ten thi bo chuyen doi bao thieu tensor — on, vi no bao.
2. QUY UOC ROPE. Sai quy uoc thi KHONG AI BAO GI CA: mo hinh van nap, van sinh chu,
   chi la sinh rac. `kien_truc.quay_nua` ghep HAI NUA (i, i+d/2), dung quy uoc ma
   bo cuc dich gia dinh. Doi quy uoc ay la lam hong moi trong so da huan luyen.
3. BUOC TRONG SO (tie_word_embeddings). Khi buoc, khong co tensor `lm_head.weight`
   rieng. Ghi thua mot ban sao thi tep phinh gap doi phan nhung tu; ghi thieu khi
   KHONG buoc thi mo hinh mat hoan toan lop chieu ra.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Dict, Tuple

import torch


# ──────────────────────────────────────────────────────────────────────────
# Bang doi ten: ten cua BDSG  ->  ten ma bo cuc dich quy dinh
#
# Bang nay la HOP DONG. Doi mot dong o day mà không đổi `kien_truc.py` theo,
# hoac nguoc lai, se cho ra mot tep xuat trong hop le nhung sai. Phep kiem
# `doi_chieu_ten()` o cuoi tep chan dung truong hop ay.
# ──────────────────────────────────────────────────────────────────────────

TEN_CHUNG = {
    "embed_tokens.weight": "model.embed_tokens.weight",
    "norm.weight": "model.norm.weight",
}

TEN_THEO_LOP = {
    "chuan_truoc_chu_y.weight": "input_layernorm.weight",
    "chuan_truoc_ffn.weight": "post_attention_layernorm.weight",
    "chu_y.q_proj.weight": "self_attn.q_proj.weight",
    "chu_y.k_proj.weight": "self_attn.k_proj.weight",
    "chu_y.v_proj.weight": "self_attn.v_proj.weight",
    "chu_y.o_proj.weight": "self_attn.o_proj.weight",
    "ffn.cong_proj.weight": "mlp.gate_proj.weight",
    "ffn.len_proj.weight": "mlp.up_proj.weight",
    "ffn.xuong_proj.weight": "mlp.down_proj.weight",
}


def doi_ten(ten_bdsg: str) -> str:
    """Doi mot ten tham so cua BDSG sang ten cua bo cuc dich. Nem loi neu khong biet."""
    if ten_bdsg in TEN_CHUNG:
        return TEN_CHUNG[ten_bdsg]
    if ten_bdsg.startswith("layers."):
        phan = ten_bdsg.split(".", 2)
        if len(phan) == 3 and phan[1].isdigit():
            duoi = phan[2]
            if duoi in TEN_THEO_LOP:
                return f"model.layers.{phan[1]}.{TEN_THEO_LOP[duoi]}"
    raise KeyError(
        f"khong biet doi ten tham so {ten_bdsg!r}. Kien truc da doi ma bang doi ten "
        f"chua doi theo — sua TEN_CHUNG hoac TEN_THEO_LOP trong xuat_hf.py."
    )


def dung_config(cfg) -> Dict[str, object]:
    """
    Dung noi dung `config.json` cho bo chuyen doi.

    Moi truong duoi day deu duoc bo chuyen doi DOC THAT, khong phai trang tri:
    thieu mot truong thi no hoac bao loi, hoac lang le dung mac dinh sai.
    """
    return {
        # Khai bao BO CUC TRONG SO — xem khoi chu thich dau tep.
        "architectures": ["LlamaForCausalLM"],
        "model_type": "llama",
        "hidden_size": cfg.hidden_size,
        "num_hidden_layers": cfg.num_hidden_layers,
        "num_attention_heads": cfg.num_attention_heads,
        "num_key_value_heads": cfg.num_key_value_heads,
        "head_dim": cfg.chieu_q,
        "intermediate_size": cfg.intermediate_size,
        "vocab_size": cfg.vocab_size,
        "hidden_act": cfg.hidden_act,
        "max_position_embeddings": cfg.max_position_embeddings,
        "rms_norm_eps": cfg.rms_norm_eps,
        "rope_theta": cfg.rope_theta,
        "tie_word_embeddings": cfg.tie_word_embeddings,
        "bos_token_id": cfg.bos_token_id,
        "eos_token_id": cfg.eos_token_id,
        "pad_token_id": cfg.pad_token_id,
        "attention_bias": False,
        "mlp_bias": False,
        "torch_dtype": "float32",
        # Truong rieng cua BDSG mang tien to, de khong va vao truong nao bo chuyen
        # doi doc. Bo chuyen doi bo qua truong la; nguoi doc thi biet tep tu dau ra.
        "bdsg_nguon": "Open BDSG",
        "bdsg_ten": getattr(cfg, "bdsg_ten", ""),
        "bdsg_ghi_chu": getattr(cfg, "bdsg_ghi_chu", ""),
    }


def dung_trong_so(mo_hinh) -> Tuple[Dict[str, torch.Tensor], list]:
    """Doi ten toan bo trong so. Tra (bang trong so, danh sach canh bao)."""
    ra: Dict[str, torch.Tensor] = {}
    canh_bao = []
    for ten, tham_so in mo_hinh.named_parameters():
        ra[doi_ten(ten)] = tham_so.detach().cpu().contiguous()

    buoc = bool(getattr(mo_hinh.cfg, "tie_word_embeddings", False))
    if not buoc and "lm_head.weight" not in ra:
        # Khong buoc ma thieu lop chieu ra => mo hinh xuat ra se khong sinh duoc gi.
        canh_bao.append(
            "tie_word_embeddings=False nhung khong tim thay trong so lop chieu ra; "
            "mo hinh xuat ra se thieu lm_head."
        )
    if buoc and "lm_head.weight" in ra:
        # Buoc ma van ghi ban sao => tep phinh them dung bang phan nhung tu.
        del ra["lm_head.weight"]
        canh_bao.append("da bo ban sao lm_head.weight vi trong so duoc buoc.")
    return ra, canh_bao


def xuat(mo_hinh, thu_muc: str) -> Dict[str, object]:
    """Ghi config.json + model.safetensors vao `thu_muc`. Tra bang so do."""
    from safetensors.torch import save_file

    d = pathlib.Path(thu_muc)
    d.mkdir(parents=True, exist_ok=True)

    cfg_json = dung_config(mo_hinh.cfg)
    (d / "config.json").write_text(
        json.dumps(cfg_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    trong_so, canh_bao = dung_trong_so(mo_hinh)
    save_file(trong_so, str(d / "model.safetensors"), metadata={"format": "pt"})

    so_tham_so = sum(t.numel() for t in trong_so.values())
    return {
        "thu_muc": str(d),
        "so_tensor": len(trong_so),
        "so_tham_so_ghi": so_tham_so,
        "byte_safetensors": (d / "model.safetensors").stat().st_size,
        "canh_bao": canh_bao,
    }


# ══════════════════════════════════════════════════════════════════════════
# Tu kiem — ba cho de hong am tham
# ══════════════════════════════════════════════════════════════════════════


def _nap_goi():
    import importlib.util

    g = pathlib.Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "mh_noi_bo", g / "__init__.py", submodule_search_locations=[str(g)]
    )
    mh = importlib.util.module_from_spec(spec)
    sys.modules["mh_noi_bo"] = mh
    spec.loader.exec_module(mh)
    return mh


def tu_kiem() -> int:
    import tempfile

    mh = _nap_goi()
    dat, hong = [], []

    def ghi(ten: str, ok: bool, chi_tiet: str) -> None:
        (dat if ok else hong).append((ten, chi_tiet))

    # ── 1. Moi tham so deu doi duoc ten, va khong hai tham so cung mot ten ──
    cfg = mh.cau_hinh_ti_hon()
    m = mh.BDSGChoNgonNgu(cfg)
    ten_goc = [n for n, _ in m.named_parameters()]
    try:
        ten_moi = [doi_ten(n) for n in ten_goc]
        trung = len(ten_moi) - len(set(ten_moi))
        ghi(
            "1. Moi tham so doi duoc ten, khong ten nao trung",
            trung == 0,
            f"{len(ten_goc)} tham so doi het; {trung} ten trung",
        )
    except KeyError as loi:
        ghi("1. Moi tham so doi duoc ten, khong ten nao trung", False, str(loi))

    # ── 2. Ten sai bi CHAN, khong lang le bo qua ──
    #     Mot bang doi ten "de dai" se bo sot tham so ma khong bao gi.
    bi_chan = False
    try:
        doi_ten("layers.0.mot_khoi_moi_ai_do_vua_them.weight")
    except KeyError:
        bi_chan = True
    ghi(
        "2. Ten la bi CHAN chu khong bi bo qua",
        bi_chan,
        "mot ten khong co trong bang lam ham nem loi — dung",
    )

    # ── 3. config.json co du truong bo chuyen doi DOC THAT ──
    c = dung_config(cfg)
    can = [
        "architectures", "model_type", "hidden_size", "num_hidden_layers",
        "num_attention_heads", "num_key_value_heads", "intermediate_size",
        "vocab_size", "rms_norm_eps", "rope_theta", "tie_word_embeddings",
    ]
    thieu = [k for k in can if k not in c]
    ghi(
        "3. config.json du truong bat buoc",
        not thieu and c["architectures"] == ["LlamaForCausalLM"],
        f"thieu: {thieu or 'khong'}; architectures={c['architectures']}",
    )

    # ── 4. Buoc trong so: KHONG duoc ghi ban sao lop chieu ra ──
    ts_buoc, _ = dung_trong_so(m)
    ghi(
        "4. Trong so buoc thi khong ghi ban sao lop chieu ra",
        "lm_head.weight" not in ts_buoc,
        f"tie_word_embeddings={cfg.tie_word_embeddings}; "
        f"co lm_head trong tep xuat: {'lm_head.weight' in ts_buoc}",
    )

    # ── 5. So tham so ghi ra khop so tham so mo hinh dem duoc ──
    dem_mo_hinh = sum(p.numel() for p in m.parameters())
    dem_ghi = sum(t.numel() for t in ts_buoc.values())
    ghi(
        "5. So tham so ghi ra == so tham so mo hinh",
        dem_ghi == dem_mo_hinh,
        f"mo hinh {dem_mo_hinh:,} · ghi ra {dem_ghi:,}",
    )

    # ── 6. Quy uoc RoPE la GHEP HAI NUA, khong phai ghep ke nhau ──
    #     Day la cho hong AM THAM nhat: sai quy uoc thi mo hinh van nap, van sinh
    #     chu, chi la sinh rac. Kiem bang chinh dinh nghia: quay_nua([a,b,c,d])
    #     phai ra [-c,-d,a,b] (hai nua), KHONG phai [-b,a,-d,c] (ke nhau).
    x = torch.tensor([[1.0, 2.0, 3.0, 4.0]])
    ra = mh.quay_nua(x)[0].tolist()
    hai_nua = ra == [-3.0, -4.0, 1.0, 2.0]
    ke_nhau = ra == [-2.0, 1.0, -4.0, 3.0]
    ghi(
        "6. Quy uoc RoPE la GHEP HAI NUA (khop bo cuc dich)",
        hai_nua and not ke_nhau,
        f"quay_nua([1,2,3,4]) = {ra} "
        f"({'hai nua — dung' if hai_nua else 'ke nhau — SAI, se sinh rac'})",
    )

    # ── 7. Xuat that ra dia roi doc lai ──
    with tempfile.TemporaryDirectory() as tmp:
        try:
            bao = xuat(m, tmp)
            from safetensors import safe_open

            with safe_open(str(pathlib.Path(tmp) / "model.safetensors"), framework="pt") as f:
                ten_trong_tep = set(f.keys())
            doc_lai = json.loads((pathlib.Path(tmp) / "config.json").read_text(encoding="utf-8"))
            ok = (
                ten_trong_tep == set(ts_buoc.keys())
                and doc_lai["architectures"] == ["LlamaForCausalLM"]
                and bao["so_tensor"] == len(ts_buoc)
            )
            ghi(
                "7. Xuat ra dia roi doc lai khong mat gi",
                ok,
                f"{bao['so_tensor']} tensor · {bao['byte_safetensors']:,} byte; "
                f"canh bao: {bao['canh_bao'] or 'khong'}",
            )
        except Exception as loi:  # noqa: BLE001
            ghi("7. Xuat ra dia roi doc lai khong mat gi", False, f"{type(loi).__name__}: {loi}")

    # ── In ket qua ──
    print("TU KIEM xuat_hf")
    print("-" * 78)
    for ten, ct in dat:
        print(f"  [DAT ] {ten}  — {ct}")
    for ten, ct in hong:
        print(f"  [HONG] {ten}  — {ct}")
    print("-" * 78)
    print(f"KET QUA: {len(dat)}/{len(dat) + len(hong)} DAT.")
    print()
    print("Nghia la gi: tep xuat ra DUNG HINH DANG de bo chuyen doi doc.")
    print("Nghia la gi KHONG: bai nay CHUA chay bo chuyen doi that, va CHUA chay mo hinh")
    print("sau chuyen doi. Hai buoc ay can cai cong cu ngoai, chua lam (26/09/2026).")
    return 0 if not hong else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Xuat mo hinh BDSG ra dinh dang cong cu suy luan doc duoc.")
    p.add_argument("--tu-kiem", action="store_true", help="chay bai tu kiem, khong can trong so")
    p.add_argument("--cau-hinh", help="duong dan tep cau hinh JSON")
    p.add_argument("--diem-dung", help="duong dan diem dung .pt de nap trong so")
    p.add_argument("--ra", help="thu muc ghi ket qua")
    t = p.parse_args()

    if t.tu_kiem:
        return tu_kiem()

    if not t.cau_hinh or not t.ra:
        p.error("can --cau-hinh va --ra (hoac dung --tu-kiem)")

    mh = _nap_goi()
    cfg = mh.CauHinhBDSG.tu_json(pathlib.Path(t.cau_hinh).read_text(encoding="utf-8"))
    m = mh.BDSGChoNgonNgu(cfg)
    if t.diem_dung:
        goi = torch.load(t.diem_dung, map_location="cpu", weights_only=False)
        # Diem dung cua bo huan luyen boc trong so trong khoa `trong_so`, canh
        # `toi_uu`, `trang_thai`, `cau_hinh`, `ngau_nhien`. Nhan ca dang boc lan
        # dang phang — nhung KHONG doan mo ho: neu khong tim thay thi noi ro, chu
        # khong nap mot phan roi xuat ra mot tep thieu trong so ma van hop le.
        if isinstance(goi, dict) and "trong_so" in goi:
            trong_so = goi["trong_so"]
            b = goi.get("trang_thai", {})
            print(f"da nap trong so tu {t.diem_dung} (buoc {b.get('buoc_toan_cuc', '?')})")
        elif isinstance(goi, dict) and all(isinstance(v, torch.Tensor) for v in goi.values()):
            trong_so = goi
            print(f"da nap trong so tu {t.diem_dung} (dang phang)")
        else:
            raise SystemExit(
                f"khong tim thay trong so trong {t.diem_dung}. "
                f"Khoa cap cao: {list(goi.keys()) if isinstance(goi, dict) else type(goi)}"
            )
        m.load_state_dict(trong_so)
    else:
        print("KHONG co --diem-dung: dang xuat trong so KHOI TAO NGAU NHIEN.")
        print("Tep ra se hop le ve hinh dang nhung vo nghia ve noi dung.")

    bao = xuat(m, t.ra)
    print(json.dumps(bao, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
