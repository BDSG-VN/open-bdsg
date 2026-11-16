"""Cấu hình mô hình do chủ quản nhập; bí mật không được trả lại giao diện."""
import json
import os
import secrets
from mo_hinh_bdsg import MoHinhBDSG


class CauHinhMoHinh:
    def __init__(self, kho, engine):
        self.kho, self.engine = kho, engine
        self.path = kho.root / "model-private.json"
        if self.path.is_file():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.engine.model = MoHinhBDSG(environ={}) if data == {"disabled": True} else self.candidate(data)

    def candidate(self, data):
        if not isinstance(data, dict) or set(data) - {"provider", "model", "api_key", "base_url"}:
            raise ValueError("Thông tin cấu hình không hợp lệ")
        provider = data.get("provider")
        model, key = data.get("model", ""), data.get("api_key", "")
        if provider not in ("openai", "anthropic", "bdsg") or not isinstance(model, str) or not isinstance(key, str) or not 1 <= len(model.strip()) <= 128 or not 10 <= len(key.strip()) <= 4096:
            raise ValueError("Cần nhà cung cấp, tên mô hình và khóa API hợp lệ")
        env = {"BDSG_MODEL_PROVIDER": provider}
        if provider == "bdsg":
            base = data.get("base_url") or "https://llm.bdsg.vn/v1"
            if not isinstance(base, str):
                raise ValueError("Địa chỉ API BDSG không hợp lệ")
            env.update(BDSG_MODEL_BASE_URL=base, BDSG_MODEL_NAME=model.strip(), BDSG_MODEL_API_KEY=key.strip())
        elif provider == "openai":
            env.update(OPENAI_MODEL=model.strip(), OPENAI_API_KEY=key.strip())
        else:
            env.update(ANTHROPIC_MODEL=model.strip(), ANTHROPIC_API_KEY=key.strip())
        candidate = MoHinhBDSG(environ=env)
        if not candidate.configured or candidate.configuration_error:
            raise ValueError("Cấu hình mô hình chưa hợp lệ; kiểm tra nhà cung cấp và tên mô hình")
        return candidate

    def _write(self, data, candidate):
        temporary = self.path.with_name("model-private-" + secrets.token_hex(8) + ".tmp")
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self.engine.model = candidate
        finally:
            temporary.unlink(missing_ok=True)
    def save(self, actor, data):
        if actor.get("role") != "quan-tri":
            raise PermissionError("Chỉ chủ quản được cấu hình mô hình")
        if getattr(self.engine,"ai",None) and self.engine.ai.path.exists():
            raise ValueError("Mô hình đang do Trung tâm AI quản lý; hãy cấu hình tại mục đó")
        candidate = self.candidate(data)
        self._write(data, candidate)
        self.kho.su_kien(actor["id"], "cau-hinh-mo-hinh", data["provider"])
        return {**candidate.public_status(), "verified": False}

    def disable(self, actor):
        if actor.get("role") != "quan-tri":
            raise PermissionError("Chỉ chủ quản được tắt mô hình")
        if getattr(self.engine,"ai",None) and self.engine.ai.path.exists():
            raise ValueError("Hãy tắt mô hình tại Trung tâm AI để giữ đúng chính sách ngân sách")
        # Giữ dấu tắt để lần khởi động sau không tự bật lại từ biến môi trường.
        model = MoHinhBDSG(environ={})
        self._write({"disabled": True}, model)
        self.kho.su_kien(actor["id"], "tat-mo-hinh")
        return model.public_status()
