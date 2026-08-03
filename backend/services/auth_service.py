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
MAX_OPERATOR_ACCOUNTS = 50


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


def _clean_account(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    username = str(value.get("username") or "").strip()
    password_hash = str(value.get("password_hash") or "").strip()
    display_name = str(value.get("display_name") or username).strip()
    role = str(value.get("role") or "operator").strip()
    if not username or len(username) > 128 or not password_hash:
        return None
    if len(display_name) > 128 or not role or len(role) > 48:
        return None
    return {
        "username": username,
        "display_name": display_name or username,
        "role": role,
        "password_hash": password_hash,
    }


def _operator_accounts() -> dict[str, dict[str, str]]:
    accounts: dict[str, dict[str, str]] = {}
    legacy = _clean_account({
        "username": config.AUTH_USERNAME,
        "display_name": config.AUTH_DISPLAY_NAME,
        "role": config.AUTH_ROLE,
        "password_hash": config.AUTH_PASSWORD_HASH,
    })
    if legacy:
        accounts[legacy["username"]] = legacy

    raw = str(config.AUTH_OPERATORS_JSON or "").strip()
    if not raw:
        return accounts
    try:
        values = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(values, list) or len(values) > MAX_OPERATOR_ACCOUNTS:
        return {}
    for value in values:
        account = _clean_account(value)
        if account is None or account["username"] in accounts:
            return {}
        accounts[account["username"]] = account
    return accounts


def configured() -> bool:
    return bool(config.AUTH_SESSION_SECRET and _operator_accounts())


def authenticate(username: str, password: str) -> dict[str, str] | None:
    accounts = _operator_accounts()
    if not config.AUTH_SESSION_SECRET or not accounts:
        return None
    account = accounts.get(username)
    comparison_hash = (
        account["password_hash"]
        if account is not None
        else next(iter(accounts.values()))["password_hash"]
    )
    password_matches = verify_password(password, comparison_hash)
    if account is None or not password_matches:
        return None
    return {key: account[key] for key in ("username", "display_name", "role")}


def current_user(username: str | None = None) -> dict[str, str]:
    accounts = _operator_accounts()
    selected = username or config.AUTH_USERNAME
    account = accounts.get(selected)
    if account is None and username is None and len(accounts) == 1:
        account = next(iter(accounts.values()))
    if account is None:
        raise RuntimeError("operator account is not configured")
    return {key: account[key] for key in ("username", "display_name", "role")}


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
        account = _operator_accounts().get(str(payload.get("sub", "")))
        if account is None:
            return None
        return {
            "username": account["username"],
            "display_name": account["display_name"],
            "role": account["role"],
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
