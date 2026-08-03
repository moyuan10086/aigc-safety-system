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
from services import audit_log_service, auth_service

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
    shadow_evaluation: dict[str, Any]
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


def _actor_context(request: Request) -> tuple[str, dict[str, str]]:
    api_client = getattr(request.state, "api_client", None)
    if api_client:
        return (
            f"api:{api_client['key_id']}",
            {
                "api_key_id": api_client["key_id"],
                "tenant_id": api_client["tenant_id"],
                "api_version": "v1",
            },
        )
    user = auth_service.verify_session(request.cookies.get("aigc_operator_session"))
    return (user["username"] if user else "anonymous", {})


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
async def check_guardrail(body: GuardrailCheckRequest, request: Request):
    try:
        result = await asyncio.to_thread(
            guardrail_service.check,
            body.prompt,
            body.response,
            body.mode,
        )
        actor, api_metadata = _actor_context(request)
        shadow_evaluation = result.get("shadow_evaluation", {})
        event_id = audit_log_service.record_safe(
            event_type="guardrail.check",
            module="guardrail",
            action=f"check_{body.mode}",
            severity={"safe": "info", "borderline": "warning", "unsafe": "high"}.get(result["verdict"], "info"),
            outcome={"safe": "allowed", "borderline": "review", "unsafe": "blocked"}.get(result["verdict"], "success"),
            actor=actor,
            client_ip=_client_key(request),
            summary=f"护栏判定：{result['risk_code']}",
            resource_id=getattr(request.state, "request_id", None),
            risk_code=result.get("risk_code"),
            risk_score=result.get("risk_score"),
            content_hash=audit_log_service.content_digest(f"{body.prompt}\n{body.response}"),
            metadata={
                "mode": body.mode,
                "categories": result.get("categories", []),
                "content_length": len(body.prompt) + len(body.response),
                "expert_parallel": (result.get("engine") or {}).get("expert_parallel"),
                "engine_timings_ms": (result.get("engine") or {}).get("timings_ms", {}),
                "shadow_evaluation": shadow_evaluation,
                **api_metadata,
            },
        )
        if event_id:
            audit_log_service.store_evidence(
                event_id,
                prompt=body.prompt or None,
                response=body.response or None,
                dangerous=result["verdict"] == "unsafe",
            )
        return result
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
            evidence_capture: dict[str, str] = {}
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    guarded_chat_service.run,
                    body.prompt.strip(),
                    body.max_tokens,
                    evidence_capture,
                ),
                timeout=config.CHAT_MODEL_TIMEOUT_SECONDS + 10,
            )
            final_guard = result.get("final_guard", {})
            actor, api_metadata = _actor_context(request)
            event_id = audit_log_service.record_safe(
                event_type="guardrail.chat",
                module="guardrail",
                action="guarded_model_generation",
                severity={"safe": "info", "borderline": "warning", "unsafe": "high"}.get(final_guard.get("verdict"), "info"),
                outcome={"completed": "allowed", "review_required": "review", "input_blocked": "blocked", "output_blocked": "blocked"}.get(result.get("status"), "success"),
                actor=actor,
                client_ip=_client_key(request),
                status_code=200,
                latency_ms=result.get("generation", {}).get("latency_ms"),
                summary=f"大模型护栏流程：{result.get('status', 'completed')}",
                resource_id=result.get("request_id"),
                risk_code=final_guard.get("risk_code"),
                risk_score=final_guard.get("risk_score"),
                content_hash=audit_log_service.content_digest(body.prompt),
                metadata={
                    "model_called": result.get("model_called", False),
                    "model": result.get("generation", {}).get("model"),
                    "quarantined": result.get("quarantined", False),
                    "categories": final_guard.get("categories", []),
                    "prompt_length": len(body.prompt),
                    **api_metadata,
                },
            )
            if event_id:
                audit_log_service.store_evidence(
                    event_id,
                    prompt=body.prompt,
                    response=evidence_capture.get("model_output"),
                    dangerous=result.get("status") in {"input_blocked", "output_blocked"},
                )
            return result
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
