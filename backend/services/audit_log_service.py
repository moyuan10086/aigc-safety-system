"""Persistent, privacy-conscious audit events with a tamper-evident hash chain."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import config
from cryptography.exceptions import InvalidTag
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
            CREATE TABLE IF NOT EXISTS guardrail_shadow_reviews (
                event_id TEXT PRIMARY KEY,
                review_label TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                reviewed_at TEXT NOT NULL,
                FOREIGN KEY(event_id) REFERENCES audit_events(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_shadow_reviews_reviewed_at
                ON guardrail_shadow_reviews(reviewed_at DESC);
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
        connection.commit()
    return event_id


def record_safe(**event: Any) -> str | None:
    """Best-effort logging must never make the protected business request fail."""
    try:
        return record(**event)
    except Exception:
        return None


def _evidence_key(value: str | None = None) -> bytes:
    value = value if value is not None else config.AUDIT_CONTENT_KEY
    if not value:
        raise RuntimeError("AUDIT_CONTENT_KEY is not configured")
    return hashlib.sha256(value.encode("utf-8")).digest()


def _evidence_keys() -> list[bytes]:
    values = [config.AUDIT_CONTENT_KEY]
    if config.AUDIT_CONTENT_PREVIOUS_KEY:
        values.append(config.AUDIT_CONTENT_PREVIOUS_KEY)
    return list(dict.fromkeys(_evidence_key(value) for value in values if value))


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
    plaintext = None
    for key in _evidence_keys():
        try:
            plaintext = AESGCM(key).decrypt(row["nonce"], row["ciphertext"], event_id.encode("ascii"))
            break
        except InvalidTag:
            continue
    if plaintext is None:
        raise RuntimeError("证据密钥不匹配，无法解密")
    data = json.loads(plaintext)
    data.update({
        "event_id": event_id,
        "content_types": row["content_types"].split(","),
        "dangerous": bool(row["dangerous"]),
        "created_at": row["created_at"],
        "encrypted_at_rest": True,
    })
    return data


def reencrypt_evidence() -> int:
    """Re-encrypt all evidence with the current key during a key rotation."""
    current_keys = _evidence_keys()
    if not current_keys:
        raise RuntimeError("AUDIT_CONTENT_KEY is not configured")
    current_key = current_keys[0]
    with _LOCK, closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT event_id, nonce, ciphertext FROM audit_evidence"
        ).fetchall()
        migrated = 0
        for row in rows:
            plaintext = None
            for key in current_keys:
                try:
                    plaintext = AESGCM(key).decrypt(
                        row["nonce"], row["ciphertext"], row["event_id"].encode("ascii")
                    )
                    break
                except InvalidTag:
                    continue
            if plaintext is None:
                raise RuntimeError(f"证据 {row['event_id']} 无法用当前或上一密钥解密")
            nonce = os.urandom(12)
            ciphertext = AESGCM(current_key).encrypt(
                nonce, plaintext, row["event_id"].encode("ascii")
            )
            connection.execute(
                "UPDATE audit_evidence SET nonce = ?, ciphertext = ? WHERE event_id = ?",
                (nonce, ciphertext, row["event_id"]),
            )
            migrated += 1
        connection.commit()
    return migrated


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


def get_event(event_id: str) -> dict[str, Any] | None:
    with closing(_connect()) as connection:
        row = connection.execute(
            """
            SELECT audit_events.*,
                   EXISTS(SELECT 1 FROM audit_evidence WHERE audit_evidence.event_id = audit_events.id)
                       AS has_evidence
            FROM audit_events WHERE audit_events.id = ?
            """,
            (event_id,),
        ).fetchone()
    return _row_to_event(row) if row else None


def export_events(*, limit: int = 5000, **filters: Any) -> list[dict[str, Any]]:
    where, params = _where(filters)
    with closing(_connect()) as connection:
        rows = connection.execute(
            f"SELECT audit_events.*, EXISTS(SELECT 1 FROM audit_evidence WHERE audit_evidence.event_id = audit_events.id) AS has_evidence FROM audit_events{where} ORDER BY occurred_at DESC, audit_events.rowid DESC LIMIT ?",
            [*params, max(1, min(limit, 5000))],
        ).fetchall()
    return [_row_to_event(row) for row in rows]


def verify_chain(db_path: str | Path | None = None) -> bool:
    if db_path is None:
        connection = _connect()
    else:
        connection = sqlite3.connect(
            f"file:{Path(db_path).resolve()}?mode=ro", uri=True, timeout=10
        )
        connection.row_factory = sqlite3.Row
    with closing(connection):
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


def dashboard_statistics(
    hours: int = 24,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Aggregate safe, structured audit fields for the operations dashboard."""
    hours = max(1, min(int(hours), 168))
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = now - timedelta(hours=hours)
    bucket_hours = 1 if hours <= 48 else 3 if hours <= 96 else 6
    bucket_count = math.ceil(hours / bucket_hours)
    bucket_seconds = bucket_hours * 3600
    buckets = [
        {
            "start": (start + timedelta(hours=index * bucket_hours))
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "events": 0,
            "alerts": 0,
            "blocked": 0,
            "latency_total_ms": 0,
            "latency_samples": 0,
        }
        for index in range(bucket_count)
    ]

    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT id, occurred_at, event_type, module, action, severity, outcome,
                   actor, client_ip, method, path, status_code, latency_ms, summary,
                   risk_code, risk_score, metadata_json
            FROM audit_events
            WHERE occurred_at >= ? AND occurred_at <= ?
            ORDER BY occurred_at ASC, rowid ASC
            """,
            (
                start.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            ),
        ).fetchall()

    total_events = len(rows)
    request_count = 0
    business_reviews = 0
    alerts = 0
    blocked = 0
    successful = 0
    latencies: list[int] = []
    clients: dict[str, dict[str, int]] = {}
    actors: dict[str, int] = {}
    modules: dict[str, int] = {}
    categories: dict[str, int] = {}
    recent_alerts: list[dict[str, Any]] = []

    for row in rows:
        event = dict(row)
        occurred_at = datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00"))
        is_alert = event["severity"] in {"warning", "high", "critical"} or event["outcome"] in {
            "review", "blocked", "denied", "error"
        }
        is_blocked = event["outcome"] in {"blocked", "denied"}
        is_success = event["outcome"] in {"success", "allowed"} and (
            event["status_code"] is None or event["status_code"] < 400
        )
        if event["event_type"] == "request.access":
            request_count += 1
        if event["event_type"] in {"guardrail.check", "guardrail.chat", "detect.review"}:
            business_reviews += 1
        alerts += int(is_alert)
        blocked += int(is_blocked)
        successful += int(is_success)
        modules[event["module"]] = modules.get(event["module"], 0) + 1

        latency = event["latency_ms"]
        if latency is not None:
            latencies.append(max(0, int(latency)))

        client_ip = event["client_ip"]
        if client_ip:
            source = clients.setdefault(client_ip, {"events": 0, "alerts": 0, "blocked": 0})
            source["events"] += 1
            source["alerts"] += int(is_alert)
            source["blocked"] += int(is_blocked)
        actor = event["actor"]
        if actor:
            actors[actor] = actors.get(actor, 0) + 1

        metadata = json.loads(event["metadata_json"] or "{}")
        event_categories = metadata.get("categories")
        if isinstance(event_categories, list):
            for category in {str(value)[:64] for value in event_categories if value}:
                categories[category] = categories.get(category, 0) + 1
        elif is_alert and event["risk_code"]:
            categories[event["risk_code"]] = categories.get(event["risk_code"], 0) + 1

        index = int((occurred_at - start).total_seconds() // bucket_seconds)
        if 0 <= index < len(buckets):
            bucket = buckets[index]
            bucket["events"] += 1
            bucket["alerts"] += int(is_alert)
            bucket["blocked"] += int(is_blocked)
            if latency is not None:
                bucket["latency_total_ms"] += max(0, int(latency))
                bucket["latency_samples"] += 1

        if is_alert:
            recent_alerts.append({
                "id": event["id"],
                "occurred_at": event["occurred_at"],
                "module": event["module"],
                "severity": event["severity"],
                "outcome": event["outcome"],
                "risk_code": event["risk_code"],
                "risk_score": event["risk_score"],
                "client_ip": event["client_ip"],
                "summary": event["summary"],
            })

    latency_sorted = sorted(latencies)
    p95_index = max(0, math.ceil(len(latency_sorted) * 0.95) - 1)
    p95_latency = latency_sorted[p95_index] if latency_sorted else 0
    average_latency = round(sum(latency_sorted) / len(latency_sorted)) if latency_sorted else 0
    timeline = []
    for bucket in buckets:
        samples = bucket.pop("latency_samples")
        total_latency = bucket.pop("latency_total_ms")
        timeline.append({
            **bucket,
            "avg_latency_ms": round(total_latency / samples) if samples else 0,
        })

    return {
        "window": {
            "hours": hours,
            "bucket_hours": bucket_hours,
            "start": start.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "end": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
        "summary": {
            "total_events": total_events,
            "request_count": request_count,
            "business_reviews": business_reviews,
            "alerts": alerts,
            "blocked": blocked,
            "successful": successful,
            "success_rate": round(successful / total_events * 100, 1) if total_events else 0.0,
            "block_rate": round(blocked / total_events * 100, 1) if total_events else 0.0,
            "average_latency_ms": average_latency,
            "p95_latency_ms": p95_latency,
            "unique_clients": len(clients),
            "unique_actors": len(actors),
        },
        "timeline": timeline,
        "risk_distribution": [
            {"name": name, "value": count}
            for name, count in sorted(categories.items(), key=lambda item: (-item[1], item[0]))[:10]
        ],
        "module_distribution": [
            {"name": name, "value": count}
            for name, count in sorted(modules.items(), key=lambda item: (-item[1], item[0]))
        ],
        "top_sources": [
            {"client_ip": ip, **counts}
            for ip, counts in sorted(clients.items(), key=lambda item: (-item[1]["events"], item[0]))[:10]
        ],
        "top_actors": [
            {"actor": actor, "events": count}
            for actor, count in sorted(actors.items(), key=lambda item: (-item[1], item[0]))[:10]
        ],
        "recent_alerts": list(reversed(recent_alerts[-12:])),
        "chain_valid": verify_chain(),
    }


def _primary_verdict(outcome: str) -> str | None:
    return {
        "allowed": "safe",
        "review": "borderline",
        "blocked": "unsafe",
        "denied": "unsafe",
    }.get(outcome)


def _shadow_reason(primary_verdict: str, shadow_decision: str, review_label: str) -> str:
    if review_label == "borderline":
        return "policy_ambiguous"
    if review_label == "safe":
        return "shadow_false_positive" if shadow_decision == "fail" else "primary_false_positive"
    if review_label == "unsafe":
        return "shadow_false_negative" if shadow_decision == "pass" else "primary_false_negative"
    return "reviewer_confirmation"


def shadow_review_statistics(
    hours: int = 24,
    *,
    now: datetime | None = None,
    queue_limit: int = 8,
) -> dict[str, Any]:
    """Aggregate metadata-only shadow comparisons and their structured reviews."""
    hours = max(1, min(int(hours), 168))
    queue_limit = max(1, min(int(queue_limit), 50))
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = now - timedelta(hours=hours)
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT audit_events.id, audit_events.occurred_at, audit_events.outcome,
                   audit_events.risk_code, audit_events.risk_score,
                   audit_events.content_hash, audit_events.metadata_json,
                   EXISTS(SELECT 1 FROM audit_evidence WHERE audit_evidence.event_id = audit_events.id)
                       AS has_evidence,
                   guardrail_shadow_reviews.review_label,
                   guardrail_shadow_reviews.reason_code,
                   guardrail_shadow_reviews.reviewer,
                   guardrail_shadow_reviews.reviewed_at
            FROM audit_events
            LEFT JOIN guardrail_shadow_reviews
                ON guardrail_shadow_reviews.event_id = audit_events.id
            WHERE audit_events.event_type = 'guardrail.check'
              AND audit_events.occurred_at >= ? AND audit_events.occurred_at <= ?
            ORDER BY audit_events.occurred_at DESC, audit_events.rowid DESC
            """,
            (
                start.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            ),
        ).fetchall()

    observed_events = 0
    evaluated_samples = 0
    agreements = 0
    disagreements = 0
    not_comparable = 0
    false_positive_candidates = 0
    false_negative_candidates = 0
    reviewed = 0
    latencies: list[float] = []
    statuses: dict[str, int] = {}
    review_labels: dict[str, int] = {}
    queue: list[dict[str, Any]] = []

    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        shadow = metadata.get("shadow_evaluation")
        if not isinstance(shadow, dict) or not shadow:
            continue
        observed_events += 1
        status = str(shadow.get("status") or "unknown")[:32]
        statuses[status] = statuses.get(status, 0) + 1
        if status != "ok":
            continue
        evaluated_samples += 1
        agreement = shadow.get("agreement")
        agreements += int(agreement is True)
        disagreements += int(agreement is False)
        not_comparable += int(agreement is None)
        latency = shadow.get("latency_ms")
        if isinstance(latency, (int, float)) and latency >= 0:
            latencies.append(float(latency))

        primary_verdict = _primary_verdict(row["outcome"])
        shadow_decision = str(shadow.get("decision") or "")
        if agreement is False and primary_verdict == "safe" and shadow_decision == "fail":
            false_positive_candidates += 1
        if agreement is False and primary_verdict == "unsafe" and shadow_decision == "pass":
            false_negative_candidates += 1

        if row["review_label"]:
            reviewed += 1
            review_labels[row["review_label"]] = review_labels.get(row["review_label"], 0) + 1

        if agreement is False and len(queue) < queue_limit:
            categories = metadata.get("categories")
            queue.append({
                "event_id": row["id"],
                "occurred_at": row["occurred_at"],
                "primary_verdict": primary_verdict,
                "risk_code": row["risk_code"],
                "risk_score": row["risk_score"],
                "content_hash": row["content_hash"],
                "categories": categories if isinstance(categories, list) else [],
                "shadow_decision": shadow_decision,
                "shadow_confidence": shadow.get("confidence"),
                "shadow_alert": bool(shadow.get("alert")),
                "shadow_latency_ms": latency,
                "shadow_risk_type": str(shadow.get("risk_type") or "")[:64],
                "has_evidence": bool(row["has_evidence"]),
                "review_label": row["review_label"],
                "reason_code": row["reason_code"],
                "reviewer": row["reviewer"],
                "reviewed_at": row["reviewed_at"],
            })

    latency_sorted = sorted(latencies)
    p95_index = max(0, math.ceil(len(latency_sorted) * 0.95) - 1)
    return {
        "observed_events": observed_events,
        "evaluated_samples": evaluated_samples,
        "agreement_count": agreements,
        "disagreement_count": disagreements,
        "not_comparable_count": not_comparable,
        "agreement_rate": round(agreements / (agreements + disagreements) * 100, 1)
        if agreements + disagreements
        else 0.0,
        "false_positive_candidates": false_positive_candidates,
        "false_negative_candidates": false_negative_candidates,
        "pending_reviews": max(0, disagreements - reviewed),
        "reviewed_count": reviewed,
        "p95_latency_ms": round(latency_sorted[p95_index], 3) if latency_sorted else 0.0,
        "statuses": statuses,
        "review_labels": review_labels,
        "queue": queue,
    }


def resolve_shadow_review(event_id: str, review_label: str, reviewer: str) -> dict[str, Any]:
    if review_label not in {"safe", "borderline", "unsafe"}:
        raise ValueError("invalid_review_label")
    with _LOCK, closing(_connect()) as connection:
        row = connection.execute(
            "SELECT outcome, metadata_json FROM audit_events WHERE id = ? AND event_type = 'guardrail.check'",
            (event_id,),
        ).fetchone()
        if row is None:
            raise LookupError("shadow_disagreement_not_found")
        try:
            shadow = json.loads(row["metadata_json"] or "{}").get("shadow_evaluation") or {}
        except (TypeError, json.JSONDecodeError) as exc:
            raise LookupError("shadow_disagreement_not_found") from exc
        primary_verdict = _primary_verdict(row["outcome"])
        shadow_decision = str(shadow.get("decision") or "")
        if shadow.get("status") != "ok" or shadow.get("agreement") is not False:
            raise LookupError("shadow_disagreement_not_found")
        reason_code = _shadow_reason(primary_verdict or "unknown", shadow_decision, review_label)
        reviewed_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        connection.execute(
            """
            INSERT INTO guardrail_shadow_reviews
                (event_id, review_label, reason_code, reviewer, reviewed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                review_label = excluded.review_label,
                reason_code = excluded.reason_code,
                reviewer = excluded.reviewer,
                reviewed_at = excluded.reviewed_at
            """,
            (event_id, review_label, reason_code, _clean_text(reviewer, 128) or "operator", reviewed_at),
        )
        connection.commit()
    return {
        "event_id": event_id,
        "review_label": review_label,
        "reason_code": reason_code,
        "reviewer": _clean_text(reviewer, 128) or "operator",
        "reviewed_at": reviewed_at,
    }


def reset_for_tests() -> None:
    global _INSERT_COUNT
    with _LOCK:
        _INITIALIZED_PATHS.clear()
        _INSERT_COUNT = 0
