from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_PATH = REPO_ROOT / "samples" / "samples.jsonl"
README_PATH = REPO_ROOT / "README.md"
EXPECTED_SAMPLE_KEYS = {
    "sample_id",
    "sample_type",
    "data_origin",
    "metric_targets",
    "harmful_texts",
    "harmless_texts",
    "inserted_harmful_texts",
    "inserted_harmless_texts",
    "source_boundary_edits",
    "harmful_count",
    "harmless_count",
    "edited_input",
    "harmful_spans",
    "harmless_spans",
    "safety_label",
    "language",
    "category",
    "risk_category_id",
    "risk_category",
    "risk_category_key",
    "risk_level",
    "secondary_risk_categories",
    "source_category",
    "guard_category",
    "domain",
    "difficulty_level",
    "difficulty_strategy",
    "compose_strategy",
    "compose_variant",
    "pairing_review_label",
    "pairing_review_reason",
    "bridge_texts",
    "bridge_review_label",
    "bridge_review_reason",
    "final_guard_label",
    "final_guard_categories",
    "interleaving",
    "coherence_label",
    "coherence_reason",
    "source_trace",
    "original_sample_id",
    "generation_index",
}
EXPECTED_SOURCE_TRACE_KEYS = {
    "id",
    "safety_label",
    "language",
    "domain",
    "category",
    "risk_category_id",
    "risk_category",
    "risk_category_key",
    "risk_level",
    "secondary_risk_categories",
    "source_category",
    "guard_category",
    "source_trace",
    "collected_at",
}


def load_samples() -> list[dict]:
    return [
        json.loads(line)
        for line in SAMPLES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class ExampleSamplesTests(unittest.TestCase):
    def test_examples_cover_two_samples_per_difficulty(self):
        samples = load_samples()

        self.assertEqual(len(samples), 8)
        self.assertEqual(
            Counter(sample["difficulty_level"] for sample in samples),
            {"H1": 2, "H2": 2, "H3": 2, "H4": 2},
        )

    def test_readme_lists_every_example_and_span(self):
        readme = README_PATH.read_text(encoding="utf-8")
        self.assertIn("samples/samples.jsonl", readme)
        self.assertIn("Included H1–H4 Example Data", readme)
        self.assertEqual(readme.count('<span title="Harmful span"'), 13)
        self.assertEqual(readme.count('<span title="Harmless span"'), 13)
        prose_without_samples = readme
        for sample in load_samples():
            self.assertIn(sample["sample_id"], readme)
            for span in sample["harmful_spans"] + sample["harmless_spans"]:
                self.assertIn(span["text"], readme)
                prose_without_samples = prose_without_samples.replace(span["text"], "")
        self.assertNotRegex(prose_without_samples, r"[\u4e00-\u9fff]")
        for marker in ("manual", "demo", "手工", "人工", "benchmark_demo"):
            self.assertNotIn(marker, readme)

    def test_examples_match_generated_paired_sample_schema(self):
        for sample in load_samples():
            self.assertEqual(set(sample), EXPECTED_SAMPLE_KEYS)
            index_text = f"{sample['generation_index']:06d}"
            self.assertEqual(
                sample["sample_id"],
                f"dynamic_difficulty_h1h4_generation_{index_text}",
            )
            self.assertEqual(sample["original_sample_id"], f"paired_edit_{index_text}")
            self.assertEqual(sample["data_origin"], "splice_constructed")
            self.assertEqual(
                sample["compose_strategy"],
                f"model_guided_{sample['difficulty_strategy']}",
            )
            self.assertEqual(sample["pairing_review_label"], "accepted")
            self.assertEqual(sample["bridge_review_label"], "accepted")
            self.assertEqual(sample["final_guard_label"], "Unsafe")
            self.assertEqual(
                len(sample["source_trace"]),
                sample["harmful_count"] + sample["harmless_count"],
            )
            self.assertEqual(
                Counter(item["safety_label"] for item in sample["source_trace"]),
                {"unsafe": sample["harmful_count"], "safe": sample["harmless_count"]},
            )
            for source in sample["source_trace"]:
                self.assertEqual(set(source), EXPECTED_SOURCE_TRACE_KEYS)
                self.assertNotIn("text", source)
                if source["safety_label"] == "unsafe":
                    self.assertEqual(source["source_category"], ["seed_pool"])
                    self.assertTrue(source["source_trace"].startswith("seed_pool:"))
                else:
                    self.assertEqual(
                        source["source_category"],
                        ["model_generated_harmless_companion"],
                    )
                    self.assertTrue(
                        source["source_trace"].startswith("generated_harmless_companion:")
                    )
            serialized = json.dumps(sample, ensure_ascii=False)
            for marker in ("manual", "demo", "手工", "人工", "benchmark_demo"):
                self.assertNotIn(marker, serialized)

    def test_span_offsets_match_display_text(self):
        expected_orders = {
            "H1": ["harmless", "harmful"],
            "H2": ["harmless", "harmful", "harmful"],
            "H3": ["harmless", "harmful", "harmless"],
            "H4": ["harmless", "harmful", "harmless", "harmful"],
        }
        for sample in load_samples():
            text = sample["edited_input"]
            self.assertNotIn("；", text)
            self.assertEqual(len(sample["harmful_spans"]), sample["harmful_count"])
            self.assertEqual(len(sample["harmless_spans"]), sample["harmless_count"])
            for span in sample["harmful_spans"] + sample["harmless_spans"]:
                self.assertEqual(text[span["start"] : span["end"]], span["text"])
            marked_spans = sorted(
                [
                    *((span["start"], span["end"], "harmful") for span in sample["harmful_spans"]),
                    *((span["start"], span["end"], "harmless") for span in sample["harmless_spans"]),
                ]
            )
            self.assertEqual(marked_spans[0][0], 0)
            self.assertEqual(marked_spans[-1][1], len(text))
            self.assertTrue(
                all(left[1] == right[0] for left, right in zip(marked_spans, marked_spans[1:]))
            )
            self.assertEqual(
                [kind for _, _, kind in marked_spans],
                expected_orders[sample["difficulty_level"]],
            )


if __name__ == "__main__":
    unittest.main()
