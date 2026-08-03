"""Persistent, privacy-conscious audit events with a tamper-evident hash chain."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import config
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_LOCK = threading.RLock()
_INITIALIZED_PATHS: set[str] = set()
_INSERT_COUNT = 0


def _db_path() -> Path:
    path = Path(config.AUDIT_LOG_DB_PATH)
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
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                occurred_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                module TEXT NOT NULL,
                action TEXT NOT NULL,
                severity TEXT NOT NULL,
                outcome TEXT NOT NULL,
                actor TEXT,
                client_ip TEXT,
                method TEXT,
                path TEXT,
                status_code INTEGER,
                latency_ms INTEGER,
                summary TEXT NOT NULL,
                resource_id TEXT,
                risk_code TEXT,
                risk_score REAL,
                content_hash TEXT,
                metadata_json TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_audit_occurred_at ON audit_events(occurred_at DESC);
            CREATE INDEX IF NOT EXISTS idx_audit_module ON audit_events(module);
            CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_events(severity);
            CREATE INDEX IF NOT EXISTS idx_audit_outcome ON audit_events(outcome);
            CREATE TABLE IF NOT EXISTS audit_evidence (
                event_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL,
                content_types TEXT NOT NULL,
                dangerous INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(event_id) REFERENCES audit_events(id) ON DELETE CASCADE
            );
            """
        )
        connection.commit()
        _INITIALIZED_PATHS.add(key)


def _clean_text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text[:limit] or None


def content_digest(value: str | bytes | None) -> str | None:
    if value is None:
        return None
    data = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _record_hash(payload: dict[str, Any], prev_hash: str) -> str:
    canonical = json.dumps(
        {**payload, "prev_hash": prev_hash},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record(
    *,
    event_type: str,
    module: str,
    action: str,
    severity: str = "info",
    outcome: str = "success",
    actor: str | None = None,
    client_ip: str | None = None,
    method: str | None = None,
    path: str | None = None,
    status_code: int | None = None,
    latency_ms: int | None = None,
    summary: str,
    resource_id: str | None = None,
    risk_code: str | None = None,
    risk_score: float | None = None,
    content_hash: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Append one event. Callers must keep secrets and raw user content out of metadata."""
    global _INSERT_COUNT
    event_id = uuid.uuid4().hex
    occurred_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    safe_metadata = metadata or {}
    metadata_json = json.dumps(safe_metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload = {
        "id": event_id,
        "occurred_at": occurred_at,
        "event_type": _clean_text(event_type, 80) or "system.event",
        "module": _clean_text(module, 48) or "system",
        "action": _clean_text(action, 80) or "unknown",
        "severity": severity if severity in {"info", "warning", "high", "critical"} else "info",
        "outcome": outcome if outcome in {"success", "allowed", "review", "blocked", "denied", "error"} else "success",
        "actor": _clean_text(actor, 128),
        "client_ip": _clean_text(client_ip, 64),
        "method": _clean_text(method, 12),
        "path": _clean_text(path, 512),
        "status_code": status_code,
        "latency_ms": max(0, int(latency_ms)) if latency_ms is not None else None,
        "summary": _clean_text(summary, 500) or "审计事件",
        "resource_id": _clean_text(resource_id, 128),
        "risk_code": _clean_text(risk_code, 64),
        "risk_score": round(float(risk_score), 4) if risk_score is not None else None,
        "content_hash": _clean_text(content_hash, 64),
        "metadata_json": metadata_json,
    }

    with _LOCK, closing(_connect()) as connection:
        previous = connection.execute(
            "SELECT record_hash FROM audit_events ORDER BY occurred_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
        prev_hash = previous["record_hash"] if previous else "GENESIS"
        record_hash = _record_hash(payload, prev_hash)
        connection.execute(
            """
            INSERT INTO audit_events (
                id, occurred_at, event_type, module, action, severity, outcome,
                actor, client_ip, method, path, status_code, latency_ms, summary,
                resource_id, risk_code, risk_score, content_hash, metadata_json,
                prev_hash, record_hash
            ) VALUES (
                :id, :occurred_at, :event_type, :module, :action, :severity, :outcome,
                :actor, :client_ip, :method, :path, :status_code, :latency_ms, :summary,
                :resource_id, :risk_code, :risk_score, :content_hash, :metadata_json,
                :prev_hash, :record_hash
            )
            """,
            {**payload, "prev_hash": prev_hash, "record_hash": record_hash},
        )
        _INSERT_COUNT += 1
        if _INSERT_COUNT % 100 == 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, config.AUDIT_LOG_RETENTION_DAYS))
            connection.execute("DELETE FROM audit_events WHERE occurred_at < ?", (cutoff.isoformat(),))
        connection.commit()
    return event_id


def record_safe(**event: Any) -> str | None:
    """Best-effort logging must never make the protected business request fail."""
    try:
        return record(**event)
    except Exception:
        return None


def _evidence_key() -> bytes:
    if not config.AUDIT_CONTENT_KEY:
        raise RuntimeError("AUDIT_CONTENT_KEY is not configured")
    return hashlib.sha256(config.AUDIT_CONTENT_KEY.encode("utf-8")).digest()


def store_evidence(
    event_id: str,
    *,
    prompt: str | None = None,
    response: str | None = None,
    dangerous: bool = False,
) -> bool:
    """Encrypt raw model evidence in a separate vault keyed by the audit event."""
    if not config.AUDIT_STORE_RAW_CONTENT or not event_id or not (prompt or response):
        return False
    payload = {
        "prompt": prompt,
        "response": response,
        "dangerous": dangerous,
    }
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    nonce = os.urandom(12)
    ciphertext = AESGCM(_evidence_key()).encrypt(nonce, plaintext, event_id.encode("ascii"))
    content_types = ",".join(key for key in ("prompt", "response") if payload[key] is not None)
    with _LOCK, closing(_connect()) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO audit_evidence
                (event_id, created_at, nonce, ciphertext, content_types, dangerous)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                nonce,
                ciphertext,
                content_types,
                int(dangerous),
            ),
        )
        connection.commit()
    return True


def get_evidence(event_id: str) -> dict[str, Any] | None:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT nonce, ciphertext, content_types, dangerous, created_at FROM audit_evidence WHERE event_id = ?",
            (event_id,),
        ).fetchone()
    if row is None:
        return None
    plaintext = AESGCM(_evidence_key()).decrypt(
        row["nonce"], row["ciphertext"], event_id.encode("ascii")
    )
    data = json.loads(plaintext)
    data.update({
        "event_id": event_id,
        "content_types": row["content_types"].split(","),
        "dangerous": bool(row["dangerous"]),
        "created_at": row["created_at"],
        "encrypted_at_rest": True,
    })
    return data


def _where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for field in ("module", "severity", "outcome", "event_type"):
        value = filters.get(field)
        if value:
            clauses.append(f"{field} = ?")
            params.append(value)
    if filters.get("start"):
        clauses.append("occurred_at >= ?")
        params.append(filters["start"])
    if filters.get("end"):
        clauses.append("occurred_at <= ?")
        params.append(filters["end"])
    if filters.get("keyword"):
        clauses.append("(summary LIKE ? OR actor LIKE ? OR client_ip LIKE ? OR risk_code LIKE ? OR resource_id LIKE ?)")
        term = f"%{filters['keyword']}%"
        params.extend([term] * 5)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    event = dict(row)
    event["metadata"] = json.loads(event.pop("metadata_json") or "{}")
    return event


def list_events(*, page: int = 1, page_size: int = 30, **filters: Any) -> dict[str, Any]:
    where, params = _where(filters)
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    with closing(_connect()) as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM audit_events{where}", params).fetchone()[0]
        rows = connection.execute(
            f"SELECT audit_events.*, EXISTS(SELECT 1 FROM audit_evidence WHERE audit_evidence.event_id = audit_events.id) AS has_evidence FROM audit_events{where} ORDER BY occurred_at DESC, audit_events.rowid DESC LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
    return {"items": [_row_to_event(row) for row in rows], "total": total, "page": page, "page_size": page_size}


def export_events(*, limit: int = 5000, **filters: Any) -> list[dict[str, Any]]:
    where, params = _where(filters)
    with closing(_connect()) as connection:
        rows = connection.execute(
            f"SELECT audit_events.*, EXISTS(SELECT 1 FROM audit_evidence WHERE audit_evidence.event_id = audit_events.id) AS has_evidence FROM audit_events{where} ORDER BY occurred_at DESC, audit_events.rowid DESC LIMIT ?",
            [*params, max(1, min(limit, 5000))],
        ).fetchall()
    return [_row_to_event(row) for row in rows]


def verify_chain() -> bool:
    with closing(_connect()) as connection:
        rows = connection.execute("SELECT * FROM audit_events ORDER BY occurred_at ASC, rowid ASC").fetchall()
    previous_hash: str | None = None
    for row in rows:
        event = dict(row)
        record_hash = event.pop("record_hash")
        prev_hash = event.pop("prev_hash")
        if previous_hash is not None and prev_hash != previous_hash:
            return False
        if _record_hash(event, prev_hash) != record_hash:
            return False
        previous_hash = record_hash
    return True


def statistics() -> dict[str, Any]:
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with closing(_connect()) as connection:
        total = connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        last_24h = connection.execute("SELECT COUNT(*) FROM audit_events WHERE occurred_at >= ?", (since,)).fetchone()[0]
        high_risk = connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE occurred_at >= ? AND severity IN ('high','critical')", (since,)
        ).fetchone()[0]
        blocked = connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE occurred_at >= ? AND outcome IN ('blocked','denied')", (since,)
        ).fetchone()[0]
        unique_clients = connection.execute(
            "SELECT COUNT(DISTINCT client_ip) FROM audit_events WHERE occurred_at >= ? AND client_ip IS NOT NULL", (since,)
        ).fetchone()[0]
        severity_rows = connection.execute(
            "SELECT severity, COUNT(*) AS count FROM audit_events WHERE occurred_at >= ? GROUP BY severity", (since,)
        ).fetchall()
        latest = connection.execute("SELECT occurred_at FROM audit_events ORDER BY occurred_at DESC LIMIT 1").fetchone()
    return {
        "total": total,
        "last_24h": last_24h,
        "high_risk": high_risk,
        "blocked": blocked,
        "unique_clients": unique_clients,
        "by_severity": {row["severity"]: row["count"] for row in severity_rows},
        "chain_valid": verify_chain(),
        "latest_at": latest["occurred_at"] if latest else None,
        "retention_days": config.AUDIT_LOG_RETENTION_DAYS,
    }


def reset_for_tests() -> None:
    global _INSERT_COUNT
    with _LOCK:
        _INITIALIZED_PATHS.clear()
        _INSERT_COUNT = 0
