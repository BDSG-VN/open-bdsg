"""Hồ sơ chuyên trách theo nền tảng; không chia sẻ hội thoại hoặc cấp quyền ngầm."""

import copy
import json
from pathlib import Path


class BoNaoTroLy:
    def __init__(self, products):
        path = Path(__file__).resolve().parents[1] / "nen-tang/bo-nao-tro-ly.json"
        records = json.loads(path.read_text(encoding="utf-8"))["profiles"]
        by_platform = {p["platform_id"]: p for p in records}
        if (
            len(by_platform) != len(records)
            or len({p["brain_id"] for p in records}) != len(records)
            or len({p["id"] for p in records}) != len(records)
        ):
            raise ValueError(
                "Hồ sơ trợ lý phải có nền tảng, danh tính và bộ não duy nhất"
            )
        self.profiles = {}
        for product in products:
            profile = by_platform.get(product["id"])
            if not profile:
                raise ValueError("Nền tảng chưa có hồ sơ trợ lý chuyên trách")
            if (
                profile["tools"] != {"read": [], "write": []}
                or profile["model_state"] != "chua-cau-hinh"
            ):
                raise ValueError(
                    "Hồ sơ công khai không được tự bật mô hình hoặc công cụ"
                )
            self.profiles[profile["id"]] = {
                "id": profile["id"],
                "platform_id": product["id"],
                "name": "Trợ lý " + product["name"],
                "brain_id": profile["brain_id"],
                "group": product.get("group", "BDSG"),
                "description": product["purpose"],
                "platform": product,
                "brain": profile,
            }

    def catalogue(self):
        return [
            {k: v for k, v in p.items() if k not in ("brain", "platform")}
            for p in self.profiles.values()
        ]

    def detail(self, identifier):
        if not isinstance(identifier, str) or identifier not in self.profiles:
            raise ValueError("Không tìm thấy trợ lý của nền tảng này")
        return copy.deepcopy(self.profiles[identifier])
