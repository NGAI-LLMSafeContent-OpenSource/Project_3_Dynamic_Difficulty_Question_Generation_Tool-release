from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


RISK_CATEGORY_DEFAULTS = {
    "隐私泄露": {
        "risk_category_id": "R10",
        "risk_category": "侵犯他人权益",
        "risk_category_key": "rights_infringement",
        "risk_level": "medium",
    },
    "不当医疗建议": {
        "risk_category_id": "R11",
        "risk_category": "无法满足特定服务类型的安全需求",
        "risk_category_key": "service_specific_safety_failure",
        "risk_level": "medium",
    },
    "歧视偏见": {
        "risk_category_id": "R08",
        "risk_category": "歧视性内容",
        "risk_category_key": "discriminatory_content",
        "risk_level": "medium",
    },
    "高风险投资建议": {
        "risk_category_id": "R12",
        "risk_category": "经济损失高风险的活动",
        "risk_category_key": "high_risk_economic_loss_activity",
        "risk_level": "high",
    },
}


@dataclass(frozen=True)
class CandidateText:
    item_id: str
    text: str
    safety_label: str
    language: str
    domain: str
    category: str
    source_trace: str
    collected_at: str
    risk_category_id: str | None
    risk_category: str
    risk_category_key: str
    risk_level: str
    secondary_risk_categories: list[str]
    source_category: list[str]
    guard_category: list[str]

    @classmethod
    def from_raw(
        cls,
        raw: dict[str, Any],
        *,
        prefix: str,
        index: int,
        default_label: str,
        default_language: str,
    ) -> "CandidateText":
        text = str(raw.get("text") or raw.get(f"{prefix}_text") or "").strip()
        if not text:
            raise ValueError(f"{prefix}_pool[{index}] missing text")

        safety_label = str(raw.get("safety_label", default_label)).strip()
        if safety_label not in {"safe", "unsafe"}:
            raise ValueError(f"{prefix}_pool[{index}] safety_label must be safe or unsafe")
        if safety_label != default_label:
            raise ValueError(f"{prefix}_pool[{index}] expected {default_label}, got {safety_label}")

        category = str(raw.get("category", "")).strip()
        domain = str(raw.get("domain") or category or "general").strip()
        language = str(raw.get("language") or default_language).strip()
        item_id = str(raw.get("id") or raw.get(f"{prefix}_id") or f"{prefix}_{index + 1:06d}")
        source_trace = str(raw.get("source_trace") or raw.get("source") or "manual_seed")
        collected_at = str(raw.get("collected_at") or now_iso())
        risk_fields = normalize_risk_fields(raw, category=category, safety_label=safety_label)

        return cls(
            item_id=item_id,
            text=text,
            safety_label=safety_label,
            language=language,
            domain=domain,
            category=category,
            source_trace=source_trace,
            collected_at=collected_at,
            risk_category_id=risk_fields["risk_category_id"],
            risk_category=risk_fields["risk_category"],
            risk_category_key=risk_fields["risk_category_key"],
            risk_level=risk_fields["risk_level"],
            secondary_risk_categories=risk_fields["secondary_risk_categories"],
            source_category=risk_fields["source_category"],
            guard_category=risk_fields["guard_category"],
        )

    def to_source_dict(self) -> dict[str, Any]:
        return {
            "id": self.item_id,
            "safety_label": self.safety_label,
            "language": self.language,
            "domain": self.domain,
            "category": self.category,
            "risk_category_id": self.risk_category_id,
            "risk_category": self.risk_category,
            "risk_category_key": self.risk_category_key,
            "risk_level": self.risk_level,
            "secondary_risk_categories": self.secondary_risk_categories,
            "source_category": self.source_category,
            "guard_category": self.guard_category,
            "source_trace": self.source_trace,
            "collected_at": self.collected_at,
        }


def normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def normalize_risk_fields(raw: dict[str, Any], *, category: str, safety_label: str) -> dict[str, Any]:
    source_category = normalize_string_list(raw.get("source_category")) or normalize_string_list(category)
    guard_category = normalize_string_list(raw.get("guard_category"))
    secondary = normalize_string_list(raw.get("secondary_risk_categories"))

    if safety_label == "safe":
        return {
            "risk_category_id": raw.get("risk_category_id"),
            "risk_category": str(raw.get("risk_category") or "安全"),
            "risk_category_key": str(raw.get("risk_category_key") or "safe"),
            "risk_level": str(raw.get("risk_level") or "safe"),
            "secondary_risk_categories": secondary,
            "source_category": source_category,
            "guard_category": guard_category,
        }

    defaults = RISK_CATEGORY_DEFAULTS.get(category, {})
    return {
        "risk_category_id": raw.get("risk_category_id") or defaults.get("risk_category_id"),
        "risk_category": str(raw.get("risk_category") or defaults.get("risk_category") or category),
        "risk_category_key": str(raw.get("risk_category_key") or defaults.get("risk_category_key") or category),
        "risk_level": str(raw.get("risk_level") or defaults.get("risk_level") or "medium"),
        "secondary_risk_categories": secondary,
        "source_category": source_category,
        "guard_category": guard_category,
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
