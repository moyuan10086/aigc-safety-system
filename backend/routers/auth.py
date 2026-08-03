"""Operator login endpoints backed by signed HttpOnly sessions."""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

import config
from services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])
COOKIE_NAME = "aigc_operator_session"
MAX_FAILURES = 5
FAILURE_WINDOW_SECONDS = 300

_failures: dict[str, deque[float]] = defaultdict(deque)
_failure_lock = Lock()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


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
        raise HTTPException(
            status_code=429,
            detail="登录失败次数过多，请 5 分钟后重试",
            headers={"Retry-After": str(FAILURE_WINDOW_SECONDS)},
        )

    user = auth_service.authenticate(body.username.strip(), body.password)
    if user is None:
        _record_failure(client_key)
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
    return {"authenticated": True, "user": user}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=config.AUTH_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
    return {"authenticated": False}
