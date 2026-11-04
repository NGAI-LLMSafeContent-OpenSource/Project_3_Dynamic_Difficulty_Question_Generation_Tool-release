from __future__ import annotations

import random
from typing import Any

from skills.common.models import CandidateText


class TextPairMatcher:
    skill_name = "text_pair_matcher"

    def run(
        self,
        pool: dict[str, list[CandidateText]],
        *,
        language: str,
        harmful_count: int,
        harmless_count: int,
        offset: int,
    ) -> dict[str, Any]:
        domains = sorted(
            {item.domain for item in pool["harmful_pool"] if item.language == language}
            & {item.domain for item in pool["harmless_pool"] if item.language == language}
        )
        rng = random.Random(offset)
        rotated_domains = list(domains)
        rng.shuffle(rotated_domains)
        for domain in rotated_domains:
            harmful_items = sorted(
                [item for item in pool["harmful_pool"] if item.language == language and item.domain == domain],
                key=lambda item: item.item_id,
            )
            harmless_items = sorted(
                [item for item in pool["harmless_pool"] if item.language == language and item.domain == domain],
                key=lambda item: item.item_id,
            )
            if len(harmful_items) >= harmful_count and len(harmless_items) >= harmless_count:
                harmful_items = random_take(harmful_items, offset * 2 + 1, harmful_count)
                harmless_items = random_take(harmless_items, offset * 2 + 2, harmless_count)
                return {
                    "harmful_items": harmful_items,
                    "harmless_items": harmless_items,
                    "coherence_label": "same_subtopic_candidate",
                    "coherence_reason": f"同一 subtopic 随机抽样：{domain}",
                }
        raise ValueError(
            f"no coherent pair for language={language}, harmful_count={harmful_count}, harmless_count={harmless_count}"
        )


def random_take(items: list[CandidateText], seed: int, count: int) -> list[CandidateText]:
    if len(items) < count:
        raise ValueError(f"need {count} items, got {len(items)}")
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    return shuffled[:count]
