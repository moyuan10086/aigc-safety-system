"""Large-model safety guardrail API."""

import asyncio
import threading
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

import config
from services import guarded_chat_service
from services import guardrail_service

router = APIRouter(prefix="/api/guardrail", tags=["guardrail"])
_CHAT_SEMAPHORE = asyncio.Semaphore(2)
_RATE_LOCK = threading.Lock()
_RATE_WINDOWS: dict[str, deque[float]] = defaultdict(deque)


class GuardrailCheckRequest(BaseModel):
    prompt: str = Field(default="", max_length=12_000)
    response: str = Field(default="", max_length=12_000)
    mode: str = Field(default="both", max_length=16)

    @model_validator(mode="after")
    def validate_content(self):
        if not self.prompt.strip() and not self.response.strip():
            raise ValueError("prompt or response must contain non-whitespace text")
        return self


class GuardrailCheckResponse(BaseModel):
    verdict: str
    decision: str
    risk_level: str
    risk_score: float
    intent: str
    categories: list[str]
    evidence: list[dict[str, Any]]
    actions: list[str]
    checks: list[dict[str, Any]]
    risk_code: str
    action: str
    redline_answer: str
    scores: dict[str, float]
    engine: dict[str, Any]


class GuardedChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4_000)
    max_tokens: int | None = Field(default=None, ge=64, le=1_200)


def _client_key(request: Request) -> str:
    client_host = request.client.host if request.client else "unknown"
    if client_host in {"127.0.0.1", "::1"}:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return client_host


def _rate_limit(request: Request) -> None:
    key = _client_key(request)
    now = time.monotonic()
    with _RATE_LOCK:
        window = _RATE_WINDOWS[key]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= config.GUARDRAIL_CHAT_RATE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail={"code": "RATE_LIMITED", "message": "模型调用过于频繁，请稍后重试"},
            )
        window.append(now)


@router.post("/check", response_model=GuardrailCheckResponse)
async def check_guardrail(request: GuardrailCheckRequest):
    try:
        return await asyncio.to_thread(
            guardrail_service.check,
            request.prompt,
            request.response,
            request.mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/model-status")
async def get_model_status():
    return guarded_chat_service.model_status()


@router.post("/chat")
async def guarded_chat(body: GuardedChatRequest, request: Request):
    _rate_limit(request)
    try:
        async with _CHAT_SEMAPHORE:
            return await asyncio.wait_for(
                asyncio.to_thread(guarded_chat_service.run, body.prompt.strip(), body.max_tokens),
                timeout=config.CHAT_MODEL_TIMEOUT_SECONDS + 10,
            )
    except guarded_chat_service.ModelNotConfiguredError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "MODEL_NOT_CONFIGURED", "message": "文本生成模型尚未配置"},
        ) from exc
    except (guarded_chat_service.ModelGatewayError, asyncio.TimeoutError) as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "MODEL_GATEWAY_ERROR", "message": "模型服务暂时不可用，请稍后重试"},
        ) from exc
