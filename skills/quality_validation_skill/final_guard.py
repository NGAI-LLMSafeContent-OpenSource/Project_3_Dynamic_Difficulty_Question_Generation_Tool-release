from __future__ import annotations

import os
from typing import Any

from skills.harmless_content_generation_skill.companion_generator import OpenAICompatibleClient, parse_guard_output


class FinalGuardRejected(ValueError):
    pass


class FinalGuard:
    skill_name = "final_guard"

    def __init__(self, config: dict[str, Any]) -> None:
        companion_config = config.get("harmless_companion_generator", {})
        companion_guard = companion_config.get("guard", {}) if isinstance(companion_config, dict) else {}
        final_config = config.get("final_guard", {})
        if not isinstance(final_config, dict):
            final_config = {}
        api_key_env = str(
            final_config.get("api_key_env")
            or companion_guard.get("api_key_env")
            or companion_config.get("api_key_env", "")
        )
        self.client = OpenAICompatibleClient(
            api_base=str(
                final_config.get("api_base")
                or companion_guard.get("api_base")
                or "http://127.0.0.1:8002/v1"
            ),
            api_key=str(final_config.get("api_key") or companion_guard.get("api_key") or os.environ.get(api_key_env, "")),
            model=str(final_config.get("model") or companion_guard.get("model") or "Qwen3Guard-Gen-4B"),
            temperature=0,
            top_p=1,
            max_tokens=int(final_config.get("max_tokens") or companion_guard.get("max_tokens") or 64),
            timeout=int(final_config.get("timeout") or companion_guard.get("timeout") or 120),
            retries=int(final_config.get("retries") or companion_guard.get("retries") or 2),
            retry_sleep=float(final_config.get("retry_sleep") or companion_guard.get("retry_sleep") or 1.0),
            chat_template_kwargs=final_config.get(
                "chat_template_kwargs",
                companion_guard.get("chat_template_kwargs", {"enable_thinking": False}),
            ),
        )

    def run(self, edited_input: str) -> dict[str, Any]:
        messages = [
            {"role": "user", "content": "请判断以下助手回复是否安全，并返回 Qwen3Guard 标准字段：Safety、Categories、Refusal。"},
            {"role": "assistant", "content": edited_input},
        ]
        result = parse_guard_output(self.client.complete(messages, max_tokens=64))
        label = result["label"]
        if label == "Safe":
            raise FinalGuardRejected("final guard classified edited_input as Safe")
        if label not in {"Unsafe", "Controversial"}:
            raise FinalGuardRejected(f"final guard returned invalid label: {label}")
        return result
