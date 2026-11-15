"""Trạng thái đăng ký SIWC hosted; chưa có OAuth client được duyệt thì đóng."""

import json


class KetNoiChatGPT:
    def __init__(self, kho):
        self.path = kho.root / "chatgpt-registration.json"

    def status(self):
        metadata = {}
        try:
            if self.path.is_file():
                value = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    metadata = value
        except (ValueError, OSError):
            pass
        # A registration receipt is not a client grant or an inference credential.
        return {
            "enabled": False,
            "has_client_id": False,
            "state": "awaiting_partner_approval",
            "registration_submitted": metadata.get("status") == "submitted",
            "deployment": "hosted",
            "uses_owner_subscription_for_guests": False,
            "registration_url": "https://openai.com/form/sign-in-with-chatgpt-interest/",
            "documentation_url": "https://developers.openai.com/siwc",
            "plan_usage_url": "https://developers.openai.com/siwc/token-sharing-open-source",
        }
