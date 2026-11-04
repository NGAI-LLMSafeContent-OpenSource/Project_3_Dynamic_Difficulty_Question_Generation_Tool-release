#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path
from typing import Any

from generate_benchmark_data import (
    difficulty_counts_total,
    load_json,
    now_iso,
    read_existing_sample_stats,
    resolve_repo_path,
    run_generation,
    write_json,
)


def current_progress(config_path: Path, output_dir_override: str | None) -> tuple[int, int, Path]:
    config = load_json(config_path)
    run_id = str(config.get("run_id", "benchmark_generation"))
    generation = config.get("generation", {})
    total = int(generation.get("total_sample_count", generation.get("sample_count", 10)))
    total = difficulty_counts_total(generation) or total
    output_dir = resolve_repo_path(output_dir_override or config.get("output_dir", f"runs/{run_id}"))
    samples_path = output_dir / "samples.jsonl"
    count, _ = read_existing_sample_stats(samples_path)
    return count, total, output_dir


def write_worker_state(output_dir: Path, payload: dict[str, Any]) -> None:
    path = output_dir / "worker_state.json"
    if "active_sample" not in payload and path.exists():
        previous = load_json(path)
        active_sample = previous.get("active_sample")
        if active_sample:
            payload["active_sample"] = active_sample
            payload.setdefault("discard_counts", previous.get("discard_counts", {}))
            if payload.get("status") == "completed":
                payload.setdefault("phase", "任务已完成")
                payload.setdefault("message", "保留最近一条样本流水线记录")
            elif payload.get("status") == "failed":
                payload.setdefault("phase", "任务失败")
                payload.setdefault("message", "保留失败前最近一条样本流水线记录")
            elif payload.get("status") == "retrying":
                payload.setdefault("phase", previous.get("phase", "重试中"))
                payload.setdefault("message", previous.get("message", "保留最近一条样本流水线记录"))
    write_json(path, payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run generation with automatic resume after transient failures.")
    parser.add_argument("--config", required=True, type=Path, help="Generation config JSON.")
    parser.add_argument("--output-dir", help="Override config output_dir.")
    parser.add_argument("--retry-sleep", type=int, default=30)
    parser.add_argument("--max-attempts", type=int, default=100)
    parser.add_argument("--max-stalled-attempts", type=int, default=10)
    args = parser.parse_args()

    attempt = 0
    stalled_attempts = 0
    last_count = -1
    while attempt < args.max_attempts:
        count, total, output_dir = current_progress(args.config, args.output_dir)
        if count >= total:
            write_worker_state(
                output_dir,
                {
                    "status": "completed",
                    "updated_at": now_iso(),
                    "generated": count,
                    "total": total,
                    "attempt": attempt,
                },
            )
            print(f"[{now_iso()}] completed generated={count} total={total}", flush=True)
            return

        attempt += 1
        print(f"[{now_iso()}] attempt {attempt} starting generated={count} total={total}", flush=True)
        try:
            manifest = run_generation(args.config, args.output_dir)
            generated = int(manifest.get("total_generated", 0))
            if generated >= total:
                write_worker_state(
                    output_dir,
                    {
                        "status": "completed",
                        "updated_at": now_iso(),
                        "generated": generated,
                        "total": total,
                        "attempt": attempt,
                    },
                )
                print(f"[{now_iso()}] completed generated={generated} total={total}", flush=True)
                return
        except Exception as exc:
            count, total, output_dir = current_progress(args.config, args.output_dir)
            stalled_attempts = stalled_attempts + 1 if count == last_count else 0
            last_count = count
            state = {
                "status": "retrying",
                "updated_at": now_iso(),
                "generated": count,
                "total": total,
                "attempt": attempt,
                "stalled_attempts": stalled_attempts,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
            write_worker_state(output_dir, state)
            print(json.dumps(state, ensure_ascii=False), flush=True)
            if stalled_attempts >= args.max_stalled_attempts:
                raise RuntimeError(f"generation stalled after {stalled_attempts} attempts") from exc
            time.sleep(args.retry_sleep)

    count, total, output_dir = current_progress(args.config, args.output_dir)
    write_worker_state(
        output_dir,
        {
            "status": "failed",
            "updated_at": now_iso(),
            "generated": count,
            "total": total,
            "attempt": attempt,
        },
    )
    raise RuntimeError(f"generation did not complete after {args.max_attempts} attempts")


if __name__ == "__main__":
    main()
