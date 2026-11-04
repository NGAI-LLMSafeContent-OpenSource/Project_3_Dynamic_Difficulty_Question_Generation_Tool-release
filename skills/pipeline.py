from __future__ import annotations

import json
import os
import random
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import replace
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from skills.common.models import CandidateText, now_iso
from skills.difficulty_assignment_skill.difficulty import DifficultyStrategyAllocator
from skills.harmless_content_generation_skill.companion_generator import (
    HarmfulAnchorRejected,
    HarmlessCompanionGenerator,
    HarmlessCompanionRejected,
)
from skills.harmful_sample_collection_skill.buffer_pool import BufferPoolManager
from skills.harmful_sample_collection_skill.extractors import HarmfulIntentExtractor, HarmlessIntentExtractor
from skills.model_guided_output_splicing_skill.assembler import DatasetAssembler
from skills.model_guided_output_splicing_skill.composer import (
    BridgeReviewRejected,
    PairingReviewRejected,
    build_output_composer,
)
from skills.quality_validation_skill.final_guard import FinalGuard, FinalGuardRejected
from skills.quality_validation_skill.quality_gate import QualityGate
from skills.risk_classification_skill.label_engine import SafetyLabelEngine
from skills.span_formatting_recording_skill.span_recorder import SpanRecorder


class SpanBackfillRejected(ValueError):
    pass


class DynamicDifficultyQuestionGenerationPipeline:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.language = str(config.get("language", "zh"))
        self.metric_targets = list(config.get("metric_targets", ["edit_success", "harmless_retention"]))
        if not self.metric_targets:
            raise ValueError("metric_targets cannot be empty")
        unsupported = [target for target in self.metric_targets if target not in {"edit_success", "harmless_retention"}]
        if unsupported:
            raise ValueError(f"unsupported metric_targets: {unsupported}")
        self.sample_mode = str(config.get("sample_mode", "paired_mixed"))
        self.data_origin_modes = list(config.get("data_origin_modes", ["splice_constructed"]))
        self.parallelism = max(1, int(config.get("llm_composer", {}).get("concurrency", 1)))
        self.discard_retry_limit = max(1, int(config.get("llm_composer", {}).get("discard_retry_limit", 50)))
        self.discard_count_base = {
            str(key): int(value) for key, value in dict(config.get("discard_count_base") or {}).items()
        }
        self.sample_offset = int(config.get("sample_offset", 0))
        sample_count = int(config.get("sample_count", 10))
        configured_indices = config.get("sample_indices")
        self.uses_global_indices = isinstance(configured_indices, list)
        self.sample_indices = (
            [int(index) for index in configured_indices]
            if self.uses_global_indices
            else list(range(self.sample_offset, self.sample_offset + sample_count))
        )
        self.total_sample_count = int(config.get("total_sample_count", sample_count))
        self.match_offset_base = int(config.get("match_offset_base", 0))
        self.difficulty_plan = list(config.get("difficulty_plan") or [])
        self.discard_counts = {
            "pairing_review_rejected": 0,
            "bridge_review_rejected": 0,
            "span_backfill_rejected": 0,
            "harmless_companion_rejected": 0,
            "harmful_anchor_rejected": 0,
            "final_guard_rejected": 0,
            "sample_resampled_after_retry_limit": 0,
        }
        self.discard_reason_samples = {
            "pairing_review_rejected": [],
            "bridge_review_rejected": [],
            "span_backfill_rejected": [],
            "harmless_companion_rejected": [],
            "harmful_anchor_rejected": [],
            "final_guard_rejected": [],
            "sample_resampled_after_retry_limit": [],
        }
        self.discard_lock = Lock()
        self.progress_lock = Lock()
        progress_state_path = str(config.get("progress_state_path") or "").strip()
        self.progress_state_path = Path(progress_state_path) if progress_state_path else None

        self.harmful_extractor = HarmfulIntentExtractor()
        self.harmless_extractor = HarmlessIntentExtractor()
        self.pool_manager = BufferPoolManager()
        self.label_engine = SafetyLabelEngine()
        self.difficulty_allocator = DifficultyStrategyAllocator(config.get("difficulty_sequence"))
        self.companion_generator = HarmlessCompanionGenerator(config.get("harmless_companion_generator", {}))
        self.composer = build_output_composer(config.get("llm_composer", {}))
        self.span_recorder = SpanRecorder()
        self.final_guard = FinalGuard(config)
        self.assembler = DatasetAssembler()
        self.quality_gate = QualityGate()

    def run(
        self,
        on_sample_completed: Callable[[int, dict[str, Any], dict[str, int], dict[str, list[str]]], None]
        | None = None,
    ) -> dict[str, Any]:
        harmful_items = [
            normalize_harmful_domain(item)
            for item in self.harmful_extractor.run(self.config.get("harmful_pool", []), language=self.language)
        ]
        harmless_items: list[CandidateText] = []
        pool = self.pool_manager.run(harmful_items, harmless_items)
        self.label_engine.validate_pool(pool)

        samples: list[dict[str, Any]] = []
        if self.sample_mode == "harmful_only_baseline":
            for index in self.sample_indices:
                sample = self._build_edit_success_sample(pool, index)
                self._complete_sample(index, sample, on_sample_completed)
                samples.append(sample)
        else:
            if self.parallelism == 1:
                for index in self.sample_indices:
                    sample = self._build_paired_edit_sample_with_retries(pool, index, self.total_sample_count)
                    self._complete_sample(index, sample, on_sample_completed)
                    samples.append(sample)
            else:
                samples = self._build_paired_edit_samples_parallel(pool, on_sample_completed)

        return {
            "samples": samples,
            "source_report": build_source_report(pool),
            "discard_report": self._discard_counts_snapshot(),
            "discard_reason_samples": self._discard_reasons_snapshot(),
            "quality_report": self.quality_gate.run(samples),
        }

    def _build_edit_success_sample(self, pool: dict[str, list[CandidateText]], index: int) -> dict[str, Any]:
        harmful_candidates = [item for item in pool["harmful_pool"] if item.language == self.language]
        if not harmful_candidates:
            raise ValueError(f"no harmful candidates for language={self.language}")
        global_index = index
        harmful_item = harmful_candidates[global_index % len(harmful_candidates)]
        difficulty = self.difficulty_allocator.for_edit_success(global_index)
        return self.assembler.build_edit_success(
            sample_id=f"edit_success_{global_index + 1:06d}",
            harmful_item=harmful_item,
            difficulty=difficulty,
        )

    def _build_paired_edit_sample(
        self,
        pool: dict[str, list[CandidateText]],
        index: int,
        *,
        retry_index: int = 0,
        retry_stride: int = 1,
    ) -> dict[str, Any]:
        global_index = index
        match_offset = self.match_offset_base + global_index + retry_index * retry_stride + retry_index * retry_index * 17
        if self.difficulty_plan:
            difficulty_index = global_index if self.uses_global_indices else global_index - self.sample_offset
            difficulty = self.difficulty_allocator.for_level(str(self.difficulty_plan[difficulty_index]))
        else:
            difficulty = self.difficulty_allocator.for_retention(match_offset)
        harmful_items = self._select_harmful_items(
            pool,
            language=self.language,
            harmful_count=difficulty["harmful_count"],
            difficulty_strategy=difficulty["difficulty_strategy"],
            offset=match_offset,
        )
        match = {
            "harmful_items": harmful_items,
            "harmless_items": [],
            "coherence_label": "same_risk_category_harmful_anchor",
            "coherence_reason": f"同一风险类别有害 seed 采样：{harmful_items[0].domain}",
        }
        sample_state = {
            "sample_id": f"paired_edit_{global_index + 1:06d}",
            "global_index": global_index + 1,
            "local_index": global_index + 1,
            "difficulty_level": difficulty["difficulty_level"],
            "difficulty_strategy": difficulty["difficulty_strategy"],
            "domain": harmful_items[0].domain,
            "retry": retry_index + 1,
            "match_offset": match_offset,
            "selected_sources": [
                *[source_preview(item, "harmful") for item in harmful_items],
            ],
            "checks": [
                {
                    "name": "同风险类别有害 seed 筛选",
                    "status": "passed",
                    "result": match["coherence_reason"],
                }
            ],
        }
        self._write_progress(
            phase="已选中候选 seed",
            message="准备生成同主题无害 companion",
            active_sample=sample_state,
        )

        def progress_hook(event: dict[str, Any]) -> None:
            active_sample = dict(sample_state)
            event_sample = event.get("active_sample", {})
            active_sample.update(event_sample)
            if event_sample.get("checks"):
                active_sample["checks"] = [*sample_state["checks"], *event_sample["checks"]]
            self._write_progress(
                phase=str(event.get("phase") or "处理中"),
                message=str(event.get("message") or ""),
                active_sample=active_sample,
            )

        harmless_items = self.companion_generator.run(
            harmful_items=harmful_items,
            harmless_count=difficulty["harmless_count"],
            difficulty_strategy=difficulty["difficulty_strategy"],
            variant_seed=match_offset,
            progress_hook=progress_hook,
        )
        match["harmless_items"] = harmless_items
        sample_state["selected_sources"] = [
            *[source_preview(item, "harmful") for item in harmful_items],
            *[source_preview(item, "harmless") for item in harmless_items],
        ]

        composed = self.composer.run(
            harmful_texts=[item.text for item in harmful_items],
            harmless_texts=[item.text for item in harmless_items],
            domain=harmful_items[0].domain,
            difficulty_strategy=difficulty["difficulty_strategy"],
            interleaving=difficulty["interleaving"],
            variant_seed=match_offset,
            progress_hook=progress_hook,
        )
        harmful_texts = [item.text for item in harmful_items]
        harmless_texts = [item.text for item in harmless_items]
        inserted_harmful_texts = list(composed.get("inserted_harmful_texts") or harmful_texts)
        inserted_harmless_texts = list(composed.get("inserted_harmless_texts") or harmless_texts)
        try:
            spans = self.span_recorder.run(
                edited_input=composed["edited_input"],
                harmful_texts=inserted_harmful_texts,
                harmless_texts=inserted_harmless_texts,
            )
        except ValueError as exc:
            raise SpanBackfillRejected(str(exc)) from exc
        self._write_progress(
            phase="最终 Guard 判定",
            message="正在确认最终拼接文本不是 Safe",
            active_sample={
                **sample_state,
                "checks": [
                    *sample_state["checks"],
                    {"name": "最终 Guard", "status": "running", "result": self.final_guard.client.model},
                ],
            },
        )
        final_guard = self.final_guard.run(composed["edited_input"])
        composed["final_guard_label"] = final_guard["label"]
        composed["final_guard_categories"] = final_guard["categories"]
        sample = self.assembler.build_paired_edit(
            sample_id=f"paired_edit_{global_index + 1:06d}",
            match=match,
            difficulty=difficulty,
            composed=composed,
            spans=spans,
        )
        final_state = dict(sample_state)
        final_state.update(
            {
                "checks": [
                    *sample_state["checks"],
                    {
                        "name": "拼接计划生成",
                        "status": sample.get("pairing_review_label") or "passed",
                        "result": sample.get("pairing_review_reason") or "accepted",
                    },
                    {
                        "name": "衔接审核",
                        "status": sample.get("bridge_review_label") or "passed",
                        "result": sample.get("bridge_review_reason") or "accepted",
                    },
                    {
                        "name": "span 回填",
                        "status": "passed",
                        "result": f"{len(sample['harmful_spans'])}H/{len(sample['harmless_spans'])}S",
                    },
                    {
                        "name": "最终 Guard",
                        "status": "passed",
                        "result": sample.get("final_guard_label") or "not Safe",
                    },
                ],
                "bridge_texts": sample.get("bridge_texts", []),
                "source_boundary_edits": sample.get("source_boundary_edits", []),
            }
        )
        self._write_progress(
            phase="样本已通过检查",
            message="样本检查完成，等待写入结果文件",
            active_sample=final_state,
        )
        return sample

    def _build_paired_edit_sample_with_retries(
        self,
        pool: dict[str, list[CandidateText]],
        index: int,
        sample_count: int,
    ) -> dict[str, Any]:
        last_error = None
        retry_block = 0
        while True:
            for retry_index in range(self.discard_retry_limit):
                effective_retry_index = retry_block * self.discard_retry_limit + retry_index
                try:
                    return self._build_paired_edit_sample(
                        pool,
                        index,
                        retry_index=effective_retry_index,
                        retry_stride=sample_count,
                    )
                except PairingReviewRejected as exc:
                    self._record_discard("pairing_review_rejected", str(exc))
                    last_error = exc
                    self._write_progress(
                        phase="候选被丢弃",
                        message=str(exc),
                        active_sample={
                            "sample_id": f"paired_edit_{index + 1:06d}",
                            "local_index": index + 1,
                            "retry": effective_retry_index + 1,
                            "checks": [{"name": "拼接计划生成", "status": "rejected", "result": str(exc)}],
                        },
                    )
                except BridgeReviewRejected as exc:
                    self._record_discard("bridge_review_rejected", str(exc))
                    last_error = exc
                    self._write_progress(
                        phase="候选被丢弃",
                        message=str(exc),
                        active_sample={
                            "sample_id": f"paired_edit_{index + 1:06d}",
                            "local_index": index + 1,
                            "retry": effective_retry_index + 1,
                            "checks": [{"name": "衔接审核", "status": "rejected", "result": str(exc)}],
                        },
                    )
                except SpanBackfillRejected as exc:
                    self._record_discard("span_backfill_rejected", str(exc))
                    last_error = exc
                    self._write_progress(
                        phase="候选被丢弃",
                        message=str(exc),
                        active_sample={
                            "sample_id": f"paired_edit_{index + 1:06d}",
                            "local_index": index + 1,
                            "retry": effective_retry_index + 1,
                            "checks": [{"name": "span 回填", "status": "rejected", "result": str(exc)}],
                        },
                    )
                except HarmlessCompanionRejected as exc:
                    self._record_discard("harmless_companion_rejected", str(exc))
                    last_error = exc
                    self._write_progress(
                        phase="候选被丢弃",
                        message=str(exc),
                        active_sample={
                            "sample_id": f"paired_edit_{index + 1:06d}",
                            "local_index": index + 1,
                            "retry": effective_retry_index + 1,
                            "checks": [{"name": "无害 companion", "status": "rejected", "result": str(exc)}],
                        },
                    )
                except HarmfulAnchorRejected as exc:
                    self._record_discard("harmful_anchor_rejected", str(exc))
                    last_error = exc
                    self._write_progress(
                        phase="候选被丢弃",
                        message=str(exc),
                        active_sample={
                            "sample_id": f"paired_edit_{index + 1:06d}",
                            "local_index": index + 1,
                            "retry": effective_retry_index + 1,
                            "checks": [{"name": "有害 anchor 选择", "status": "rejected", "result": str(exc)}],
                        },
                    )
                except FinalGuardRejected as exc:
                    self._record_discard("final_guard_rejected", str(exc))
                    last_error = exc
                    self._write_progress(
                        phase="候选被丢弃",
                        message=str(exc),
                        active_sample={
                            "sample_id": f"paired_edit_{index + 1:06d}",
                            "local_index": index + 1,
                            "retry": effective_retry_index + 1,
                            "checks": [{"name": "最终 Guard", "status": "rejected", "result": str(exc)}],
                        },
                    )
            retry_block += 1
            message = f"candidate retry limit reached for index={index}; resampling sample: {last_error}"
            self._record_discard("sample_resampled_after_retry_limit", message)
            self._write_progress(
                phase="样本重新采样",
                message=message,
                active_sample={
                    "sample_id": f"paired_edit_{index + 1:06d}",
                    "local_index": index + 1,
                    "retry": retry_block * self.discard_retry_limit,
                    "checks": [{"name": "候选重采样", "status": "resampling", "result": str(last_error)}],
                },
            )

    def _select_harmful_items(
        self,
        pool: dict[str, list[CandidateText]],
        *,
        language: str,
        harmful_count: int,
        difficulty_strategy: str,
        offset: int,
    ) -> list[CandidateText]:
        domains = sorted({item.domain for item in pool["harmful_pool"] if item.language == language})
        rng = random.Random(offset)
        rotated_domains = list(domains)
        rng.shuffle(rotated_domains)
        last_error = None
        for domain in rotated_domains:
            harmful_items = sorted(
                [item for item in pool["harmful_pool"] if item.language == language and item.domain == domain],
                key=lambda item: item.item_id,
            )
            if len(harmful_items) >= harmful_count:
                window_count = min(
                    len(harmful_items),
                    max(harmful_count, self.companion_generator.harmful_candidate_window),
                )
                candidates = random_take(harmful_items, offset * 2 + 1, window_count)
                try:
                    return self.companion_generator.select_harmful_anchors(
                        candidates=candidates,
                        harmful_count=harmful_count,
                        domain=domain,
                        difficulty_strategy=difficulty_strategy,
                        variant_seed=offset,
                    )
                except HarmfulAnchorRejected as exc:
                    last_error = exc
                    continue
        if last_error is not None:
            raise HarmfulAnchorRejected(str(last_error))
        raise ValueError(f"no harmful seed group for language={language}, harmful_count={harmful_count}")

    def _build_paired_edit_samples_parallel(
        self,
        pool: dict[str, list[CandidateText]],
        on_sample_completed: Callable[[int, dict[str, Any], dict[str, int], dict[str, list[str]]], None]
        | None,
    ) -> list[dict[str, Any]]:
        pending = deque(self.sample_indices)
        results: dict[int, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=self.parallelism) as executor:
            future_to_index = {}
            while pending and len(future_to_index) < self.parallelism:
                index = pending.popleft()
                future = executor.submit(
                    self._build_paired_edit_sample_with_retries,
                    pool,
                    index,
                    self.total_sample_count,
                )
                future_to_index[future] = index
            while future_to_index:
                completed, _ = wait(future_to_index, return_when=FIRST_COMPLETED)
                for future in completed:
                    index = future_to_index.pop(future)
                    sample = future.result()
                    self._complete_sample(index, sample, on_sample_completed)
                    results[index] = sample
                    if pending:
                        next_index = pending.popleft()
                        next_future = executor.submit(
                            self._build_paired_edit_sample_with_retries,
                            pool,
                            next_index,
                            self.total_sample_count,
                        )
                        future_to_index[next_future] = next_index
        return [results[index] for index in sorted(results)]

    def _complete_sample(
        self,
        index: int,
        sample: dict[str, Any],
        callback: Callable[[int, dict[str, Any], dict[str, int], dict[str, list[str]]], None] | None,
    ) -> None:
        report = self.quality_gate.run([sample])
        if any(value != "passed" for key, value in report.items() if key.endswith("_check")):
            raise RuntimeError(f"quality_report failed for sample index {index + 1}: {report}")
        if callback:
            callback(index, sample, self._discard_counts_snapshot(), self._discard_reasons_snapshot())

    def _write_progress(self, *, phase: str, message: str, active_sample: dict[str, Any]) -> None:
        if not self.progress_state_path:
            return
        payload = {
            "status": "running",
            "updated_at": now_iso(),
            "run_id": self.config.get("run_id"),
            "phase": phase,
            "message": message,
            "sample_count": len(self.sample_indices),
            "random_seed": self.config.get("random_seed"),
            "discard_counts": self._total_discard_counts_snapshot(),
            "active_sample": active_sample,
        }
        with self.progress_lock:
            self.progress_state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.progress_state_path.with_suffix(self.progress_state_path.suffix + ".tmp")
            temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary_path, self.progress_state_path)

    def _record_discard(self, category: str, reason: str) -> None:
        with self.discard_lock:
            self.discard_counts[category] += 1
            samples = self.discard_reason_samples[category]
            if len(samples) < 12:
                samples.append(shorten(reason, 240))

    def _discard_counts_snapshot(self) -> dict[str, int]:
        with self.discard_lock:
            return dict(self.discard_counts)

    def _discard_reasons_snapshot(self) -> dict[str, list[str]]:
        with self.discard_lock:
            return {key: list(values) for key, values in self.discard_reason_samples.items()}

    def _total_discard_counts_snapshot(self) -> dict[str, int]:
        current = self._discard_counts_snapshot()
        keys = set(self.discard_count_base) | set(current)
        return {
            key: int(self.discard_count_base.get(key, 0)) + int(current.get(key, 0))
            for key in keys
        }


def source_preview(item: CandidateText, kind: str) -> dict[str, str]:
    return {
        "id": item.item_id,
        "kind": kind,
        "domain": item.domain,
        "preview": shorten(item.text),
    }


def random_take(items: list[CandidateText], seed: int, count: int) -> list[CandidateText]:
    if len(items) < count:
        raise ValueError(f"need {count} items, got {len(items)}")
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    return shuffled[:count]


def normalize_harmful_domain(item: CandidateText) -> CandidateText:
    if not item.risk_category_id:
        return item
    prefix = item.domain.split("：", 1)[0].split(":", 1)[0].strip() if item.domain else "risk"
    if not prefix or prefix == "general":
        prefix = "risk"
    domain = f"{prefix}：{item.risk_category_id}：{item.risk_category}"
    return replace(item, domain=domain)


def shorten(text: str, limit: int = 96) -> str:
    compact = " ".join(str(text).split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "..."


def build_source_report(pool: dict[str, list[CandidateText]]) -> list[dict[str, Any]]:
    rows: dict[tuple[str, str], int] = {}
    for pool_name, items in pool.items():
        for item in items:
            key = (pool_name, item.source_trace)
            rows[key] = rows.get(key, 0) + 1
    return [
        {"pool": pool_name, "source_trace": source_trace, "count": count}
        for (pool_name, source_trace), count in sorted(rows.items())
    ]
