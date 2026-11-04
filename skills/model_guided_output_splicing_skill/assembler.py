from __future__ import annotations

from typing import Any

from skills.common.models import CandidateText


class DatasetAssembler:
    skill_name = "dataset_assembler"

    def build_edit_success(
        self,
        *,
        sample_id: str,
        harmful_item: CandidateText,
        difficulty: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "sample_id": sample_id,
            "sample_type": "harmful_only_baseline",
            "metric_targets": ["edit_success"],
            "harmful_text": harmful_item.text,
            "safety_label": "unsafe",
            "language": harmful_item.language,
            "category": harmful_item.category,
            **risk_fields(harmful_item),
            "domain": harmful_item.domain,
            "difficulty_strategy": difficulty["difficulty_strategy"],
            "source_trace": [harmful_item.to_source_dict()],
        }

    def build_paired_edit(
        self,
        *,
        sample_id: str,
        match: dict[str, Any],
        difficulty: dict[str, Any],
        composed: dict[str, Any],
        spans: dict[str, list[dict[str, Any]]],
        data_origin: str = "splice_constructed",
    ) -> dict[str, Any]:
        harmful_items = match["harmful_items"]
        harmless_items = match["harmless_items"]
        sample = {
            "sample_id": sample_id,
            "sample_type": "mixed_edit_input",
            "data_origin": data_origin,
            "metric_targets": ["edit_success", "harmless_retention"],
            "harmful_texts": [item.text for item in harmful_items],
            "harmless_texts": [item.text for item in harmless_items],
            "inserted_harmful_texts": composed.get("inserted_harmful_texts", [item.text for item in harmful_items]),
            "inserted_harmless_texts": composed.get("inserted_harmless_texts", [item.text for item in harmless_items]),
            "source_boundary_edits": composed.get("source_boundary_edits", []),
            "harmful_count": difficulty["harmful_count"],
            "harmless_count": difficulty["harmless_count"],
            "edited_input": composed["edited_input"],
            "harmful_spans": spans["harmful_spans"],
            "harmless_spans": spans["harmless_spans"],
            "safety_label": "unsafe",
            "language": harmful_items[0].language,
            "category": harmful_items[0].category,
            **risk_fields(harmful_items[0]),
            "domain": harmful_items[0].domain,
            "difficulty_level": difficulty["difficulty_level"],
            "difficulty_strategy": difficulty["difficulty_strategy"],
            "compose_strategy": composed.get("compose_strategy", difficulty["difficulty_strategy"]),
            "compose_variant": composed.get("compose_variant"),
            "pairing_review_label": composed.get("pairing_review_label"),
            "pairing_review_reason": composed.get("pairing_review_reason"),
            "bridge_texts": composed.get("bridge_texts", []),
            "bridge_review_label": composed.get("bridge_review_label"),
            "bridge_review_reason": composed.get("bridge_review_reason"),
            "final_guard_label": composed.get("final_guard_label"),
            "final_guard_categories": composed.get("final_guard_categories", []),
            "interleaving": difficulty["interleaving"],
            "coherence_label": "coherent" if composed.get("pairing_review_label") == "accepted" else "unknown",
            "coherence_reason": composed.get("pairing_review_reason") or match["coherence_reason"],
            "source_trace": [item.to_source_dict() for item in harmful_items + harmless_items],
        }
        return sample


def risk_fields(item: CandidateText) -> dict[str, Any]:
    return {
        "risk_category_id": item.risk_category_id,
        "risk_category": item.risk_category,
        "risk_category_key": item.risk_category_key,
        "risk_level": item.risk_level,
        "secondary_risk_categories": item.secondary_risk_categories,
        "source_category": item.source_category,
        "guard_category": item.guard_category,
    }
