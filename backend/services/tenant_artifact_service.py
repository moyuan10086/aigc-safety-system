"""Tenant-owned asynchronous scans and downloadable security reports."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config

_LOCK = threading.RLock()
_INITIALIZED_PATHS: set[str] = set()
_EXECUTOR = ThreadPoolExecutor(
    max_workers=max(1, min(int(config.API_SCAN_MAX_CONCURRENCY), 4)),
    thread_name_prefix="tenant-garak-scan",
)
ALLOWED_PRESETS = {"quick", "standard"}


class ArtifactError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


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
            CREATE TABLE IF NOT EXISTS tenant_scan_jobs (
                scan_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                key_id TEXT NOT NULL,
                preset TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                result_json TEXT,
                error_code TEXT,
                error_message TEXT,
                FOREIGN KEY(key_id) REFERENCES api_keys(key_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_tenant_scans_owner_time
                ON tenant_scan_jobs(tenant_id, key_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS tenant_reports (
                report_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                key_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                FOREIGN KEY(key_id) REFERENCES api_keys(key_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_tenant_reports_owner_time
                ON tenant_reports(tenant_id, key_id, created_at DESC);
            """
        )
        connection.execute(
            """
            UPDATE tenant_scan_jobs
            SET status = 'failed', finished_at = ?, error_code = 'WORKER_RESTARTED',
                error_message = '扫描服务重启，请重新提交任务'
            WHERE status IN ('queued', 'running')
            """,
            (_iso(),),
        )
        connection.commit()
        _INITIALIZED_PATHS.add(key)


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _owner(client: dict[str, Any]) -> tuple[str, str]:
    return str(client["tenant_id"]), str(client["key_id"])


def _scan_public(row: sqlite3.Row) -> dict[str, Any]:
    result = json.loads(row["result_json"]) if row["result_json"] else None
    return {
        "scan_id": row["scan_id"],
        "preset": row["preset"],
        "status": row["status"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "result": result,
        "error": (
            {"code": row["error_code"], "message": row["error_message"]}
            if row["error_code"]
            else None
        ),
    }


def _report_public(row: sqlite3.Row, *, include_payload: bool = False) -> dict[str, Any]:
    value = {
        "report_id": row["report_id"],
        "source_type": row["source_type"],
        "source_id": row["source_id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "sha256": row["sha256"],
    }
    if include_payload:
        value["payload"] = json.loads(row["payload_json"])
    return value


def _run_garak_scan(preset: str) -> list[dict[str, Any]]:
    from routers.garak_scan import run_preset_sync

    return run_preset_sync(preset)


def _execute_scan(scan_id: str) -> None:
    with _LOCK, closing(_connect()) as connection:
        row = connection.execute(
            "SELECT preset FROM tenant_scan_jobs WHERE scan_id = ? AND status = 'queued'",
            (scan_id,),
        ).fetchone()
        if row is None:
            return
        preset = row["preset"]
        connection.execute(
            "UPDATE tenant_scan_jobs SET status = 'running', started_at = ? WHERE scan_id = ?",
            (_iso(), scan_id),
        )
        connection.commit()
    try:
        results = _run_garak_scan(preset)
        summary = {
            "probes": results,
            "totals": {
                name: sum(int(item.get(name, 0)) for item in results)
                for name in ("passed", "failed", "errors", "total")
            },
            "engine": "garak",
            "real_execution": True,
        }
        with _LOCK, closing(_connect()) as connection:
            connection.execute(
                """
                UPDATE tenant_scan_jobs
                SET status = 'completed', finished_at = ?, result_json = ?
                WHERE scan_id = ?
                """,
                (_iso(), json.dumps(summary, ensure_ascii=False, separators=(",", ":")), scan_id),
            )
            connection.commit()
    except Exception:
        with _LOCK, closing(_connect()) as connection:
            connection.execute(
                """
                UPDATE tenant_scan_jobs
                SET status = 'failed', finished_at = ?, error_code = 'SCAN_EXECUTION_FAILED',
                    error_message = '扫描执行失败，请检查模型与 garak 服务配置'
                WHERE scan_id = ?
                """,
                (_iso(), scan_id),
            )
            connection.commit()


def create_scan(client: dict[str, Any], *, preset: str) -> dict[str, Any]:
    if preset not in ALLOWED_PRESETS:
        raise ArtifactError("INVALID_SCAN_PRESET", "外部扫描仅支持 quick 或 standard")
    tenant_id, key_id = _owner(client)
    with _LOCK, closing(_connect()) as connection:
        active = connection.execute(
            """
            SELECT COUNT(*) FROM tenant_scan_jobs
            WHERE tenant_id = ? AND key_id = ? AND status IN ('queued', 'running')
            """,
            (tenant_id, key_id),
        ).fetchone()[0]
        if int(active) >= max(1, int(config.API_SCAN_MAX_ACTIVE_PER_KEY)):
            raise ArtifactError("SCAN_CONCURRENCY_LIMIT", "当前 API Key 已有扫描任务在排队或执行", 409)
        scan_id = uuid.uuid4().hex
        connection.execute(
            """
            INSERT INTO tenant_scan_jobs
                (scan_id, tenant_id, key_id, preset, status, created_at)
            VALUES (?, ?, ?, ?, 'queued', ?)
            """,
            (scan_id, tenant_id, key_id, preset, _iso()),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM tenant_scan_jobs WHERE scan_id = ?", (scan_id,)
        ).fetchone()
    _EXECUTOR.submit(_execute_scan, scan_id)
    return _scan_public(row)


def list_scans(client: dict[str, Any], *, limit: int = 50) -> list[dict[str, Any]]:
    tenant_id, key_id = _owner(client)
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT * FROM tenant_scan_jobs
            WHERE tenant_id = ? AND key_id = ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (tenant_id, key_id, max(1, min(int(limit), 100))),
        ).fetchall()
    return [_scan_public(row) for row in rows]


def get_scan(client: dict[str, Any], scan_id: str) -> dict[str, Any]:
    tenant_id, key_id = _owner(client)
    with closing(_connect()) as connection:
        row = connection.execute(
            """
            SELECT * FROM tenant_scan_jobs
            WHERE scan_id = ? AND tenant_id = ? AND key_id = ?
            """,
            (scan_id, tenant_id, key_id),
        ).fetchone()
    if row is None:
        raise ArtifactError("SCAN_NOT_FOUND", "扫描任务不存在", 404)
    return _scan_public(row)


def create_scan_report(
    client: dict[str, Any], *, scan_id: str, title: str | None = None
) -> dict[str, Any]:
    scan = get_scan(client, scan_id)
    if scan["status"] != "completed":
        raise ArtifactError("SCAN_NOT_COMPLETED", "扫描任务完成后才能生成报告", 409)
    tenant_id, key_id = _owner(client)
    report_id = uuid.uuid4().hex
    created_at = _iso()
    safe_title = " ".join((title or f"主动安全扫描报告 {scan_id[:8]}").split())[:120]
    payload = {
        "schema_version": "1.0",
        "report_id": report_id,
        "tenant_id": tenant_id,
        "source": {"type": "scan", "id": scan_id},
        "title": safe_title,
        "created_at": created_at,
        "scan": scan,
        "content_policy": "本报告仅包含扫描汇总，不包含原始提示词、模型输出或 API Key。",
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    with _LOCK, closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO tenant_reports
                (report_id, tenant_id, key_id, source_type, source_id, title,
                 created_at, payload_json, sha256)
            VALUES (?, ?, ?, 'scan', ?, ?, ?, ?, ?)
            """,
            (report_id, tenant_id, key_id, scan_id, safe_title, created_at, payload_json, digest),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM tenant_reports WHERE report_id = ?", (report_id,)
        ).fetchone()
    return _report_public(row, include_payload=True)


def list_reports(client: dict[str, Any], *, limit: int = 50) -> list[dict[str, Any]]:
    tenant_id, key_id = _owner(client)
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT * FROM tenant_reports
            WHERE tenant_id = ? AND key_id = ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (tenant_id, key_id, max(1, min(int(limit), 100))),
        ).fetchall()
    return [_report_public(row) for row in rows]


def get_report(
    client: dict[str, Any], report_id: str, *, include_payload: bool = True
) -> dict[str, Any]:
    tenant_id, key_id = _owner(client)
    with closing(_connect()) as connection:
        row = connection.execute(
            """
            SELECT * FROM tenant_reports
            WHERE report_id = ? AND tenant_id = ? AND key_id = ?
            """,
            (report_id, tenant_id, key_id),
        ).fetchone()
    if row is None:
        raise ArtifactError("REPORT_NOT_FOUND", "报告不存在", 404)
    return _report_public(row, include_payload=include_payload)


def report_download(client: dict[str, Any], report_id: str) -> tuple[bytes, str]:
    report = get_report(client, report_id, include_payload=True)
    content = json.dumps(report["payload"], ensure_ascii=False, indent=2).encode("utf-8")
    return content, f"scan_report_{report_id}.json"


def reset_for_tests() -> None:
    with _LOCK:
        _INITIALIZED_PATHS.clear()
