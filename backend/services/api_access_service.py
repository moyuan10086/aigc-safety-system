"""API key issuance, tenant identity, quotas and usage accounting.

The service deliberately keeps this ledger separate from the evidence vault.
Only key metadata and aggregate request facts are persisted; request content
must remain in the encrypted audit evidence table when a workflow captures it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import secrets
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

import config

_LOCK = threading.RLock()
_INITIALIZED_PATHS: set[str] = set()
_RATE_WINDOWS: dict[str, list[float]] = {}


def _db_path() -> Path:
    path = Path(config.API_KEY_DB_PATH)
    if not path.is_absolute():
        path = Path(__file__).parents[1] / path
    return path


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    _initialize(connection, str(path.resolve()))
    return connection


def _initialize(connection: sqlite3.Connection, key: str) -> None:
    if key in _INITIALIZED_PATHS:
        return
    with _LOCK:
        if key in _INITIALIZED_PATHS:
            return
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                key_prefix TEXT NOT NULL UNIQUE,
                key_hash TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                scopes_json TEXT NOT NULL,
                rate_limit_per_minute INTEGER NOT NULL,
                daily_quota INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                revoked_at TEXT,
                last_used_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id);
            CREATE TABLE IF NOT EXISTS api_usage (
                id TEXT PRIMARY KEY,
                key_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                operation TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                latency_ms INTEGER NOT NULL,
                units INTEGER NOT NULL DEFAULT 1,
                client_ip TEXT,
                request_id TEXT,
                FOREIGN KEY(key_id) REFERENCES api_keys(key_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_api_usage_key_time ON api_usage(key_id, occurred_at DESC);
            CREATE INDEX IF NOT EXISTS idx_api_usage_tenant_time ON api_usage(tenant_id, occurred_at DESC);
            """
        )
        connection.commit()
        _INITIALIZED_PATHS.add(key)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _p95(values: list[int]) -> int:
    ordered = sorted(max(0, int(value)) for value in values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)] if ordered else 0


def _secret_digest(raw_key: str) -> str:
    if not config.API_KEY_HASH_SECRET:
        raise RuntimeError("API_KEY_HASH_SECRET is not configured")
    return hmac.new(
        config.API_KEY_HASH_SECRET.encode("utf-8"),
        raw_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _safe_scopes(scopes: list[str] | None) -> list[str]:
    values = scopes or ["guardrail:check", "guardrail:chat", "content:check", "usage:read"]
    normalized = sorted({str(value).strip().lower() for value in values if str(value).strip()})
    if not normalized or len(normalized) > 20 or any(len(value) > 64 for value in normalized):
        raise ValueError("scopes must contain 1-20 short values")
    return normalized


def _row_to_client(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "key_id": row["key_id"],
        "key_prefix": row["key_prefix"],
        "tenant_id": row["tenant_id"],
        "name": row["name"],
        "scopes": json.loads(row["scopes_json"]),
        "rate_limit_per_minute": int(row["rate_limit_per_minute"]),
        "daily_quota": int(row["daily_quota"]),
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "revoked_at": row["revoked_at"],
        "last_used_at": row["last_used_at"],
    }


def issue_key(
    *,
    tenant_id: str,
    name: str,
    scopes: list[str] | None = None,
    rate_limit_per_minute: int | None = None,
    daily_quota: int | None = None,
) -> dict[str, Any]:
    tenant_id = " ".join(str(tenant_id).split())[:80]
    name = " ".join(str(name).split())[:120]
    if not tenant_id or not name:
        raise ValueError("tenant_id and name are required")
    rate = int(rate_limit_per_minute or config.API_KEY_DEFAULT_RATE_LIMIT)
    quota = int(daily_quota or config.API_KEY_DEFAULT_DAILY_QUOTA)
    if not 1 <= rate <= config.API_KEY_MAX_RATE_LIMIT:
        raise ValueError("rate_limit_per_minute is outside the allowed range")
    if not 1 <= quota <= config.API_KEY_MAX_DAILY_QUOTA:
        raise ValueError("daily_quota is outside the allowed range")
    scope_values = _safe_scopes(scopes)
    key_id = uuid.uuid4().hex[:16]
    key_prefix = f"aigc_{key_id}"
    raw_key = f"{key_prefix}_{secrets.token_urlsafe(32)}"
    created_at = _iso()
    with _LOCK, closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO api_keys (
                key_id, key_prefix, key_hash, tenant_id, name, scopes_json,
                rate_limit_per_minute, daily_quota, active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                key_id,
                key_prefix,
                _secret_digest(raw_key),
                tenant_id,
                name,
                json.dumps(scope_values, ensure_ascii=True),
                rate,
                quota,
                created_at,
            ),
        )
        connection.commit()
    return {
        "key": raw_key,
        "key_id": key_id,
        "key_prefix": key_prefix,
        "tenant_id": tenant_id,
        "name": name,
        "scopes": scope_values,
        "rate_limit_per_minute": rate,
        "daily_quota": quota,
        "created_at": created_at,
        "warning": "请立即保存明文 API Key；服务端不会再次显示。",
    }


def authenticate(raw_key: str | None) -> dict[str, Any] | None:
    if not raw_key or len(raw_key) > 256 or not raw_key.startswith("aigc_"):
        return None
    parts = raw_key.split("_", 2)
    if len(parts) != 3 or len(parts[1]) != 16 or not parts[2]:
        return None
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT * FROM api_keys WHERE key_id = ? AND active = 1",
            (parts[1],),
        ).fetchone()
    if row is None:
        return None
    if not hmac.compare_digest(row["key_hash"], _secret_digest(raw_key)):
        return None
    return _row_to_client(row)


def _raw_key_from_request(request: Request) -> str | None:
    value = request.headers.get("x-api-key", "").strip()
    if value:
        return value
    authorization = request.headers.get("authorization", "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def require_api_key(request: Request, *, scope: str | None = None) -> dict[str, Any]:
    client = authenticate(_raw_key_from_request(request))
    if client is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "API_KEY_REQUIRED", "message": "请提供有效的 API Key"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if scope and scope not in client["scopes"] and "*" not in client["scopes"]:
        raise HTTPException(
            status_code=403,
            detail={"code": "INSUFFICIENT_SCOPE", "message": f"API Key 缺少作用域 {scope}"},
        )
    check_limits(client)
    request.state.api_client = client
    return client


def check_limits(client: dict[str, Any], *, now: datetime | None = None) -> None:
    current = (now or _now()).timestamp()
    with _LOCK:
        window = _RATE_WINDOWS.setdefault(client["key_id"], [])
        window[:] = [stamp for stamp in window if current - stamp < 60]
        if len(window) >= client["rate_limit_per_minute"]:
            retry_after = max(1, int(60 - (current - window[0])))
            raise HTTPException(
                status_code=429,
                detail={"code": "API_RATE_LIMITED", "message": "API Key 请求频率超出配额"},
                headers={"Retry-After": str(retry_after)},
            )
        window.append(current)
        since = _iso((now or _now()).replace(hour=0, minute=0, second=0, microsecond=0))
        with closing(_connect()) as connection:
            used = connection.execute(
                "SELECT COALESCE(SUM(units), 0) FROM api_usage WHERE key_id = ? AND occurred_at >= ?",
                (client["key_id"], since),
            ).fetchone()[0]
        if int(used) >= client["daily_quota"]:
            raise HTTPException(
                status_code=429,
                detail={"code": "API_DAILY_QUOTA_EXCEEDED", "message": "API Key 每日配额已用尽"},
                headers={"Retry-After": "3600"},
            )


def record_usage(
    client: dict[str, Any],
    *,
    operation: str,
    status_code: int,
    latency_ms: int,
    units: int = 1,
    client_ip: str | None = None,
    request_id: str | None = None,
) -> None:
    occurred_at = _iso()
    with _LOCK, closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO api_usage
                (id, key_id, tenant_id, occurred_at, operation, status_code,
                 latency_ms, units, client_ip, request_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                client["key_id"],
                client["tenant_id"],
                occurred_at,
                operation[:120],
                int(status_code),
                max(0, int(latency_ms)),
                max(1, int(units)),
                (client_ip or "")[:64] or None,
                (request_id or "")[:128] or None,
            ),
        )
        connection.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE key_id = ?",
            (occurred_at, client["key_id"]),
        )
        connection.commit()


def usage(client: dict[str, Any], *, days: int = 1) -> dict[str, Any]:
    days = max(1, min(int(days), 31))
    start = _iso(_now() - timedelta(days=days))
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT operation, COUNT(*) AS requests, COALESCE(SUM(units), 0) AS units,
                   SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) AS successes,
                   AVG(latency_ms) AS avg_latency_ms
            FROM api_usage
            WHERE key_id = ? AND occurred_at >= ?
            GROUP BY operation ORDER BY requests DESC, operation ASC
            """,
            (client["key_id"], start),
        ).fetchall()
        totals = connection.execute(
            """
            SELECT COUNT(*) AS requests, COALESCE(SUM(units), 0) AS units,
                   SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) AS successes,
                   AVG(latency_ms) AS avg_latency_ms
            FROM api_usage WHERE key_id = ? AND occurred_at >= ?
            """,
            (client["key_id"], start),
        ).fetchone()
        latency_rows = connection.execute(
            "SELECT latency_ms FROM api_usage WHERE key_id = ? AND occurred_at >= ?",
            (client["key_id"], start),
        ).fetchall()
    request_count = int(totals["requests"] or 0)
    success_count = int(totals["successes"] or 0)
    return {
        "tenant_id": client["tenant_id"],
        "key_id": client["key_id"],
        "window_days": days,
        "quota": {
            "daily": client["daily_quota"],
            "rate_limit_per_minute": client["rate_limit_per_minute"],
        },
        "totals": {
            "requests": request_count,
            "units": int(totals["units"] or 0),
            "successes": success_count,
            "success_rate": round(success_count / request_count * 100, 1) if request_count else 0.0,
            "failure_rate": round((request_count - success_count) / request_count * 100, 1)
            if request_count else 0.0,
            "avg_latency_ms": round(float(totals["avg_latency_ms"] or 0), 1),
            "p95_latency_ms": _p95([row["latency_ms"] for row in latency_rows]),
        },
        "by_operation": [
            {
                "operation": row["operation"],
                "requests": int(row["requests"]),
                "units": int(row["units"]),
                "successes": int(row["successes"] or 0),
                "avg_latency_ms": round(float(row["avg_latency_ms"] or 0), 1),
            }
            for row in rows
        ],
    }


def list_keys(*, tenant_id: str | None = None) -> list[dict[str, Any]]:
    with closing(_connect()) as connection:
        if tenant_id:
            rows = connection.execute(
                "SELECT * FROM api_keys WHERE tenant_id = ? ORDER BY created_at DESC", (tenant_id,)
            ).fetchall()
        else:
            rows = connection.execute("SELECT * FROM api_keys ORDER BY created_at DESC").fetchall()
    return [_row_to_client(row) for row in rows]


def operator_usage(*, days: int = 7, tenant_id: str | None = None) -> dict[str, Any]:
    """Return content-free usage aggregates for authenticated operators."""
    days = max(1, min(int(days), 31))
    start = _iso(_now() - timedelta(days=days))
    tenant_clause = " AND api_usage.tenant_id = ?" if tenant_id else ""
    params: list[Any] = [start]
    if tenant_id:
        params.append(tenant_id)
    with closing(_connect()) as connection:
        totals = connection.execute(
            f"""
            SELECT COUNT(*) AS requests, COALESCE(SUM(units), 0) AS units,
                   SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) AS successes,
                   COUNT(DISTINCT tenant_id) AS tenants,
                   COUNT(DISTINCT key_id) AS keys,
                   AVG(latency_ms) AS avg_latency_ms
            FROM api_usage WHERE occurred_at >= ?{tenant_clause}
            """,
            params,
        ).fetchone()
        tenants = connection.execute(
            f"""
            SELECT tenant_id, COUNT(*) AS requests, COALESCE(SUM(units), 0) AS units,
                   SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) AS successes,
                   COUNT(DISTINCT key_id) AS keys
            FROM api_usage WHERE occurred_at >= ?{tenant_clause}
            GROUP BY tenant_id ORDER BY requests DESC, tenant_id ASC
            """,
            params,
        ).fetchall()
        keys = connection.execute(
            f"""
            SELECT api_usage.key_id, api_usage.tenant_id, api_keys.key_prefix, api_keys.name,
                   COUNT(*) AS requests, COALESCE(SUM(api_usage.units), 0) AS units,
                   SUM(CASE WHEN api_usage.status_code < 400 THEN 1 ELSE 0 END) AS successes,
                   AVG(api_usage.latency_ms) AS avg_latency_ms
            FROM api_usage JOIN api_keys ON api_keys.key_id = api_usage.key_id
            WHERE api_usage.occurred_at >= ?{tenant_clause}
            GROUP BY api_usage.key_id, api_usage.tenant_id, api_keys.key_prefix, api_keys.name
            ORDER BY requests DESC, api_usage.key_id ASC
            """,
            params,
        ).fetchall()
        samples = connection.execute(
            f"""
            SELECT key_id, tenant_id, latency_ms
            FROM api_usage WHERE occurred_at >= ?{tenant_clause}
            """,
            params,
        ).fetchall()
    request_count = int(totals["requests"] or 0)
    success_count = int(totals["successes"] or 0)
    tenant_latencies: dict[str, list[int]] = {}
    key_latencies: dict[str, list[int]] = {}
    all_latencies: list[int] = []
    for row in samples:
        latency = int(row["latency_ms"])
        all_latencies.append(latency)
        tenant_latencies.setdefault(row["tenant_id"], []).append(latency)
        key_latencies.setdefault(row["key_id"], []).append(latency)
    return {
        "window_days": days,
        "tenant_filter": tenant_id,
        "totals": {
            "requests": request_count,
            "units": int(totals["units"] or 0),
            "successes": success_count,
            "success_rate": round(success_count / request_count * 100, 1) if request_count else 0.0,
            "failure_rate": round((request_count - success_count) / request_count * 100, 1)
            if request_count else 0.0,
            "tenants": int(totals["tenants"] or 0),
            "keys": int(totals["keys"] or 0),
            "avg_latency_ms": round(float(totals["avg_latency_ms"] or 0), 1),
            "p95_latency_ms": _p95(all_latencies),
        },
        "by_tenant": [
            {
                "tenant_id": row["tenant_id"],
                "requests": int(row["requests"]),
                "units": int(row["units"]),
                "successes": int(row["successes"] or 0),
                "keys": int(row["keys"]),
                "failure_rate": round(
                    (int(row["requests"]) - int(row["successes"] or 0))
                    / int(row["requests"])
                    * 100,
                    1,
                ),
                "p95_latency_ms": _p95(tenant_latencies.get(row["tenant_id"], [])),
            }
            for row in tenants
        ],
        "by_key": [
            {
                "key_id": row["key_id"],
                "tenant_id": row["tenant_id"],
                "key_prefix": row["key_prefix"],
                "name": row["name"],
                "requests": int(row["requests"]),
                "units": int(row["units"]),
                "successes": int(row["successes"] or 0),
                "avg_latency_ms": round(float(row["avg_latency_ms"] or 0), 1),
                "failure_rate": round(
                    (int(row["requests"]) - int(row["successes"] or 0))
                    / int(row["requests"])
                    * 100,
                    1,
                ),
                "p95_latency_ms": _p95(key_latencies.get(row["key_id"], [])),
            }
            for row in keys
        ],
    }


def revoke_key(key_id: str) -> bool:
    now = _iso()
    with _LOCK, closing(_connect()) as connection:
        cursor = connection.execute(
            "UPDATE api_keys SET active = 0, revoked_at = ? WHERE key_id = ? AND active = 1",
            (now, key_id),
        )
        connection.commit()
    with _LOCK:
        _RATE_WINDOWS.pop(key_id, None)
    return cursor.rowcount > 0


def reset_for_tests() -> None:
    with _LOCK:
        _INITIALIZED_PATHS.clear()
        _RATE_WINDOWS.clear()
