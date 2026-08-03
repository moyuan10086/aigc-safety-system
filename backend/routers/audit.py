"""Authenticated audit-log query and evidence export endpoints."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

from services import audit_log_service, auth_service

router = APIRouter(prefix="/api/audit", tags=["audit"])
COOKIE_NAME = "aigc_operator_session"


def _operator(request: Request) -> dict[str, Any]:
    user = auth_service.verify_session(request.cookies.get(COOKIE_NAME))
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录审核员账号")
    return user


def _filters(
    module: str | None,
    severity: str | None,
    outcome: str | None,
    event_type: str | None,
    keyword: str | None,
    start: str | None,
    end: str | None,
) -> dict[str, str | None]:
    return {
        "module": module,
        "severity": severity,
        "outcome": outcome,
        "event_type": event_type,
        "keyword": keyword.strip()[:120] if keyword else None,
        "start": start,
        "end": end,
    }


@router.get("/stats")
async def audit_stats(request: Request):
    _operator(request)
    return audit_log_service.statistics()


@router.get("/logs")
async def audit_logs(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    module: str | None = None,
    severity: str | None = None,
    outcome: str | None = None,
    event_type: str | None = None,
    keyword: str | None = None,
    start: str | None = None,
    end: str | None = None,
):
    _operator(request)
    return audit_log_service.list_events(
        page=page,
        page_size=page_size,
        **_filters(module, severity, outcome, event_type, keyword, start, end),
    )


@router.get("/logs/{event_id}/evidence")
async def audit_evidence(event_id: str, request: Request):
    user = _operator(request)
    try:
        evidence = audit_log_service.get_evidence(event_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="隔离证据密钥不可用") from exc
    if evidence is None:
        raise HTTPException(status_code=404, detail="该日志没有原始证据")
    audit_log_service.record_safe(
        event_type="audit.evidence_access",
        module="audit",
        action="reveal_raw_evidence",
        severity="warning" if evidence["dangerous"] else "info",
        outcome="success",
        actor=user["username"],
        client_ip=request.client.host if request.client else "unknown",
        summary="审核员查看加密原始证据",
        resource_id=event_id,
        metadata={"dangerous": evidence["dangerous"], "content_types": evidence["content_types"]},
    )
    return JSONResponse(evidence, headers={"Cache-Control": "no-store"})


@router.get("/export.csv")
async def export_audit_logs(
    request: Request,
    module: str | None = None,
    severity: str | None = None,
    outcome: str | None = None,
    event_type: str | None = None,
    keyword: str | None = None,
    start: str | None = None,
    end: str | None = None,
):
    user = _operator(request)
    events = audit_log_service.export_events(
        **_filters(module, severity, outcome, event_type, keyword, start, end)
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "occurred_at", "event_type", "module", "action", "severity",
        "outcome", "actor", "client_ip", "method", "path", "status_code",
        "latency_ms", "summary", "resource_id", "risk_code", "risk_score",
        "content_hash", "record_hash", "metadata",
    ])
    for event in events:
        writer.writerow([
            event.get(key) for key in (
                "id", "occurred_at", "event_type", "module", "action", "severity",
                "outcome", "actor", "client_ip", "method", "path", "status_code",
                "latency_ms", "summary", "resource_id", "risk_code", "risk_score",
                "content_hash", "record_hash",
            )
        ] + [json.dumps(event.get("metadata", {}), ensure_ascii=False, sort_keys=True)])
    audit_log_service.record_safe(
        event_type="audit.export",
        module="audit",
        action="export_csv",
        severity="info",
        outcome="success",
        actor=user["username"],
        summary=f"导出 {len(events)} 条审计日志",
        metadata={"exported_count": len(events)},
    )
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=aigc_audit_logs.csv"},
    )
