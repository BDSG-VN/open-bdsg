"""Danh mục nhân sự từ bộ kỹ năng đã duyệt; tên vai trò không tự cấp quyền."""

import copy
import hashlib
import json
import re
from pathlib import Path


class NhanSu:
    def __init__(self, root=None):
        self.root = Path(
            root or Path(__file__).resolve().parents[1] / "nhan-su"
        ).resolve()
        manifest = json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))
        if manifest.get("schema") != 1 or manifest.get("locale") != "vi-VN":
            raise ValueError("Bộ kỹ năng chưa đúng chuẩn Việt Nam")
        self.version = manifest["version"]
        self.skills = {}
        for item in manifest["skills"]:
            identifier = item.get("id")
            if (
                not isinstance(identifier, str)
                or not re.fullmatch(r"[a-z][a-z0-9-]{2,62}", identifier)
                or identifier in self.skills
            ):
                raise ValueError("Mã nhân sự không hợp lệ hoặc bị lặp")
            path = self.root / "skills" / identifier / "SKILL.md"
            if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                raise ValueError("Kỹ năng không được trỏ ra ngoài danh mục")
            raw = path.read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            if len(raw) > 32768 or checksum != item.get("sha256"):
                raise ValueError("Nội dung kỹ năng không khớp bản đã duyệt")
            text = raw.decode("utf-8")
            if (
                not text.startswith("---\n")
                or "\nname: " + identifier + "\n" not in text
            ):
                raise ValueError("Kỹ năng cần tên frontmatter khớp thư mục")
            if not isinstance(item.get("sources"), list) or not item["sources"]:
                raise ValueError("Kỹ năng cần nguồn và nguồn gốc biên soạn")
            self.skills[identifier] = {**item, "instructions": text}
        if not self.skills or len(self.skills) > 100:
            raise ValueError("Danh mục nhân sự ngoài giới hạn")

    def catalogue(self):
        return {
            "version": self.version,
            "locale": "vi-VN",
            "timezone": "Asia/Ho_Chi_Minh",
            "agents": [
                {k: copy.deepcopy(v) for k, v in item.items() if k != "instructions"}
                for item in self.skills.values()
            ],
            "grants_permissions": False,
        }

    def detail(self, identifier):
        if not isinstance(identifier, str) or identifier not in self.skills:
            raise ValueError("Nhân sự chuyên môn chưa được duyệt")
        return copy.deepcopy(self.skills[identifier])

    def planning_catalogue(self):
        return [
            {"id": s["id"], "name": s["name"], "description": s["description"]}
            for s in self.skills.values()
        ]
