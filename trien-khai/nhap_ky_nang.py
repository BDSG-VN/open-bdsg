"""Tải văn bản kỹ năng đã chọn ở commit cố định; không chạy mã từ nhà cung cấp."""

import argparse
import hashlib
import json
import re
import ssl
from pathlib import Path, PurePosixPath
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download(selection, destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Thư mục đích đã có; không ghi đè gói đã duyệt")
    records = json.loads(Path(selection).read_text(encoding="utf-8"))["repositories"]
    if not 1 <= len(records) <= 50:
        raise ValueError("Chọn tối đa năm mươi nguồn đã rà soát")
    opener = build_opener(
        NoRedirect(), HTTPSHandler(context=ssl.create_default_context())
    )
    lock = {
        "schema": 1,
        "reviewed_at": "2026-11-16",
        "execution_enabled": False,
        "repositories": [],
    }
    destination.mkdir(parents=True)
    for entry in records:
        repo, commit, paths = entry["repository"], entry["commit"], entry["files"]
        if (
            not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
            or not re.fullmatch(r"[a-f0-9]{40}", commit)
            or not isinstance(paths, list)
            or not 1 <= len(paths) <= 100
            or len(set(paths)) != len(paths)
            or entry["license"] not in ("MIT", "Apache-2.0", "BSD-3-Clause")
        ):
            raise ValueError("Nguồn tải không đúng tập đã duyệt")
        output = {k: entry[k] for k in ("repository", "commit", "stars", "license")}
        output["files"] = []
        for name in paths:
            path = PurePosixPath(name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in name
                or not re.fullmatch(r"[A-Za-z0-9_./-]+", name)
                or (
                    path.suffix.lower() not in (".md", ".txt")
                    and path.name not in ("LICENSE", "NOTICE")
                )
            ):
                raise ValueError("Chỉ nhập văn bản kỹ năng và giấy phép")
            url = (
                "https://raw.githubusercontent.com/" + repo + "/" + commit + "/" + name
            )
            request = Request(url, headers={"User-Agent": "BDSG-reviewed-skills/1"})
            with opener.open(request, timeout=30) as response:
                if response.status != 200:
                    raise ValueError("Nguồn không trả văn bản thành công")
                raw = response.read(262145)
            if len(raw) > 262144 or b"\0" in raw:
                raise ValueError("Tệp nguồn không phải văn bản trong giới hạn")
            raw.decode("utf-8")
            target = destination / repo.replace("/", "--") / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            output["files"].append(
                {
                    "path": name,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                    "url": url,
                }
            )
        lock["repositories"].append(output)
    (destination / "sources.lock.json").write_text(
        json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return lock


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    result = download(args.selection, args.destination)
    print(
        json.dumps(
            {
                "repositories": len(result["repositories"]),
                "files": sum(len(r["files"]) for r in result["repositories"]),
                "execution_enabled": False,
            }
        )
    )
