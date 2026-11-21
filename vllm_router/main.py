from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response


DEFAULT_MODEL_MAP = {
    "Qwen3.5-9B": "http://127.0.0.1:8011/v1",
    "Qwen3Guard-Gen-4B": "http://127.0.0.1:8012/v1",
}

app = FastAPI(
    title="Dynamic Difficulty Question Generation vLLM Router",
    version="0.1.0",
    description="Routes OpenAI-compatible chat completion requests to local vLLM workers by model name.",
)


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"status": "ok", "models": sorted(model_map())}


@app.get("/v1/models")
async def list_models(request: Request) -> JSONResponse:
    models = []
    for model_name, api_base in model_map().items():
        models.append({"id": model_name, "object": "model", "owned_by": "local-vllm", "root": model_name})
    return JSONResponse({"object": "list", "data": models})


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    payload = await request.json()
    model_name = str(payload.get("model") or "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="missing model")
    if payload.get("stream") is True:
        raise HTTPException(status_code=400, detail="streaming requests are not supported by this router")

    api_base = model_map().get(model_name)
    if not api_base:
        available = ", ".join(sorted(model_map()))
        raise HTTPException(status_code=404, detail=f"unknown model: {model_name}; available: {available}")

    authorization = request.headers.get("authorization")
    result = await asyncio.to_thread(proxy_json_request, api_base, "/chat/completions", payload, authorization)
    return Response(
        content=result["body"],
        status_code=result["status"],
        media_type=result["content_type"],
    )


def model_map() -> dict[str, str]:
    raw = os.environ.get("VLLM_ROUTER_MODEL_MAP", "").strip()
    if not raw:
        return DEFAULT_MODEL_MAP
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"invalid VLLM_ROUTER_MODEL_MAP: {exc}") from exc
    if not isinstance(parsed, dict) or not parsed:
        raise HTTPException(status_code=500, detail="VLLM_ROUTER_MODEL_MAP must be a non-empty JSON object")
    return {str(key): str(value).rstrip("/") for key, value in parsed.items()}


def proxy_json_request(
    api_base: str,
    path: str,
    payload: dict[str, Any],
    authorization: str | None,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    backend_api_key = os.environ.get("VLLM_ROUTER_BACKEND_API_KEY", "")
    if backend_api_key:
        headers["Authorization"] = f"Bearer {backend_api_key}"
    elif authorization:
        headers["Authorization"] = authorization

    request = urllib.request.Request(f"{api_base}{path}", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=int(os.environ.get("VLLM_ROUTER_TIMEOUT", "300"))) as response:
            return {
                "status": response.status,
                "body": response.read(),
                "content_type": response.headers.get("content-type", "application/json"),
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "body": exc.read(),
            "content_type": exc.headers.get("content-type", "application/json"),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"backend request failed for {api_base}: {exc}") from exc
