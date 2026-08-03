"""Password verification and signed operator sessions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

import config

PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 310_000


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, *, iterations: int = PASSWORD_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{PASSWORD_SCHEME}${iterations}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations_text, salt_text, digest_text = encoded.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        iterations = int(iterations_text)
        if iterations < 100_000:
            return False
        salt = _decode(salt_text)
        expected = _decode(digest_text)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def configured() -> bool:
    return bool(
        config.AUTH_USERNAME
        and config.AUTH_PASSWORD_HASH
        and config.AUTH_SESSION_SECRET
    )


def authenticate(username: str, password: str) -> dict[str, str] | None:
    username_matches = hmac.compare_digest(username, config.AUTH_USERNAME)
    password_matches = verify_password(password, config.AUTH_PASSWORD_HASH)
    if not configured() or not username_matches or not password_matches:
        return None
    return current_user()


def current_user() -> dict[str, str]:
    return {
        "username": config.AUTH_USERNAME,
        "display_name": config.AUTH_DISPLAY_NAME or config.AUTH_USERNAME,
        "role": config.AUTH_ROLE,
    }


def create_session(user: dict[str, str], now: int | None = None) -> str:
    issued_at = int(time.time() if now is None else now)
    payload = {
        "sub": user["username"],
        "name": user["display_name"],
        "role": user["role"],
        "iat": issued_at,
        "exp": issued_at + config.AUTH_SESSION_TTL_SECONDS,
        "jti": secrets.token_hex(8),
    }
    body = _encode(json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode())
    signature = hmac.new(
        config.AUTH_SESSION_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{body}.{_encode(signature)}"


def verify_session(token: str | None, now: int | None = None) -> dict[str, Any] | None:
    if not configured() or not token:
        return None
    try:
        body, signature_text = token.split(".", 1)
        expected = hmac.new(
            config.AUTH_SESSION_SECRET.encode("utf-8"),
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_decode(signature_text), expected):
            return None
        payload = json.loads(_decode(body))
        current_time = int(time.time() if now is None else now)
        if payload.get("exp", 0) <= current_time:
            return None
        if not hmac.compare_digest(str(payload.get("sub", "")), config.AUTH_USERNAME):
            return None
        return {
            "username": payload["sub"],
            "display_name": payload.get("name") or payload["sub"],
            "role": payload.get("role") or "operator",
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
