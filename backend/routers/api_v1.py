"""Versioned, tenant-aware external API contracts."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, File
from pydantic import BaseModel, Field

from routers import guardrail as guardrail_router
from services import api_access_service, audit_log_service

router = APIRouter(prefix="/api/v1", tags=["external-api-v1"])


class ContentCheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12_000)


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if peer in {"127.0.0.1", "::1"}:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        return forwarded or peer
    return peer


def _envelope(request: Request, data: Any) -> dict[str, Any]:
    return {
        "api_version": "v1",
        "request_id": getattr(request.state, "request_id", None),
        "data": data,
    }


async def _metered(
    request: Request,
    *,
    scope: str,
    operation: str,
    run: Callable[[], Awaitable[Any]],
) -> dict[str, Any]:
    client = api_access_service.require_api_key(request, scope=scope)
    started = time.perf_counter()
    status_code = 200
    try:
        data = await run()
        return _envelope(request, data)
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception:
        status_code = 500
        raise
    finally:
        latency_ms = round((time.perf_counter() - started) * 1000)
        api_access_service.record_usage(
            client,
            operation=operation,
            status_code=status_code,
            latency_ms=latency_ms,
            client_ip=_client_ip(request),
            request_id=getattr(request.state, "request_id", None),
        )
        audit_log_service.record_safe(
            event_type="api.v1.usage",
            module="api",
            action=operation,
            severity="info" if status_code < 400 else "warning",
            outcome="success" if status_code < 400 else "error",
            actor=f"api:{client['key_id']}",
            client_ip=_client_ip(request),
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            latency_ms=latency_ms,
            summary=f"外部 API v1 调用：{operation}",
            resource_id=getattr(request.state, "request_id", None),
            metadata={
                "api_version": "v1",
                "api_key_id": client["key_id"],
                "tenant_id": client["tenant_id"],
                "operation": operation,
            },
        )


@router.get("/catalog")
async def catalog(request: Request):
    async def run():
        client = request.state.api_client
        return {
            "tenant_id": client["tenant_id"],
            "key_id": client["key_id"],
            "scopes": client["scopes"],
            "limits": {
                "requests_per_minute": client["rate_limit_per_minute"],
                "daily_quota": client["daily_quota"],
            },
            "operations": [
                {"method": "POST", "path": "/api/v1/guardrail/check", "scope": "guardrail:check"},
                {"method": "POST", "path": "/api/v1/guardrail/chat", "scope": "guardrail:chat"},
                {"method": "POST", "path": "/api/v1/content/check", "scope": "content:check"},
                {"method": "POST", "path": "/api/v1/images/face", "scope": "image:face"},
                {"method": "POST", "path": "/api/v1/images/deepfake", "scope": "image:deepfake"},
                {"method": "POST", "path": "/api/v1/images/mllm", "scope": "image:mllm"},
                {"method": "GET", "path": "/api/v1/usage", "scope": "usage:read"},
            ],
        }

    return await _metered(request, scope="usage:read", operation="catalog.read", run=run)


@router.post("/guardrail/check")
async def guardrail_check(
    body: guardrail_router.GuardrailCheckRequest,
    request: Request,
):
    async def run():
        return await guardrail_router.check_guardrail(body, request)

    return await _metered(
        request,
        scope="guardrail:check",
        operation="guardrail.check",
        run=run,
    )


@router.post("/guardrail/chat")
async def guardrail_chat(
    body: guardrail_router.GuardedChatRequest,
    request: Request,
):
    async def run():
        return await guardrail_router.guarded_chat(body, request)

    return await _metered(
        request,
        scope="guardrail:chat",
        operation="guardrail.chat",
        run=run,
    )


@router.post("/content/check")
async def content_check(body: ContentCheckRequest, request: Request):
    from services import rag_service

    async def run():
        return await asyncio.to_thread(rag_service.check_content, body.text)

    return await _metered(
        request,
        scope="content:check",
        operation="content.check",
        run=run,
    )


async def _run_image(file: UploadFile, detector: Callable[[str], Any]) -> Any:
    from routers import detect as detect_router

    path = await detect_router._save_upload(file)
    try:
        return await asyncio.to_thread(detector, path)
    finally:
        if os.path.exists(path):
            os.unlink(path)


@router.post("/images/face")
async def image_face(request: Request, image: UploadFile = File(...)):
    from routers import detect as detect_router

    async def run():
        return await _run_image(image, detect_router._inspect_faces)

    return await _metered(request, scope="image:face", operation="image.face", run=run)


@router.post("/images/deepfake")
async def image_deepfake(request: Request, image: UploadFile = File(...)):
    from services import deepfake_service

    async def run():
        return await _run_image(image, deepfake_service.detect)

    return await _metered(request, scope="image:deepfake", operation="image.deepfake", run=run)


@router.post("/images/mllm")
async def image_mllm(request: Request, image: UploadFile = File(...)):
    from services import mllm_service

    async def run():
        return await _run_image(image, mllm_service.analyze)

    return await _metered(request, scope="image:mllm", operation="image.mllm", run=run)


@router.get("/usage")
async def usage(request: Request, days: int = Query(default=1, ge=1, le=31)):
    async def run():
        return api_access_service.usage(request.state.api_client, days=days)

    return await _metered(request, scope="usage:read", operation="usage.read", run=run)
