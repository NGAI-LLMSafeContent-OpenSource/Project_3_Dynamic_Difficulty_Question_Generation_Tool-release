from __future__ import annotations

from typing import Any

from skills.common.models import CandidateText


class HarmfulIntentExtractor:
    skill_name = "harmful_intent_extractor"

    def run(self, raw_items: list[dict[str, Any]], *, language: str) -> list[CandidateText]:
        return [
            CandidateText.from_raw(item, prefix="harmful", index=index, default_label="unsafe", default_language=language)
            for index, item in enumerate(raw_items)
        ]


class HarmlessIntentExtractor:
    skill_name = "harmless_intent_extractor"

    def run(self, raw_items: list[dict[str, Any]], *, language: str) -> list[CandidateText]:
        return [
            CandidateText.from_raw(item, prefix="harmless", index=index, default_label="safe", default_language=language)
            for index, item in enumerate(raw_items)
        ]
