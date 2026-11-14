#!/usr/bin/env python3
"""Đo HTTP và tài nguyên của bản giao diện, không suy ra nghiệp vụ từ HTTP 200."""
import argparse
import json
import ipaddress
import subprocess
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


class TaiNguyen(HTMLParser):
    def __init__(self):
        super().__init__()
        self.duong_dan = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and a.get("src"):
            self.duong_dan.append(a["src"])
        if tag == "link" and a.get("rel") == "stylesheet" and a.get("href"):
            self.duong_dan.append(a["href"])


def tai(goc, duong_dan, host=None, ip_origin=None):
    if ip_origin:
        ip = str(ipaddress.ip_address(ip_origin))
        url = urlsplit(goc)
        if url.scheme not in ("http", "https") or not url.hostname:
            raise ValueError("Gốc HTTP không hợp lệ")
        port = url.port or (443 if url.scheme == "https" else 80)
        if ":" in ip:
            ip = "[" + ip + "]"
        # curl --resolve giữ nguyên SNI và kiểm chứng thư cho tên miền; không dùng -k.
        r = subprocess.run(["curl", "--silent", "--show-error", "--max-time", "12",
                            "--resolve", "%s:%s:%s" % (url.hostname, port, ip),
                            "--write-out", "\n%{http_code}", goc.rstrip("/") + duong_dan],
                           capture_output=True, timeout=16)
        if r.returncode:
            raise RuntimeError("Không đo được origin: " + r.stderr.decode("utf-8", "replace"))
        than, ma = r.stdout.rsplit(b"\n", 1)
        return int(ma), than
    headers = {"User-Agent": "Open-BDSG-Verification/1"}
    if host:
        headers["Host"] = host
    try:
        with urlopen(Request(goc.rstrip("/") + duong_dan, headers=headers), timeout=12) as r:
            return r.status, r.read(4 * 1024 * 1024)
    except HTTPError as e:
        return e.code, b""


def do(goc, docroot, host=None, ip_origin=None):
    docroot = Path(docroot).resolve()
    if not (docroot / "thuc-the.json").is_file():
        raise ValueError("Đầu vào không phải bản giao diện đã đóng gói")
    ds = json.loads((docroot / "cong/so-ghi-linh-vuc.json").read_text(encoding="utf-8"))
    ket_qua = []
    for lv in ds:
        duong = lv["duong_dan"] + "/"
        ma, than = tai(goc, duong, host, ip_origin)
        tep = docroot / duong.lstrip("/") / "index.html"
        bang_chung = ["GET " + duong + " → HTTP " + str(ma)]
        trang_thai = "chua-trien-khai"
        if tep.is_file():
            trang_thai = "hong"
            if ma == 200 and than == tep.read_bytes():
                tai_nguyen = TaiNguyen()
                tai_nguyen.feed(than.decode("utf-8"))
                loi = []
                for duong_tn in tai_nguyen.duong_dan:
                    url = urljoin(goc.rstrip("/") + duong, duong_tn)
                    if urlsplit(url).netloc != urlsplit(goc).netloc:
                        loi.append("Tài nguyên ngoài chưa đo: " + duong_tn)
                        continue
                    ma_tn, than_tn = tai(goc, urlsplit(url).path, host, ip_origin)
                    tep_tn = docroot / urlsplit(url).path.lstrip("/")
                    if ma_tn != 200 or not tep_tn.is_file() or than_tn != tep_tn.read_bytes():
                        loi.append("Tài nguyên không khớp bản đóng gói: " + duong_tn)
                if loi:
                    trang_thai = "trang-trang"
                    bang_chung.extend(loi)
                else:
                    trang_thai = "giao-dien"
                    bang_chung.append("HTML và tài nguyên khớp từng byte với bản đóng gói")
        ket_qua.append({"ma": lv["ma"], "trang_thai": trang_thai, "bang_chung": bang_chung,
                        "canh_bao": ["Chỉ xác nhận giao diện; nghiệp vụ và dữ liệu chưa kết nối."]})
    kiem_bao_ve = []
    for duong in ("/.git/config", "/.env", "/phuc-vu/may_chu.py", "/so-tay/", "/khong-ton-tai"):
        ma, _ = tai(goc, duong, host, ip_origin)
        kiem_bao_ve.append({"duong_dan": duong, "ma": ma, "dat": ma == 404})
    for duong in ("/api/requests", "/mcp"):
        ma_api, _ = tai(goc, duong, host, ip_origin)
        kiem_bao_ve.append({"duong_dan": duong, "ma": ma_api, "dat": ma_api == 401})
    bao_cao = {"do_luc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "goc_da_goi": urlsplit(goc).scheme + "://" + host if host else goc,
               "cach_do": "HTTP trực tiếp origin; so HTML và tài nguyên với tệp đóng gói. --ip-origin giữ kiểm chứng TLS theo tên miền; không đo các biến đổi HTML của CDN.",
               "lien_thong_du_lieu": "chua-cau-hinh", "muc": ket_qua, "kiem_bao_ve": kiem_bao_ve}
    (docroot / "cong/trang-thai-linh-vuc.json").write_text(json.dumps(bao_cao, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dat = all(x["dat"] for x in kiem_bao_ve) and all(x["trang_thai"] in ("giao-dien", "chua-trien-khai") for x in ket_qua)
    print(json.dumps({"dat": dat, "giao_dien": sum(x["trang_thai"] == "giao-dien" for x in ket_qua), "chua_trien_khai": sum(x["trang_thai"] == "chua-trien-khai" for x in ket_qua), "kiem_bao_ve": kiem_bao_ve}, ensure_ascii=False))
    return dat


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--goc", required=True)
    ap.add_argument("--docroot", required=True, type=Path)
    ap.add_argument("--host")
    ap.add_argument("--ip-origin", help="IP origin để bỏ qua CDN; cần curl, vẫn kiểm chứng TLS theo tên miền")
    ns = ap.parse_args()
    raise SystemExit(0 if do(ns.goc, ns.docroot, ns.host, ns.ip_origin) else 1)
