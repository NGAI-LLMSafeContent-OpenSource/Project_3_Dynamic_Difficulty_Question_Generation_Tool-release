from __future__ import annotations

from skills.common.models import CandidateText


class BufferPoolManager:
    skill_name = "buffer_pool_manager"

    def run(self, harmful_items: list[CandidateText], harmless_items: list[CandidateText]) -> dict[str, list[CandidateText]]:
        return {
            "harmful_pool": harmful_items,
            "harmless_pool": harmless_items,
        }
