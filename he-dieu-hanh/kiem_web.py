"""Đo HTTP công khai theo danh mục; không suy diễn đăng nhập hoặc kết nối dữ liệu."""
import argparse
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def kiem(url):
    try:
        with urlopen(Request(url, headers={"User-Agent": "Open-BDSG-Public-Check/0.2"}), timeout=10) as r:
            code = r.status
    except HTTPError as e:
        code = e.code
    except Exception:
        return {"state": "khong-phan-hoi", "http_status": None}
    return {"state": "co-phan-hoi" if 200 <= code < 400 else "can-dang-nhap" if code == 401 else "gioi-han-truy-cap" if code == 403 else "khong-phan-hoi", "http_status": code}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ra", type=Path, required=True)
    args = ap.parse_args()
    os.umask(0o077)
    products = json.loads((Path(__file__).resolve().parents[1] / "nen-tang/danh-muc.json").read_text(encoding="utf-8-sig"))["products"]
    urls = list(dict.fromkeys(p["url"] for p in products))
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = dict(zip(urls, pool.map(kiem, urls)))
    output = {"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "checks": {p["id"]: results[p["url"]] for p in products}}
    temporary = args.ra.with_suffix(".tmp")
    temporary.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, args.ra)
    print(json.dumps({"products": len(products), "unique_urls": len(urls), "states": {s: sum(x["state"] == s for x in output["checks"].values()) for s in sorted({x["state"] for x in output["checks"].values()})}}))
