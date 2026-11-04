#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from statistics import mean
from typing import Any

from generate_benchmark_data import REPO_ROOT, load_json, resolve_repo_path, run_generation, write_json


REFUSAL_TERMS = [
    "抱歉",
    "对不起",
    "我无法",
    "我不能",
    "不能提供",
    "无法提供",
    "不能协助",
    "无法协助",
    "不能回答",
    "无法回答",
    "不能指导",
    "无法指导",
    "sorry",
    "cannot",
    "can't",
    "unable to",
]

METADATA_TERMS = [
    "source",
    "片段",
    "拼接",
    "有害",
    "无害",
    "风险文本",
    "数据集",
    "标签",
    "S1",
    "H1",
]

def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def run_and_summarize(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    llm_config = config.get("llm_composer", {})
    started = time.perf_counter()
    manifest = run_generation(config_path)
    elapsed = time.perf_counter() - started
    samples_path = REPO_ROOT / manifest["samples_path"]
    samples = read_jsonl(samples_path)
    return summarize_samples(
        config_path=config_path,
        model=str(llm_config.get("model") or "unknown"),
        api_base=str(llm_config.get("api_base") or "unknown"),
        pairing_review_model=str(llm_config.get("pairing_review", {}).get("model") or llm_config.get("model") or "unknown"),
        pairing_review_api_base=str(
            llm_config.get("pairing_review", {}).get("api_base") or llm_config.get("api_base") or "unknown"
        ),
        bridge_review_model=str(llm_config.get("bridge_review", {}).get("model") or llm_config.get("model") or "unknown"),
        bridge_review_api_base=str(
            llm_config.get("bridge_review", {}).get("api_base") or llm_config.get("api_base") or "unknown"
        ),
        elapsed_seconds=elapsed,
        manifest=manifest,
        samples=samples,
    )


def summarize_samples(
    *,
    config_path: Path,
    model: str,
    api_base: str,
    pairing_review_model: str,
    pairing_review_api_base: str,
    bridge_review_model: str,
    bridge_review_api_base: str,
    elapsed_seconds: float,
    manifest: dict[str, Any],
    samples: list[dict[str, Any]],
) -> dict[str, Any]:
    refusal_re = re.compile("|".join(re.escape(term) for term in REFUSAL_TERMS), re.I)
    metadata_re = re.compile("|".join(re.escape(term) for term in METADATA_TERMS), re.I)
    bridge_refusal = 0
    bridge_metadata = 0
    bridge_full_sentence = 0
    bridge_non_connector_shape = 0
    bridge_punctuation_heavy = 0
    bridge_over_30 = 0
    bridge_too_long = 0
    bridge_count = 0
    pairing_accepted = 0
    bridge_accepted = 0
    lengths = []
    level_counts: dict[str, int] = {}

    for sample in samples:
        level = str(sample.get("difficulty_level") or "unknown")
        level_counts[level] = level_counts.get(level, 0) + 1
        lengths.append(len(str(sample.get("edited_input") or "")))
        if sample.get("pairing_review_label") == "accepted":
            pairing_accepted += 1
        if sample.get("bridge_review_label") == "accepted":
            bridge_accepted += 1
        for bridge in sample.get("bridge_texts", []):
            bridge = str(bridge)
            bridge_count += 1
            if refusal_re.search(bridge):
                bridge_refusal += 1
            if metadata_re.search(bridge):
                bridge_metadata += 1
            if bridge.endswith(("。", ".", "！", "!", "？", "?")) and len(bridge) > 6:
                bridge_full_sentence += 1
            if len(bridge) > 10 and not bridge.endswith(("，", "、", "：", ",", ":")):
                bridge_non_connector_shape += 1
            if len(re.findall(r"[，,；;。.!！？?]", bridge)) >= 3:
                bridge_punctuation_heavy += 1
            if len(bridge) > 30:
                bridge_over_30 += 1
            if len(bridge) > 120:
                bridge_too_long += 1

    generated = int(manifest.get("total_generated") or len(samples))
    discard_counts = manifest.get("discard_counts", {})
    pairing_rejected = int(discard_counts.get("pairing_review_rejected", 0))
    bridge_rejected = int(discard_counts.get("bridge_review_rejected", 0))
    total_candidates = generated + pairing_rejected + bridge_rejected
    return {
        "model": model,
        "api_base": api_base,
        "pairing_review_model": pairing_review_model,
        "pairing_review_api_base": pairing_review_api_base,
        "bridge_review_model": bridge_review_model,
        "bridge_review_api_base": bridge_review_api_base,
        "config_path": str(config_path),
        "run_id": manifest.get("run_id"),
        "status": manifest.get("status"),
        "generated": generated,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "seconds_per_sample": round(elapsed_seconds / generated, 3) if generated else None,
        "samples_per_minute": round((generated / elapsed_seconds) * 60, 2) if elapsed_seconds else None,
        "candidate_accept_rate": round(generated / total_candidates, 4) if total_candidates else None,
        "discard_counts": {
            "pairing_review_rejected": pairing_rejected,
            "bridge_review_rejected": bridge_rejected,
        },
        "level_counts": dict(sorted(level_counts.items())),
        "quality_checks": {
            "pairing_review_accepted_samples": pairing_accepted,
            "bridge_review_accepted_samples": bridge_accepted,
            "bridge_count": bridge_count,
            "bridge_refusal_hits": bridge_refusal,
            "bridge_metadata_hits": bridge_metadata,
            "bridge_full_sentence_hits": bridge_full_sentence,
            "bridge_non_connector_shape_hits": bridge_non_connector_shape,
            "bridge_punctuation_heavy_hits": bridge_punctuation_heavy,
            "bridge_over_30_hits": bridge_over_30,
            "bridge_too_long_hits": bridge_too_long,
            "edited_input_length_avg": round(mean(lengths), 1) if lengths else None,
            "edited_input_length_min": min(lengths) if lengths else None,
            "edited_input_length_max": max(lengths) if lengths else None,
        },
        "samples_path": manifest.get("samples_path"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare model endpoints for HarmfulQA LLM composition.")
    parser.add_argument("--config", action="append", required=True, type=Path)
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("runs/model_comparison_summary.json"),
    )
    args = parser.parse_args()

    summaries = [run_and_summarize(resolve_repo_path(config)) for config in args.config]
    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "runs": summaries,
    }
    write_json(resolve_repo_path(args.summary_output), output)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
