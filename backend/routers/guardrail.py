"""Large-model safety guardrail API."""

import asyncio
import json
import threading
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

import config
from services import agent_guardrail_service, guarded_chat_service
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


class AgentActionBase(BaseModel):
    tool_name: str = Field(min_length=1, max_length=120)
    resource: str = Field(min_length=1, max_length=500)
    arguments: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_action_size(self):
        canonical = json.dumps(
            self.arguments,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(canonical.encode("utf-8")) > 12_000:
            raise ValueError("Agent 工具参数不能超过 12 KB")
        return self


class AgentActionCheckRequest(AgentActionBase):
    approval_token: str | None = Field(default=None, max_length=2_000)


class AgentApprovalRequest(AgentActionBase):
    reason: str = Field(min_length=2, max_length=500)
    ttl_seconds: int | None = Field(default=None, ge=60, le=900)


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


def _operator(request: Request) -> dict[str, str]:
    user = auth_service.verify_session(request.cookies.get("aigc_operator_session"))
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录审核员账号")
    return user


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


@router.post("/agent/approvals")
async def issue_agent_approval(body: AgentApprovalRequest, request: Request):
    user = _operator(request)
    try:
        issued = await asyncio.to_thread(
            agent_guardrail_service.issue_approval,
            tool_name=body.tool_name,
            arguments=body.arguments,
            resource=body.resource,
            approver=user["username"],
            ttl_seconds=body.ttl_seconds,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    event_id = audit_log_service.record_safe(
        event_type="guardrail.agent_approval.issue",
        module="guardrail",
        action="issue_agent_action_approval",
        severity="warning",
        outcome="success",
        actor=user["username"],
        client_ip=_client_key(request),
        summary="签发 Agent 工具执行一次性审批凭证",
        resource_id=getattr(request.state, "request_id", None),
        content_hash=issued["action_digest"],
        metadata={
            "approval_id": issued["approval_id"],
            "tool_name": body.tool_name.strip()[:120],
            "resource_hash": audit_log_service.content_digest(body.resource),
            "reason_hash": audit_log_service.content_digest(body.reason),
            "expires_at": issued["expires_at"],
            "single_use": True,
        },
    )
    if event_id:
        audit_log_service.store_evidence(
            event_id,
            prompt=agent_guardrail_service.canonical_action(
                body.tool_name, body.arguments, body.resource
            ),
            response=body.reason,
            dangerous=True,
        )
    return issued


@router.post("/agent/check")
async def check_agent_action(body: AgentActionCheckRequest, request: Request):
    result = await asyncio.to_thread(
        agent_guardrail_service.check_action,
        tool_name=body.tool_name,
        arguments=body.arguments,
        resource=body.resource,
        approval_token=body.approval_token,
    )
    actor, api_metadata = _actor_context(request)
    event_id = audit_log_service.record_safe(
        event_type="guardrail.agent_check",
        module="guardrail",
        action="pre_execute_agent_tool",
        severity={"safe": "info", "borderline": "warning", "unsafe": "critical"}.get(
            result["verdict"], "warning"
        ),
        outcome={"safe": "allowed", "borderline": "review", "unsafe": "blocked"}.get(
            result["verdict"], "error"
        ),
        actor=actor,
        client_ip=_client_key(request),
        summary=f"Agent 工具执行前门禁：{result['risk_code']}",
        resource_id=getattr(request.state, "request_id", None),
        risk_code=result["risk_code"],
        risk_score=result["risk_score"],
        content_hash=result["action_digest"],
        metadata={
            "tool_name": body.tool_name.strip()[:120],
            "resource_hash": audit_log_service.content_digest(body.resource),
            "categories": result.get("categories", []),
            "approval_status": result.get("approval", {}).get("status"),
            "engine_components": result.get("engine", {}).get("components", {}),
            **api_metadata,
        },
    )
    if event_id:
        audit_log_service.store_evidence(
            event_id,
            prompt=agent_guardrail_service.canonical_action(
                body.tool_name, body.arguments, body.resource
            ),
            dangerous=result["verdict"] != "safe",
        )
        result["audit_event_id"] = event_id
    return result


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
