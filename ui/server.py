#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = Path(__file__).resolve().parent

from backend import (  # noqa: E402
    ApiError,
    api_health,
    build_job_artifacts_archive,
    create_generation_job,
    example_samples,
    generation_options,
    job_samples,
    job_status,
    list_generation_jobs,
    resume_generation_job,
    seed_topics,
    stop_generation_job,
)


class QuestionAgentHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(UI_ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        try:
            if route == "/api/health":
                self.send_json(api_health())
                return
            if route == "/api/generation/options":
                self.send_json(generation_options())
                return
            if route == "/api/example-samples":
                self.send_json(example_samples())
                return
            if route == "/api/seed-topics":
                query = parse_qs(parsed.query)
                path = query.get("path", ["seed_data/harmful_zh_17class_v1"])[0]
                self.send_json(seed_topics(path))
                return
            if route == "/api/generation/jobs":
                self.send_json(list_generation_jobs())
                return
            if route.startswith("/api/generation/jobs/") and route.endswith(
                "/artifacts/download"
            ):
                job_id = route.removeprefix("/api/generation/jobs/").removesuffix(
                    "/artifacts/download"
                )
                archive = build_job_artifacts_archive(job_id)
                try:
                    self.send_file(
                        archive.path,
                        content_type="application/zip",
                        filename=archive.filename,
                    )
                finally:
                    archive.path.unlink(missing_ok=True)
                return
            if route.startswith("/api/generation/jobs/") and route.endswith("/samples"):
                job_id = route.removeprefix("/api/generation/jobs/").removesuffix("/samples")
                query = parse_qs(parsed.query)
                limit = int(query["limit"][0]) if "limit" in query else None
                self.send_json(job_samples(job_id, limit))
                return
            if route.startswith("/api/generation/jobs/"):
                self.send_json(job_status(route.removeprefix("/api/generation/jobs/")))
                return
            super().do_GET()
        except ApiError as exc:
            self.send_json(exc.to_payload(), status=exc.status)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        try:
            if route in {"/api/generate", "/api/generation/jobs"}:
                request = self.read_json_body()
                config = request.get("config", request)
                if not isinstance(config, dict):
                    raise ValueError("request config must be an object")
                self.send_json(create_generation_job(config), status=202)
                return
            if route.startswith("/api/generation/jobs/") and route.endswith("/stop"):
                job_id = route.removeprefix("/api/generation/jobs/").removesuffix("/stop")
                self.send_json(stop_generation_job(job_id))
                return
            if route.startswith("/api/generation/jobs/") and route.endswith("/resume"):
                job_id = route.removeprefix("/api/generation/jobs/").removesuffix("/resume")
                self.send_json(resume_generation_job(job_id), status=202)
                return
            self.send_error(404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("request body must be a JSON object")
        return data

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path, *, content_type: str, filename: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                self.wfile.write(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the dynamic difficulty question generation Agent UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), QuestionAgentHandler)
    print(f"Serving dynamic difficulty question generation Agent UI at http://{args.host}:{args.port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
