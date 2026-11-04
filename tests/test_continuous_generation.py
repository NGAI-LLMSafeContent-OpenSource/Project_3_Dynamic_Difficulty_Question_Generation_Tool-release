from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import MethodType
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_SCRIPTS = REPO_ROOT / "agent_framework" / "scripts"
UI_ROOT = REPO_ROOT / "ui"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(GENERATOR_SCRIPTS))
sys.path.insert(0, str(UI_ROOT))

import generate_benchmark_data as generator
import backend as ui_backend
from skills.pipeline import DynamicDifficultyQuestionGenerationPipeline


PASSED_REPORT = {
    "safe_label_check": "passed",
    "span_check": "passed",
    "coherence_check": "passed",
    "difficulty_check": "passed",
    "final_guard_check": "passed",
    "human_review_ratio": 0.05,
    "sample_count": 1,
}


class PassingQualityGate:
    def run(self, samples):
        return {**PASSED_REPORT, "sample_count": len(samples)}


class ContinuousSchedulerTests(unittest.TestCase):
    def test_refills_one_slot_without_waiting_for_slow_sample(self):
        pipeline = DynamicDifficultyQuestionGenerationPipeline.__new__(
            DynamicDifficultyQuestionGenerationPipeline
        )
        pipeline.parallelism = 2
        pipeline.sample_indices = [0, 1, 2, 3]
        pipeline.total_sample_count = 4
        pipeline.quality_gate = PassingQualityGate()
        pipeline.discard_counts = {}
        pipeline.discard_reason_samples = {}
        pipeline.discard_lock = threading.Lock()

        state_lock = threading.Lock()
        active = 0
        max_active = 0
        started_at = {}
        finished_at = {}

        def build_sample(self, pool, index, sample_count):
            nonlocal active, max_active
            with state_lock:
                active += 1
                max_active = max(max_active, active)
                started_at[index] = time.monotonic()
            time.sleep(0.12 if index == 0 else 0.02)
            with state_lock:
                active -= 1
                finished_at[index] = time.monotonic()
            return {"sample_id": f"sample_{index}", "difficulty_level": f"H{index + 1}"}

        pipeline._build_paired_edit_sample_with_retries = MethodType(build_sample, pipeline)
        completion_order = []
        results = pipeline._build_paired_edit_samples_parallel(
            {},
            lambda index, sample, counts, reasons: completion_order.append(index),
        )

        self.assertEqual(max_active, 2)
        self.assertEqual(completion_order[0], 1)
        self.assertLess(started_at[2], finished_at[0])
        self.assertEqual(
            [sample["sample_id"] for sample in results],
            [f"sample_{index}" for index in range(4)],
        )

    def test_repairs_partial_jsonl_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "samples.jsonl"
            path.write_bytes(
                b'{"generation_index": 1, "difficulty_level": "H1"}\n'
                b'{"generation_index": 3, "difficulty_level": "H3"}\n'
                b'{"generation_index":'
            )

            rows = generator.read_jsonl_rows(path, repair_tail=True)

            self.assertEqual([row["generation_index"] for row in rows], [1, 3])
            self.assertTrue(path.read_bytes().endswith(b"\n"))

    def test_resume_only_generates_missing_non_contiguous_indices(self):
        runs_root = REPO_ROOT / "runs"
        runs_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runs_root) as directory:
            output_dir = Path(directory)
            config_path = output_dir / "generation_config.json"
            samples_path = output_dir / "samples.jsonl"
            config = {
                "run_id": "continuous_resume_test",
                "output_dir": str(output_dir.relative_to(REPO_ROOT)),
                "generation": {
                    "total_sample_count": 4,
                    "difficulty_counts": {"H1": 1, "H2": 1, "H3": 1, "H4": 1},
                    "resume": True,
                },
                "skill": {"path": "skills"},
                "harmless_companion_generator": {"model": "fake"},
                "llm_composer": {"concurrency": 2},
                "llm": {"enabled": False},
                "seed_generation": {"enabled": False},
            }
            config_path.write_text(json.dumps(config), encoding="utf-8")
            generator.append_jsonl(
                samples_path,
                [
                    {"sample_id": "existing_1", "generation_index": 1, "difficulty_level": "H1"},
                    {"sample_id": "existing_3", "generation_index": 3, "difficulty_level": "H3"},
                ],
            )

            class FakePipeline:
                received_indices = []

                def __init__(self, pipeline_config):
                    self.pipeline_config = pipeline_config
                    self.__class__.received_indices = list(pipeline_config["sample_indices"])

                def run(self, on_sample_completed):
                    for index in self.pipeline_config["sample_indices"]:
                        level = self.pipeline_config["difficulty_plan"][index]
                        on_sample_completed(
                            index,
                            {"sample_id": f"generated_{index}", "difficulty_level": level},
                            {},
                            {},
                        )
                    return {
                        "quality_report": {
                            **PASSED_REPORT,
                            "sample_count": len(self.pipeline_config["sample_indices"]),
                        },
                        "discard_report": {},
                        "discard_reason_samples": {},
                    }

            with (
                patch.object(generator, "load_seed_pools", return_value=([{"id": "synthetic"}], [])),
                patch.object(
                    generator,
                    "filter_seed_pools",
                    side_effect=lambda harmful, harmless, generation: (harmful, harmless),
                ),
                patch.object(generator, "import_skill_pipeline", return_value=FakePipeline),
            ):
                manifest = generator.run_generation(config_path)

            rows = generator.read_jsonl_rows(samples_path)
            self.assertEqual(FakePipeline.received_indices, [1, 3])
            self.assertEqual([row["generation_index"] for row in rows], [1, 3, 2, 4])
            self.assertEqual(manifest["total_generated"], 4)
            self.assertNotIn("batch_size", manifest)
            self.assertNotIn("batches", manifest)

    def test_api_preview_returns_latest_twenty_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "samples.jsonl"
            generator.append_jsonl(
                path,
                [{"generation_index": index, "sample_id": f"sample_{index}"} for index in range(1, 26)],
            )

            rows = ui_backend.read_jsonl_tail(path, 20)

            self.assertEqual(len(rows), 20)
            self.assertEqual(rows[0]["generation_index"], 6)
            self.assertEqual(rows[-1]["generation_index"], 25)

    def test_ui_no_longer_submits_batch_size(self):
        app_source = (UI_ROOT / "app.js").read_text(encoding="utf-8")
        page_source = (UI_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertNotIn("batch_size", app_source)
        self.assertNotIn("batchSize", app_source)
        self.assertNotIn('id="batchSize"', page_source)

    def test_api_rejects_batch_size(self):
        config = {
            "run_id": "legacy_batch_config",
            "generation": {"total_sample_count": 1, "batch_size": 1},
        }

        with self.assertRaisesRegex(ValueError, "batch_size has been removed"):
            ui_backend.create_generation_job(config)


if __name__ == "__main__":
    unittest.main()
