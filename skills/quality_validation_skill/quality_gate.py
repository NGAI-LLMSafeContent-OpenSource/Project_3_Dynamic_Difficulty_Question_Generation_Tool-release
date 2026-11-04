from __future__ import annotations

from typing import Any

from skills.difficulty_assignment_skill.difficulty import DIFFICULTY_SHAPES


class QualityGate:
    skill_name = "quality_gate"

    def run(self, samples: list[dict[str, Any]]) -> dict[str, Any]:
        safe_label_check = all(sample.get("safety_label") in {"safe", "unsafe"} for sample in samples)
        span_check = all(self._span_check(sample) for sample in samples)
        coherence_check = all(
            not targets_include(sample, "harmless_retention") or sample.get("coherence_label") == "coherent"
            for sample in samples
        )
        difficulty_check = all(self._difficulty_check(sample) for sample in samples)
        final_guard_check = all(self._final_guard_check(sample) for sample in samples)
        return {
            "safe_label_check": "passed" if safe_label_check else "failed",
            "span_check": "passed" if span_check else "failed",
            "coherence_check": "passed" if coherence_check else "failed",
            "difficulty_check": "passed" if difficulty_check else "failed",
            "final_guard_check": "passed" if final_guard_check else "failed",
            "human_review_ratio": 0.05,
            "sample_count": len(samples),
        }

    def _span_check(self, sample: dict[str, Any]) -> bool:
        if not targets_include(sample, "harmless_retention"):
            return True
        edited_input = sample["edited_input"]
        spans = sample["harmful_spans"] + sample["harmless_spans"]
        return all(edited_input[span["start"] : span["end"]] == span["text"] for span in spans)

    def _difficulty_check(self, sample: dict[str, Any]) -> bool:
        if not targets_include(sample, "harmless_retention"):
            return True
        shape = DIFFICULTY_SHAPES[sample["difficulty_level"]]
        return (
            sample["harmful_count"] == shape["harmful_count"]
            and sample["harmless_count"] == shape["harmless_count"]
            and sample["interleaving"] == shape["interleaving"]
        )

    def _final_guard_check(self, sample: dict[str, Any]) -> bool:
        if sample.get("sample_type") != "mixed_edit_input":
            return True
        return sample.get("final_guard_label") in {"Unsafe", "Controversial"}


def targets_include(sample: dict[str, Any], target: str) -> bool:
    return target in sample.get("metric_targets", [])
