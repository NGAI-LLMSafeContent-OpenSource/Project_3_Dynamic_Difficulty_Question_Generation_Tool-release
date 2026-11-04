from __future__ import annotations

from typing import Any


DIFFICULTY_SHAPES = {
    "H1": {"harmful_count": 1, "harmless_count": 1, "interleaving": False, "strategy": "same_answer"},
    "H2": {"harmful_count": 2, "harmless_count": 1, "interleaving": False, "strategy": "background_nesting"},
    "H3": {"harmful_count": 1, "harmless_count": 2, "interleaving": False, "strategy": "near_semantic_mix"},
    "H4": {"harmful_count": 2, "harmless_count": 2, "interleaving": True, "strategy": "interleaved_multi_span"},
}


class DifficultyStrategyAllocator:
    skill_name = "difficulty_strategy_allocator"

    def __init__(self, difficulty_sequence: list[str] | None = None) -> None:
        self.difficulty_sequence = difficulty_sequence or ["H1", "H2", "H3"]
        for level in self.difficulty_sequence:
            if level not in DIFFICULTY_SHAPES:
                raise ValueError(f"unsupported difficulty_level: {level}")

    def for_retention(self, index: int) -> dict[str, Any]:
        level = self.difficulty_sequence[index % len(self.difficulty_sequence)]
        return self.for_level(level)

    def for_level(self, level: str) -> dict[str, Any]:
        shape = DIFFICULTY_SHAPES[level]
        return {
            "difficulty_level": level,
            "difficulty_strategy": shape["strategy"],
            "harmful_count": shape["harmful_count"],
            "harmless_count": shape["harmless_count"],
            "interleaving": shape["interleaving"],
        }

    def for_edit_success(self, index: int) -> dict[str, Any]:
        strategies = ["role_play", "encoding_obfuscation"]
        return {
            "difficulty_strategy": strategies[index % len(strategies)],
        }
