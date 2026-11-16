"""Danh mục nhân sự từ bộ kỹ năng đã duyệt; tên vai trò không tự cấp quyền."""

import base64
import copy
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


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
                or identifier.endswith("-")
                or "--" in identifier
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

    def export_bundle(self, arguments):
        """Chỉ đóng gói kỹ năng công khai; không duyệt thư mục dữ liệu vận hành."""
        if not isinstance(arguments, dict) or set(arguments) != {"format"}:
            raise ValueError("Cần chọn định dạng gói kỹ năng")
        format_id = arguments["format"]
        if format_id not in ("portable", "codex", "claude"):
            raise ValueError("Định dạng gói chưa được hỗ trợ")
        files = {}
        prefix = ".agents/skills/" if format_id == "codex" else "skills/"
        for identifier, item in self.skills.items():
            files[prefix + identifier + "/SKILL.md"] = item["instructions"].encode()
        controller = (self.root / "bo-dieu-phoi/bdsg-agent-tong/SKILL.md").read_text(
            encoding="utf-8"
        )
        files[prefix + "bdsg-agent-tong/SKILL.md"] = controller.encode()
        files[prefix + "bdsg-agent-tong/references/catalog.json"] = json.dumps(
            self.planning_catalogue(), ensure_ascii=False, indent=2
        ).encode()
        export_ids = [*self.skills, "bdsg-agent-tong"]
        lock = json.loads(
            (self.root / "vendor/sources.lock.json").read_text(encoding="utf-8")
        )
        for repository in lock["repositories"]:
            slug = repository["repository"].replace("/", "--")
            for record in repository["files"]:
                name = record["path"]
                if not any(
                    word in Path(name).name.upper() for word in ("LICENSE", "NOTICE")
                ):
                    continue
                original = self.root / "vendor" / slug / name
                if original.is_symlink() or not original.resolve().is_relative_to(
                    self.root / "vendor"
                ):
                    raise ValueError("Giấy phép nằm ngoài gói nguồn")
                raw = original.read_bytes()
                if (
                    len(raw) > 262144
                    or hashlib.sha256(raw).hexdigest() != record["sha256"]
                ):
                    raise ValueError("Giấy phép nguồn không khớp bản đã duyệt")
                files["third_party/" + slug + "/" + name] = raw
        files["catalog.json"] = json.dumps(
            self.catalogue(), ensure_ascii=False, indent=2
        ).encode()
        files["LICENSE"] = (
            (self.root.parent / "LICENSE-CODE").read_text(encoding="utf-8").encode()
        )
        if format_id == "portable":
            files["plugin.json"] = json.dumps(
                {
                    "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                    "name": "bdsg-thanhhoa-skills",
                    "version": "0.22.0",
                    "description": "Bộ kỹ năng nhân sự chuyên môn cho cá nhân và doanh nghiệp Việt Nam",
                    "license": "Apache-2.0",
                    "repository": "https://github.com/BDSG-VN/open-bdsg",
                },
                ensure_ascii=False,
                indent=2,
            ).encode()
        instructions = {
            "portable": "Gói Agent Plugins có plugin.json và skills/. Cần nhập/thử trên môi trường hỗ trợ. Chưa được công bố lên thư mục plugin ChatGPT; khả năng cài tùy bề mặt và tài khoản.",
            "codex": "Chép các thư mục .agents/skills/bdsg-* vào dự án Codex được chọn. Không ghi đè kỹ năng cũ nếu chưa đối chiếu. Kỹ năng sẽ được phát hiện ở lượt dùng tiếp theo của môi trường hỗ trợ.",
            "claude": "Thư mục individual/ có một zip riêng cho từng kỹ năng. Nhập từng zip vào môi trường Claude hỗ trợ custom skills. Có thể dùng thư mục skills/ với công cụ phát hiện SKILL.md tương thích.",
        }[format_id]
        files["HUONG-DAN.md"] = (
            "# BDSG — bộ kỹ năng chuyên môn\n\n"
            + instructions
            + "\n\nKỹ năng là quy trình, không phải mô hình, quyền truy cập hay tài khoản. Không có khóa, dữ liệu khách hàng, hook hoặc chương trình chạy tự động trong gói. Công cụ và xác thực phải được cấu hình riêng.\n"
            + "\nGiấy phép của nguồn tham khảo giữ trong third_party; quy trình tiếng Việt có attribution trong SKILL.md. Không nhận rằng toàn bộ mã nguồn tham khảo đã được kích hoạt.\n"
            + "\nTài liệu đối chiếu ngày 17/11/2026:\n- https://agentskills.io/specification\n- https://developers.openai.com/plugins/build/plugins\n- https://platform.claude.com/docs/en/managed-agents/skills\n"
        ).encode()
        if format_id == "claude":
            for identifier in export_ids:
                skill_prefix = prefix + identifier + "/"
                individual = {
                    identifier + "/" + name[len(skill_prefix) :]: raw
                    for name, raw in files.items()
                    if name.startswith(skill_prefix)
                }
                individual[identifier + "/LICENSE"] = files["LICENSE"]
                # Gói một skill vẫn tự chứa attribution và các thông báo giấy phép.
                individual.update(
                    {
                        identifier + "/" + name: raw
                        for name, raw in files.items()
                        if name.startswith("third_party/")
                    }
                )
                files["individual/" + identifier + ".zip"] = self._zip(individual)
        raw = self._zip(files)
        if len(raw) > 3 * 1024 * 1024:
            raise ValueError("Gói kỹ năng vượt giới hạn tải")
        return {
            "filename": "bdsg-thanhhoa-skills-" + format_id + ".zip",
            "mime_type": "application/zip",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "content_base64": base64.b64encode(raw).decode(),
            "skill_count": len(export_ids),
            "specialist_count": len(self.skills),
            "contains_credentials": False,
        }

    @staticmethod
    def _zip(files):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted(files.items()):
                path = PurePosixPath(name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in name
                    or "\0" in name
                ):
                    raise ValueError("Tên tệp trong gói không hợp lệ")
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, raw)
        return stream.getvalue()
