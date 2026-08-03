"""Operator login endpoints backed by signed HttpOnly sessions."""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
import time

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

import config
from services import api_access_service, audit_log_service, auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])
COOKIE_NAME = "aigc_operator_session"
MAX_FAILURES = 5
FAILURE_WINDOW_SECONDS = 300

_failures: dict[str, deque[float]] = defaultdict(deque)
_failure_lock = Lock()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class ApiKeyCreateRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] | None = None
    rate_limit_per_minute: int | None = Field(default=None, ge=1)
    daily_quota: int | None = Field(default=None, ge=1)


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def _trim_failures(client_key: str, now: float) -> deque[float]:
    failures = _failures[client_key]
    while failures and failures[0] <= now - FAILURE_WINDOW_SECONDS:
        failures.popleft()
    return failures


def _is_limited(client_key: str) -> bool:
    with _failure_lock:
        return len(_trim_failures(client_key, time.monotonic())) >= MAX_FAILURES


def _record_failure(client_key: str) -> None:
    with _failure_lock:
        _trim_failures(client_key, time.monotonic()).append(time.monotonic())


def _clear_failures(client_key: str) -> None:
    with _failure_lock:
        _failures.pop(client_key, None)


def _operator(request: Request) -> dict[str, str]:
    user = auth_service.verify_session(request.cookies.get(COOKIE_NAME))
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录审核员账号")
    return user


@router.get("/session")
async def session(request: Request):
    user = auth_service.verify_session(request.cookies.get(COOKIE_NAME))
    return {
        "authenticated": user is not None,
        "configured": auth_service.configured(),
        "user": user,
    }


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    if not auth_service.configured():
        raise HTTPException(status_code=503, detail="服务器尚未配置登录账号")

    client_key = _client_key(request)
    if _is_limited(client_key):
        audit_log_service.record_safe(
            event_type="auth.login",
            module="auth",
            action="operator_login",
            severity="high",
            outcome="denied",
            actor=body.username.strip(),
            client_ip=client_key,
            summary="审核员登录被速率限制",
            metadata={"reason": "rate_limited"},
        )
        raise HTTPException(
            status_code=429,
            detail="登录失败次数过多，请 5 分钟后重试",
            headers={"Retry-After": str(FAILURE_WINDOW_SECONDS)},
        )

    user = auth_service.authenticate(body.username.strip(), body.password)
    if user is None:
        _record_failure(client_key)
        audit_log_service.record_safe(
            event_type="auth.login",
            module="auth",
            action="operator_login",
            severity="warning",
            outcome="denied",
            actor=body.username.strip(),
            client_ip=client_key,
            summary="审核员登录失败",
            metadata={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    _clear_failures(client_key)
    response.set_cookie(
        key=COOKIE_NAME,
        value=auth_service.create_session(user),
        max_age=config.AUTH_SESSION_TTL_SECONDS,
        httponly=True,
        secure=config.AUTH_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    audit_log_service.record_safe(
        event_type="auth.login",
        module="auth",
        action="operator_login",
        severity="info",
        outcome="success",
        actor=user["username"],
        client_ip=client_key,
        summary="审核员登录成功",
        metadata={"role": user["role"]},
    )
    return {"authenticated": True, "user": user}


@router.post("/logout")
async def logout(request: Request, response: Response):
    user = auth_service.verify_session(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=config.AUTH_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
    audit_log_service.record_safe(
        event_type="auth.logout",
        module="auth",
        action="operator_logout",
        severity="info",
        outcome="success",
        actor=user["username"] if user else "anonymous",
        client_ip=_client_key(request),
        summary="审核员退出登录",
    )
    return {"authenticated": False}


@router.post("/api-keys")
async def create_api_key(body: ApiKeyCreateRequest, request: Request):
    """Issue an external API key; the plaintext is returned only once."""
    user = _operator(request)
    try:
        issued = api_access_service.issue_key(
            tenant_id=body.tenant_id,
            name=body.name,
            scopes=body.scopes,
            rate_limit_per_minute=body.rate_limit_per_minute,
            daily_quota=body.daily_quota,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_log_service.record_safe(
        event_type="auth.api_key.issue",
        module="auth",
        action="issue_api_key",
        actor=user["username"],
        client_ip=_client_key(request),
        summary="签发外部 API Key",
        metadata={
            "key_id": issued["key_id"],
            "key_prefix": issued["key_prefix"],
            "tenant_id": issued["tenant_id"],
            "scopes": issued["scopes"],
            "rate_limit_per_minute": issued["rate_limit_per_minute"],
            "daily_quota": issued["daily_quota"],
        },
    )
    return issued


@router.get("/api-keys")
async def list_api_keys(request: Request, tenant_id: str | None = None):
    _operator(request)
    return {"items": api_access_service.list_keys(tenant_id=tenant_id)}


@router.get("/api-usage")
async def api_usage(
    request: Request,
    days: int = Query(default=7, ge=1, le=31),
    tenant_id: str | None = None,
):
    _operator(request)
    return api_access_service.operator_usage(days=days, tenant_id=tenant_id)


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, request: Request):
    user = _operator(request)
    revoked = api_access_service.revoke_key(key_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="API Key 不存在或已撤销")
    audit_log_service.record_safe(
        event_type="auth.api_key.revoke",
        module="auth",
        action="revoke_api_key",
        actor=user["username"],
        client_ip=_client_key(request),
        summary="撤销外部 API Key",
        metadata={"key_id": key_id[:32]},
    )
    return {"revoked": True, "key_id": key_id}
