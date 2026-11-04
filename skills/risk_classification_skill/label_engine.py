from __future__ import annotations

from skills.common.models import CandidateText


class SafetyLabelEngine:
    skill_name = "safety_label_engine"

    def validate_pool(self, pool: dict[str, list[CandidateText]]) -> None:
        for item in pool["harmful_pool"]:
            if item.safety_label != "unsafe":
                raise ValueError(f"{item.item_id} must be unsafe")
        for item in pool["harmless_pool"]:
            if item.safety_label != "safe":
                raise ValueError(f"{item.item_id} must be safe")
