"""Xuất bộ kỹ năng dùng trên môi trường AI tương thích, không kèm cấu hình riêng."""

import argparse
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "he-dieu-hanh"))
from nhan_su import NhanSu


def export(destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Thư mục đích đã tồn tại; chọn thư mục mới để giữ gói cũ")
    registry = NhanSu()
    destination.mkdir(parents=True)
    manifest = {
        "version": registry.version,
        "skill_count": len(registry.skills) + 1,
        "specialist_count": len(registry.skills),
        "packages": [],
    }
    for format_id in ("portable", "codex", "claude"):
        result = registry.export_bundle({"format": format_id})
        (destination / result["filename"]).write_bytes(
            base64.b64decode(result["content_base64"])
        )
        manifest["packages"].append(
            {k: v for k, v in result.items() if k != "content_base64"}
        )
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True)
    result = export(parser.parse_args().destination)
    print(
        json.dumps(
            {
                "version": result["version"],
                "skills": result["skill_count"],
                "packages": len(result["packages"]),
            }
        )
    )
