from __future__ import annotations

import json
import os
import random
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = REPO_ROOT / "agent_framework" / "scripts"
RUNNER_PATH = GENERATOR_PATH / "run_resumable_generation.py"
EXAMPLE_SAMPLES_PATH = REPO_ROOT / "samples" / "samples.jsonl"
if str(GENERATOR_PATH) not in sys.path:
    sys.path.insert(0, str(GENERATOR_PATH))

from generate_benchmark_data import (  # noqa: E402
    domain_topic,
    load_harmful_seed_library,
    load_json,
    read_existing_sample_stats,
    write_json,
)


JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = Lock()

REQUIRED_ARTIFACT_FILES = (
    "samples.jsonl",
    "manifest.json",
    "worker_state.json",
    "generation_config.json",
    "worker.log",
)


class ApiError(RuntimeError):
    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def to_payload(self) -> dict[str, Any]:
        return {"error": self.code, "message": self.message}


@dataclass(frozen=True)
class ArtifactArchive:
    filename: str
    path: Path


def api_health() -> dict[str, Any]:
    with JOBS_LOCK:
        active = sum(1 for job in JOBS.values() if process_running(job.get("process")))
    return {
        "ok": True,
        "active_jobs": active,
        "endpoints": [
            "GET /api/seed-topics?path=<seed_input_path>",
            "GET /api/example-samples",
            "GET /api/generation/options",
            "POST /api/generation/jobs",
            "GET /api/generation/jobs",
            "GET /api/generation/jobs/<job_id>",
            "POST /api/generation/jobs/<job_id>/stop",
            "POST /api/generation/jobs/<job_id>/resume",
            "GET /api/generation/jobs/<job_id>/artifacts/download",
        ],
    }


def example_samples() -> dict[str, Any]:
    samples = read_jsonl(EXAMPLE_SAMPLES_PATH)
    return {"count": len(samples), "samples": samples}


def generation_options() -> dict[str, Any]:
    return {
        "skill_versions": [
            {
                "id": "dynamic_difficulty_question_generation_skill",
                "label": "动态难度出题 skill",
                "path": "skills",
                "supports_harmful_seed_library": True,
                "uses_generated_companions": True,
            }
        ],
        "data_sources": [
            {
                "id": "harmful_seed_library",
                "label": "有害样本 seed 数据",
                "path": "seed_data/harmful_zh_17class_v1",
            },
            {
                "id": "seed_input_json",
                "label": "兼容旧 seed_input JSON",
                "path": "",
            },
        ],
    }


def seed_topics(seed_input_path: str) -> dict[str, Any]:
    path = resolve_repo_path(seed_input_path)
    if path.is_dir():
        harmful_rows = load_harmful_seed_library(
            {
                "harmful_seed_library": {
                    "path": str(path.relative_to(REPO_ROOT)),
                    "sources": [],
                    "deduplicate": True,
                }
            }
        )
        payload = {"harmful_pool": harmful_rows, "harmless_pool": []}
    else:
        payload = load_json(path)
    domains: dict[str, dict[str, Any]] = {}
    for pool_name in ("harmful_pool", "harmless_pool"):
        for row in payload.get(pool_name, []):
            if not isinstance(row, dict):
                continue
            domain = str(row.get("domain") or "").strip()
            if not domain:
                continue
            topic = domain_topic(domain)
            record = domains.setdefault(
                domain,
                {
                    "domain": domain,
                    "topic": topic,
                    "harmful_count": 0,
                    "harmless_count": 0,
                },
            )
            key = "harmful_count" if pool_name == "harmful_pool" else "harmless_count"
            record[key] += 1

    topic_rows: dict[str, dict[str, Any]] = {}
    for domain in domains.values():
        topic = domain["topic"]
        row = topic_rows.setdefault(
            topic,
            {
                "topic": topic,
                "domain_count": 0,
                "harmful_count": 0,
                "harmless_count": 0,
            },
        )
        row["domain_count"] += 1
        row["harmful_count"] += domain["harmful_count"]
        row["harmless_count"] += domain["harmless_count"]

    return {
        "seed_input_path": str(path.relative_to(REPO_ROOT)),
        "topics": sorted(topic_rows.values(), key=lambda item: item["topic"]),
        "domains": sorted(domains.values(), key=lambda item: item["domain"]),
    }


def create_generation_job(config: dict[str, Any]) -> dict[str, Any]:
    run_id = safe_run_id(str(config.get("run_id") or f"ui_generation_{int(time.time())}"))
    config["run_id"] = run_id
    generation = config.setdefault("generation", {})
    if "batch_size" in generation:
        raise ValueError("generation.batch_size has been removed; use llm_composer.concurrency")
    generation["resume"] = True
    random_seed = normalize_random_seed(generation.get("random_seed"))
    generation["random_seed"] = random_seed
    generation["match_offset_base"] = random.Random(random_seed).randint(0, 10_000_000)
    llm_composer = config.setdefault("llm_composer", {})
    llm_composer["enabled"] = True
    bridge_review = llm_composer.setdefault("bridge_review", {})
    bridge_review["enabled"] = True
    output_dir = config.get("output_dir") or f"runs/{run_id}"
    output_path = resolve_repo_path(output_dir)
    with JOBS_LOCK:
        existing = JOBS.get(run_id)
        if existing and process_running(existing.get("process")):
            raise ValueError(f"job already running: {run_id}")
        if output_path.exists():
            shutil.rmtree(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        config["output_dir"] = str(output_path.relative_to(REPO_ROOT))
        config_path = output_path / "generation_config.json"
        write_json(config_path, config)
        job = launch_job(run_id, config_path, output_path)
        JOBS[run_id] = job
    return job_status(run_id)


def list_generation_jobs() -> dict[str, Any]:
    with JOBS_LOCK:
        ids = sorted(JOBS)
    return {"jobs": [job_status(job_id) for job_id in ids]}


def job_status(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise KeyError(f"unknown job: {job_id}")

    output_path = Path(job["output_dir"])
    config = read_json_if_exists(Path(job["config_path"]))
    generation = config.get("generation", {})
    manifest = read_json_if_exists(output_path / "manifest.json")
    worker_state = read_json_if_exists(output_path / "worker_state.json")
    samples_path = output_path / "samples.jsonl"
    generated, level_counts = read_existing_sample_stats(samples_path)
    total = infer_total(job.get("config_path"), manifest)
    proc = job.get("process")
    running = process_running(proc)
    status = "running" if running else status_from_files(generated, total, worker_state, manifest)
    progress = round((generated / total) * 100, 2) if total else 0
    return {
        "job_id": job_id,
        "status": status,
        "running": running,
        "pid": proc.pid if running else None,
        "generated": generated,
        "total": total,
        "progress": progress,
        "difficulty_level_counts": level_counts,
        "output_dir": str(output_path.relative_to(REPO_ROOT)),
        "config_path": str(Path(job["config_path"]).relative_to(REPO_ROOT)),
        "samples_path": str(samples_path.relative_to(REPO_ROOT)),
        "random_seed": generation.get("random_seed"),
        "match_offset_base": generation.get("match_offset_base"),
        "manifest": manifest,
        "worker_state": worker_state,
        "log_tail": tail_text(output_path / "worker.log", 60),
        "samples": read_jsonl_tail(samples_path, 20),
    }


def job_samples(job_id: str, limit: int | None = None) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise KeyError(f"unknown job: {job_id}")
    samples_path = Path(job["output_dir"]) / "samples.jsonl"
    samples = read_jsonl(samples_path)
    if limit is not None and limit >= 0:
        samples = samples[-limit:]
    return {
        "job_id": job_id,
        "samples_path": str(samples_path.relative_to(REPO_ROOT)),
        "count": len(samples),
        "samples": samples,
    }


def build_job_artifacts_archive(job_id: str) -> ArtifactArchive:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise ApiError("job_not_found", f"unknown job: {job_id}", 404)

    status = job_status(job_id)
    if status.get("running") or status.get("status") != "completed":
        raise ApiError("artifacts_not_ready", "job artifacts are not ready", 409)

    output_path = Path(job["output_dir"])
    missing = [
        name for name in REQUIRED_ARTIFACT_FILES if not (output_path / name).is_file()
    ]
    if missing:
        raise ApiError(
            "artifact_packaging_failed",
            f"required artifact files are missing: {', '.join(missing)}",
            500,
        )

    archive_path = create_artifacts_archive_file(job_id, output_path)
    return ArtifactArchive(filename=f"{job_id}_artifacts.zip", path=archive_path)


def create_artifacts_archive_file(job_id: str, output_path: Path) -> Path:
    archive_file = tempfile.NamedTemporaryFile(
        prefix=f"{job_id}_artifacts_",
        suffix=".zip",
        delete=False,
    )
    archive_path = Path(archive_file.name)
    archive_file.close()
    try:
        with zipfile.ZipFile(
            archive_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in REQUIRED_ARTIFACT_FILES:
                archive.write(output_path / name, arcname=name)
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise
    return archive_path


def stop_generation_job(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise KeyError(f"unknown job: {job_id}")
    proc = job.get("process")
    if process_running(proc):
        terminate_process(proc)
    output_path = Path(job["output_dir"])
    generated, _ = read_existing_sample_stats(output_path / "samples.jsonl")
    state_path = output_path / "worker_state.json"
    previous_state = read_json_if_exists(state_path)
    state = {
        "status": "stopped",
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "generated": generated,
        "job_id": job_id,
    }
    if previous_state.get("active_sample"):
        state["phase"] = "任务已停止"
        state["message"] = "保留停止前最近一条样本流水线记录"
        state["active_sample"] = previous_state["active_sample"]
        state["discard_counts"] = previous_state.get("discard_counts", {})
    write_json(
        state_path,
        state,
    )
    return job_status(job_id)


def resume_generation_job(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise KeyError(f"unknown job: {job_id}")
        if process_running(job.get("process")):
            return job_status(job_id)
        JOBS[job_id] = launch_job(job_id, Path(job["config_path"]), Path(job["output_dir"]))
    return job_status(job_id)


def launch_job(run_id: str, config_path: Path, output_path: Path) -> dict[str, Any]:
    log_path = output_path / "worker.log"
    log_handle = log_path.open("a", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, str(RUNNER_PATH), "--config", str(config_path)],
        cwd=REPO_ROOT,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return {
        "job_id": run_id,
        "process": process,
        "config_path": config_path,
        "output_dir": output_path,
        "started_at": time.time(),
    }


def infer_total(config_path: str | Path | None, manifest: dict[str, Any]) -> int:
    if manifest.get("total_requested"):
        return int(manifest["total_requested"])
    if config_path and Path(config_path).exists():
        config = load_json(Path(config_path))
        generation = config.get("generation", {})
        counts = generation.get("difficulty_counts")
        if isinstance(counts, dict):
            total = sum(max(0, int(counts.get(level, 0))) for level in ("H1", "H2", "H3", "H4"))
            if total:
                return total
        return int(generation.get("total_sample_count", generation.get("sample_count", 0)))
    return 0


def status_from_files(
    generated: int,
    total: int,
    worker_state: dict[str, Any],
    manifest: dict[str, Any],
) -> str:
    if total and generated >= total:
        return "completed"
    if worker_state.get("status"):
        return str(worker_state["status"])
    if manifest.get("status"):
        return str(manifest["status"])
    return "idle"


def process_running(process: Any) -> bool:
    return bool(process and process.poll() is None)


def terminate_process(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=8)


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    resolved = path.resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise ValueError(f"path is outside repository: {value}")
    return resolved


def safe_run_id(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_.-]+", "_", value.strip())
    return cleaned or f"ui_generation_{int(time.time())}"


def normalize_random_seed(value: Any) -> int:
    if value is None or str(value).strip() == "":
        return random.SystemRandom().randint(0, 2_147_483_647)
    seed = int(value)
    if seed < 0:
        raise ValueError("generation.random_seed must be a non-negative integer")
    return seed


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_json(path)


def read_jsonl_tail(path: Path, limit: int) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    return rows[-limit:]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()
        for line_index, line in enumerate(lines):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    if line_index != len(lines) - 1:
                        raise
    return rows


def tail_text(path: Path, max_lines: int) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-max_lines:]
