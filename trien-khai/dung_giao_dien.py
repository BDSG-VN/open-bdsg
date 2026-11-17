#!/usr/bin/env python3
"""Đóng gói giao diện hiện có; không đưa mã máy chủ hoặc dữ liệu nội bộ lên web."""
import argparse
import html
import json
import re
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
TRANG = {"os": "trang-openos", "tac-nhan": "trang-agent", "web3": "trang-web3"}


def doc_tep(duong_dan, nhi_phan=False):
    p = GOC / duong_dan
    if p.is_symlink() or not p.is_file():
        raise ValueError("Tệp nguồn không phải tệp thường: " + str(p))
    return p.read_bytes() if nhi_phan else p.read_text(encoding="utf-8")


def dung(cau_hinh, thu_muc_ra):
    cau_hinh = dict(cau_hinh)
    for ten in ("ma", "ten", "ten_mien", "mo_ta", "thong_bao"):
        if not isinstance(cau_hinh.get(ten), str) or not cau_hinh[ten].strip():
            raise ValueError("Thiếu trường cấu hình: " + ten)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", cau_hinh["ma"]):
        raise ValueError("Mã thực thể không hợp lệ")
    if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", cau_hinh["ten_mien"]):
        raise ValueError("Tên miền không hợp lệ")
    dich = Path(thu_muc_ra).resolve()
    if dich.exists():
        raise ValueError("Chọn thư mục đầu ra mới, không ghi đè bản đang phục vụ")
    if dich == GOC or GOC in dich.parents:
        raise ValueError("Bản đóng gói phải nằm ngoài kho mã nguồn")
    dich.mkdir(parents=True)

    def ghi(ten, noi_dung):
        p = dich / ten
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(noi_dung, bytes):
            p.write_bytes(noi_dung)
        else:
            p.write_text(noi_dung, encoding="utf-8")

    goc_url = "https://" + cau_hinh["ten_mien"]
    dau = doc_tep("khong-gian/index.html")
    dau = dau.replace("<title>Bảng điều khiển — Open BDSG</title>",
                       "<title>" + html.escape(cau_hinh["ten"]) + " — Open BDSG</title>")
    dau = dau.replace("<span class=\"ten\">Open BDSG</span>",
                       '<span class="ten">' + html.escape(cau_hinh["ten"]) + "</span>")
    dau = dau.replace("</head>", '<link rel="canonical" href="' + goc_url + '/">\n</head>')
    ghi("index.html", dau)
    ghi("workspace.html", dau.replace('<link rel="canonical" href="' + goc_url + '/">', ''))
    for ten in ("may-chu.js", "may-chu.css", "he-dieu-hanh-state.js", "he-dieu-hanh.js", "bao-ve-phien.js", "ios.css", "trinh-duyet.html", "trinh-duyet.js", "trinh-duyet.css", "ung-dung.webmanifest"):
        ghi(ten, doc_tep("khong-gian/" + ten))
    ghi("portal.css", doc_tep("khong-gian/giao-dien.css"))
    ghi("portal.js", doc_tep("khong-gian/ung-dung.js"))
    ghi("cong-viec.css", doc_tep("khong-gian/cong-viec.css"))
    ghi("cong-viec.js", doc_tep("khong-gian/cong-viec.js"))
    ghi("nhan-su.js", doc_tep("khong-gian/nhan-su.js"))
    ghi("nhan-su.css", doc_tep("khong-gian/nhan-su.css"))
    ghi("trung-tam-ai.js", doc_tep("khong-gian/trung-tam-ai.js"))
    ghi("trung-tam-ai.css", doc_tep("khong-gian/trung-tam-ai.css"))
    ghi("ket-noi.js", doc_tep("khong-gian/ket-noi.js"))
    ghi("ket-noi.css", doc_tep("khong-gian/ket-noi.css"))
    ghi("tich-hop-vn.js", doc_tep("khong-gian/tich-hop-vn.js"))
    ghi("tich-hop-vn.css", doc_tep("khong-gian/tich-hop-vn.css"))
    ghi("du-an.js", doc_tep("khong-gian/du-an.js"))
    ghi("du-an.css", doc_tep("khong-gian/du-an.css"))
    ghi("van-phong.js", doc_tep("khong-gian/van-phong.js"))
    ghi("van-phong.css", doc_tep("khong-gian/van-phong.css"))
    for ten in ("soan-thao.html", "soan-thao.js", "soan-thao.css", "google-picker.html", "google-picker.js"):
        ghi(ten, doc_tep("khong-gian/" + ten))
    ghi("studio.js", doc_tep("khong-gian/studio.js"))
    ghi("studio.css", doc_tep("khong-gian/studio.css"))
    ghi("ho-tro.js", doc_tep("khong-gian/ho-tro.js"))
    ghi("ho-tro.css", doc_tep("khong-gian/ho-tro.css"))
    ghi("dien-mao.css", doc_tep("khong-gian/dien-mao.css"))
    for ten_font in ("lora-latin.woff2", "lora-vietnamese.woff2"):
        ghi("fonts/" + ten_font, doc_tep("khong-gian/fonts/" + ten_font, nhi_phan=True))
    ghi("fonts/OFL-Lora.txt", doc_tep("khong-gian/fonts/OFL-Lora.txt"))
    ghi("bdsg-mark.svg", doc_tep("khong-gian/bdsg-mark.svg"))
    ghi("bang-dieu-khien.js", doc_tep("bang-dieu-khien/bang-dieu-khien.js"))
    # Chỉ xuất các trường công khai đã chọn, không chép cấu hình tuỳ ý vào docroot.
    cong_khai = {k: cau_hinh[k] for k in ("ma", "ten", "ten_mien", "mo_ta", "thong_bao")}
    ghi("thuc-the.json", json.dumps(cong_khai, ensure_ascii=False, indent=2) + "\n")
    ghi("cong/so-ghi-linh-vuc.json", doc_tep("cong/so-ghi-linh-vuc.json"))
    muc = json.loads(doc_tep("cong/so-ghi-linh-vuc.json"))
    ghi("cong/trang-thai-linh-vuc.json", json.dumps({"do_luc": None, "goc_da_goi": None,
        "muc": [{"ma": m["ma"], "trang_thai": "chua-do"} for m in muc]}, ensure_ascii=False, indent=2))

    quay_lai = '<nav style="padding:12px 20px;border-bottom:1px solid #e3e8ed"><a href="/">← ' + html.escape(cau_hinh["ten"]) + "</a></nav>"
    for tuyen, nguon in TRANG.items():
        trang = doc_tep(nguon + "/index.html")
        trang = re.sub(r'^.*<link[^>]+(?:fonts\.googleapis|fonts\.gstatic)[^>]*>.*\n?', '', trang, flags=re.M)
        for ten_mien, duong_dan in (("openos.bdsg.vn", "os"), ("agent.bdsg.vn", "tac-nhan"), ("web3.bdsg.vn", "web3")):
            trang = trang.replace("https://" + ten_mien + "/", goc_url + "/" + duong_dan + "/")
        trang = trang.replace("<body>", "<body>\n" + quay_lai, 1)
        ghi(tuyen + "/index.html", trang)

    trang_chat = doc_tep("chat/index.html")
    thong_bao = '<aside role="status" style="padding:12px 20px;background:#fff4df;color:#4c3500">Giao diện xem trước — chưa kết nối đăng nhập và mô hình. Chưa gửi được câu hỏi. <a href="/">Về bảng điều khiển</a></aside>'
    trang_chat = trang_chat.replace("<body>", "<body>\n" + thong_bao, 1)
    trang_chat = trang_chat.replace('<script src="/chat.js" type="module"></script>', '<script src="/xem-truoc.js" type="module"></script>')
    ghi("tro-chuyen/index.html", trang_chat)
    ghi("giao-dien.css", doc_tep("chat/giao-dien.css"))
    ghi("xem-truoc.js", "document.querySelectorAll('textarea,input,button').forEach(function(e){e.disabled=true;});\n")
    ghi("chua-ket-noi.html", '<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Chưa kết nối</title><body style="font-family:system-ui;max-width:680px;margin:12vh auto;padding:24px"><h1>Nền tảng chưa kết nối</h1><p>Phần nghiệp vụ này chưa được triển khai trên thực thể hiện tại.</p><a href="/">Về bảng điều khiển</a></body></html>')
    ghi("404.html", '<!doctype html><html lang="vi"><meta charset="utf-8"><title>Không tìm thấy</title><h1>Không tìm thấy trang</h1><a href="/">Về bảng điều khiển</a></html>')
    ghi("robots.txt", "User-agent: *\nDisallow: /\n")
    return dich


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cau-hinh", type=Path, required=True)
    ap.add_argument("--ra", type=Path, required=True)
    ns = ap.parse_args()
    print(dung(json.loads(ns.cau_hinh.read_text(encoding="utf-8")), ns.ra))
