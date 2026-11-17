"""Danh mục mô hình, chọn theo chuyên môn và cấu hình LiteLLM riêng.

LiteLLM xử lý giao thức nhà cung cấp; BDSG giữ danh tính, quyền công cụ,
hạn mức và chứng cứ chọn mô hình. Không tự đổi nhà cung cấp khi gọi lỗi.
"""

import copy
import json
import os
import re
import secrets
import threading
from urllib.request import Request, build_opener

from mo_hinh_bdsg import KhongChuyenHuong, LoiMoHinhBDSG, MoHinhBDSG
from ngan_sach_ai import DEFAULT_POLICY, NganSachAI, money, validate_policy

PROVIDERS = {"openai", "anthropic", "gemini", "deepseek", "mistral", "groq", "xai"}
CAPABILITIES = {"general", "reasoning", "coding", "writing", "analysis", "fast"}
ID = re.compile(r"[a-z][a-z0-9-]{1,47}\Z")
SKILL_CAPABILITIES = {
    "bdsg-debug": "coding",
    "bdsg-review-code": "coding",
    "bdsg-backend-api": "coding",
    "bdsg-phat-trien-frontend": "coding",
    "bdsg-sql-co-so-du-lieu": "coding",
    "bdsg-tai-chinh": "analysis",
    "bdsg-ke-toan-doi-soat": "analysis",
    "bdsg-phan-tich-du-lieu": "analysis",
    "bdsg-bang-tinh-excel": "analysis",
    "bdsg-viet-noi-dung": "writing",
    "bdsg-bien-tap": "writing",
    "bdsg-seo-noi-dung": "writing",
    "bdsg-chien-luoc": "reasoning",
    "bdsg-nghien-cuu": "reasoning",
}


def validate_catalogue(data, previous):
    if not isinstance(data, dict) or set(data) != {
        "enabled",
        "default_model",
        "models",
        "policy",
    }:
        raise ValueError("Cấu hình trung tâm AI chưa đúng cấu trúc")
    if (
        type(data["enabled"]) is not bool
        or not isinstance(data["models"], list)
        or len(data["models"]) > 16
    ):
        raise ValueError("Chọn tối đa 16 mô hình trong danh mục được duyệt")
    policy = validate_policy(data["policy"])
    old = {model["id"]: model for model in previous["models"]}
    models, seen = [], set()
    for incoming in data["models"]:
        if (
            not isinstance(incoming, dict)
            or set(incoming)
            - {
                "id",
                "label",
                "upstream_model",
                "api_key",
                "capabilities",
                "skills",
                "prices",
            }
            or not {
                "id",
                "label",
                "upstream_model",
                "capabilities",
                "skills",
                "prices",
            }
            <= set(incoming)
        ):
            raise ValueError("Hồ sơ mô hình có trường không được hỗ trợ")
        item = copy.deepcopy(incoming)
        identifier = item["id"]
        if (
            not isinstance(identifier, str)
            or not ID.fullmatch(identifier)
            or identifier in seen
        ):
            raise ValueError("Mã mô hình phải duy nhất, chữ thường không dấu")
        seen.add(identifier)
        if (
            not isinstance(item["label"], str)
            or not 1 <= len(item["label"]) <= 80
        ):
            raise ValueError("Tên hiển thị mô hình chưa hợp lệ")
        upstream = item["upstream_model"]
        if (
            not isinstance(upstream, str)
            or not re.fullmatch(r"[A-Za-z0-9_./:-]{3,180}", upstream)
            or upstream.split("/")[0] not in PROVIDERS
        ):
            raise ValueError("Nhà cung cấp hoặc tên mô hình chưa được hỗ trợ")
        for key, allowed, maximum in (
            ("capabilities", CAPABILITIES, 6),
            ("skills", None, 38),
        ):
            values = item[key]
            if (
                not isinstance(values, list)
                or len(values) > maximum
                or any(not isinstance(v, str) for v in values)
                or len(set(values)) != len(values)
                or (allowed and any(v not in allowed for v in values))
                or (
                    key == "skills" and any(not ID.fullmatch(v) for v in values)
                )
            ):
                raise ValueError("Nhóm năng lực hoặc mã chuyên môn chưa hợp lệ")
        if not isinstance(item["prices"], dict) or set(item["prices"]) != {
            "input_per_million",
            "output_per_million",
        }:
            raise ValueError(
                "Nhập giá input/output USD trên một triệu token để giữ ngân sách"
            )
        item["prices"] = {
            key: str(money(value, 1000))
            for key, value in item["prices"].items()
        }
        key = item.get("api_key") or old.get(identifier, {}).get("api_key")
        if (
            not isinstance(key, str)
            or not 10 <= len(key) <= 4096
            or any(ord(c) < 32 for c in key)
        ):
            raise ValueError(
                "Cần khóa API hợp lệ; không dán khóa vào cuộc trò chuyện"
            )
        if (
            item.get("api_key") in (None, "")
            and old.get(identifier, {}).get("upstream_model") != upstream
        ):
            raise ValueError(
                "Đổi nhà cung cấp/mô hình cần nhập lại khóa để tránh gửi nhầm chứng thư"
            )
        item["api_key"] = key
        models.append(item)
    if data["default_model"] not in seen and (
        models or data["default_model"] is not None
    ):
        raise ValueError("Mô hình mặc định phải nằm trong danh mục")
    if data["enabled"] and not models:
        raise ValueError("Cần ít nhất một mô hình trước khi bật")
    return {"enabled": data["enabled"], "models": models,
            "default_model": data["default_model"], "policy": policy}


def choose_catalogue(data, context):
    if not data["enabled"] or not data["models"]:
        raise LoiMoHinhBDSG("Trung tâm AI chưa có mô hình được chủ quản cấu hình")
    models = {model["id"]: model for model in data["models"]}
    selected = context.get("model_selection", "auto")
    if selected != "auto":
        if not isinstance(selected, str) or selected not in models:
            raise LoiMoHinhBDSG(
                "Mô hình đã chọn không còn trong danh mục được duyệt"
            )
        reason = "Lựa chọn cụ thể của tác vụ hoặc Agent tổng"
    else:
        skill = context.get("assignment", {}).get("skill_id")
        candidates = [
            model for model in data["models"] if skill and skill in model["skills"]
        ]
        capability = SKILL_CAPABILITIES.get(skill, "general")
        if "workforce_catalogue" in context or "workforce_results" in context:
            capability = "reasoning"
        candidates = candidates or [
            model for model in data["models"] if capability in model["capabilities"]
        ]
        selected = candidates[0]["id"] if candidates else data["default_model"]
        reason = "Chính sách chuyên môn " + (skill or capability)
    return models[selected], data, reason


class MoHinhLiteLLM(MoHinhBDSG):
    MAX_OUTPUT_TOKENS = 8192
    MAX_REQUEST_SECONDS = 60

    def __init__(self, alias, key, opener=None):
        # Chỉ giao tiếp loopback do vận hành sở hữu; không nhận base_url từ chat.
        super().__init__(
            environ={
                "BDSG_MODEL_PROVIDER": "bdsg",
                "BDSG_MODEL_BASE_URL": "http://127.0.0.1:4000/v1",
                "BDSG_MODEL_NAME": alias,
                "BDSG_MODEL_API_KEY": key,
            },
            opener=opener,
        )
        self.provider = "litellm"


class TrungTamAI:
    def __init__(self, kho, adapter_factory=None, probe=None):
        self.kho = kho
        self.path = kho.root / "ai-models-private.json"
        self.proxy_path = kho.root / "litellm-config.json"
        self.lock = threading.RLock()
        self.budget = NganSachAI(kho)
        self.factory = adapter_factory or (lambda alias, key: MoHinhLiteLLM(alias, key))
        self.probe = probe or self._probe
        self.data = {
            "enabled": False,
            "revision": "none",
            "default_model": None,
            "models": [],
            "policy": dict(DEFAULT_POLICY),
            "gateway_key": None,
        }
        if self.path.is_file():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            self.data["policy"] = validate_policy(
                {**DEFAULT_POLICY, **self.data["policy"]}
            )
        self.configuration_error = ""

    @staticmethod
    def _probe(key, aliases):
        request = Request(
            "http://127.0.0.1:4000/v1/models",
            headers={"Authorization": "Bearer " + key},
        )
        try:
            with build_opener(KhongChuyenHuong()).open(request, timeout=2) as response:
                raw = response.read(131073)
                if len(raw) > 131072:
                    return False
                result = json.loads(raw)
            return aliases <= {item["id"] for item in result["data"]}
        except (OSError, ValueError, TypeError, KeyError):
            return False

    def assert_ready(self):
        with self.lock:
            data = copy.deepcopy(self.data)
        aliases = {model["id"] + "-" + data["revision"] for model in data["models"]}
        if (
            not data["enabled"]
            or not aliases
            or not self.probe(data["gateway_key"], aliases)
        ):
            raise LoiMoHinhBDSG(
                "Gateway AI chưa nạp danh mục mới hoặc chưa hoạt động; chưa nhận tác vụ hay gửi yêu cầu tới nhà cung cấp."
            )

    @property
    def configured(self):
        with self.lock:
            return bool(self.data["enabled"] and self.data["models"])

    def public_status(self):
        return {
            "configured": self.configured,
            "mode": "mo-hinh-api" if self.configured else "quy-trinh",
            "provider": "litellm",
            "model": "Tự động theo công việc" if self.configured else None,
            "verified": False,
            "configuration_revision": self.data["revision"],
        }

    def catalogue(self):
        with self.lock:
            return {
                "enabled": self.data["enabled"],
                "default_model": self.data["default_model"],
                "models": [
                    {
                        key: model[key]
                        for key in ("id", "label", "capabilities", "skills")
                    }
                    for model in self.data["models"]
                ],
                "automatic_selection": True,
            }

    def admin(self, actor):
        self._admin(actor)
        with self.lock:
            result = self.catalogue()
            result["models"] = [
                {**model, "has_api_key": bool(model.get("api_key"))}
                for model in copy.deepcopy(self.data["models"])
            ]
            for model in result["models"]:
                model.pop("api_key", None)
            result["policy"] = dict(self.data["policy"])
            result["configured"] = self.configured
            result["verified"] = False
            result["revision"] = self.data["revision"]
            return result

    @staticmethod
    def _admin(actor):
        if not isinstance(actor, dict) or actor.get("role") != "quan-tri":
            raise PermissionError("Chỉ chủ quản được cấu hình mô hình và ngân sách AI")

    @staticmethod
    def _write(path, data):
        temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
        try:
            fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, actor, data):
        self._admin(actor)
        # Cùng khóa SQLite với quota và snapshot: không có cấu hình mới đi với số dư cũ.
        with self.kho.ket_noi() as db:
            db.execute("BEGIN IMMEDIATE")
            result = self._save_guarded(actor, data)
        self.kho.su_kien(actor["id"], "cau-hinh-trung-tam-ai", result["revision"])
        return result

    def _save_guarded(self, actor, data):
        with self.lock:
            validated = validate_catalogue(data, self.data)
            models, policy = validated["models"], validated["policy"]
            revision = secrets.token_hex(6)
            candidate = {
                "enabled": data["enabled"],
                "revision": revision,
                "models": models,
                "default_model": data["default_model"],
                "policy": policy,
                "gateway_key": self.data["gateway_key"] or secrets.token_urlsafe(36),
            }
            proxy = self.proxy_config(candidate)
            # Mỗi alias có revision: trong cửa sổ reload, proxy cũ không thể gọi nhầm model mới.
            previous_proxy = (
                json.loads(self.proxy_path.read_text(encoding="utf-8"))
                if self.proxy_path.exists()
                else None
            )
            self._write(self.proxy_path, proxy)
            try:
                self._write(self.path, candidate)
            except OSError:
                if previous_proxy is None:
                    self.proxy_path.unlink(missing_ok=True)
                else:
                    self._write(self.proxy_path, previous_proxy)
                raise
            self.data = candidate
        return self.admin(actor)

    def admit(self, db, actor, task_id, run, selection="auto"):
        """Transaction thuộc tác vụ; readiness và giữ suất dùng cùng danh mục ổn định."""
        with self.lock:
            self.assert_ready()
            if selection != "auto" and selection not in {
                model["id"] for model in self.data["models"]
            }:
                raise ValueError("Mô hình đã chọn vừa thay đổi; hãy tải lại danh mục")
            self.budget.claim_task(db, actor, task_id, run, self.data["policy"])

    def quota(self, actor):
        with self.lock:
            policy = dict(self.data["policy"])
        result=self.budget.status(actor, policy)
        if actor.get("role") != "quan-tri":
            result["policy"]={key:value for key,value in result["policy"].items() if key.endswith("_per_user")}
        return result

    @staticmethod
    def proxy_config(data):
        return {
            "model_list": [
                {
                    "model_name": model["id"] + "-" + data["revision"],
                    "litellm_params": {
                        "model": model["upstream_model"],
                        "api_key": model["api_key"],
                        "num_retries": 0,
                        "max_retries": 0,
                    },
                }
                for model in data["models"]
            ]
            if data["enabled"]
            else [],
            "general_settings": {
                "master_key": data["gateway_key"],
                "disable_spend_logs": True,
            },
            "litellm_settings": {
                "turn_off_message_logging": True,
                "set_verbose": False,
                "success_callback": [],
                "failure_callback": [],
                "suppress_startup_output": True,
            },
            "router_settings": {"num_retries": 0, "fallbacks": []},
        }

    def choose(self, context):
        with self.lock:
            data = copy.deepcopy(self.data)
        return choose_catalogue(data, context)

    def run(self, prompt, context, core, actor, on_event=None, cancelled=None):
        self.assert_ready()
        model, config, reason = self.choose(context)
        emit = on_event or (lambda *a, **k: None)
        if cancelled and cancelled():
            raise LoiMoHinhBDSG("Tác vụ đã được yêu cầu dừng")
        emit(
            "model-selected",
            "Đã chọn mô hình trong danh mục được duyệt.",
            model_id=model["id"],
            model_label=model["label"],
            selection_reason=reason,
        )
        adapter = self.factory(
            model["id"] + "-" + config["revision"], config["gateway_key"]
        )

        def event(kind, message, **extra):
            if kind == "model-reserve":
                count = extra.get("input_bytes")
                if type(count) is not int or count < 1:
                    raise LoiMoHinhBDSG(
                        "Thiếu số đo ngữ cảnh để giữ ngân sách trước khi gọi AI"
                    )
                self.budget.reserve(
                    actor,
                    context.get("task_id", ""),
                    model["id"],
                    count + 4096,
                    MoHinhLiteLLM.MAX_OUTPUT_TOKENS,
                    model["prices"],
                    config["policy"],
                    project_id=context.get("project_id", ""),
                )
            emit(kind, message, **extra)

        return adapter.run(prompt, context, core, actor, event, cancelled)
