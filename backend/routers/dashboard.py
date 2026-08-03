"""Authenticated operations-dashboard aggregation API."""

import csv
import io
import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from services import audit_log_service, auth_service, dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
COOKIE_NAME = "aigc_operator_session"


class ShadowReviewRequest(BaseModel):
    review_label: Literal["safe", "borderline", "unsafe"]


def _operator(request: Request) -> dict[str, Any]:
    user = auth_service.verify_session(request.cookies.get(COOKIE_NAME))
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录审核员账号")
    return user


@router.get("/overview")
async def dashboard_overview(
    request: Request,
    hours: int = Query(default=24, ge=1, le=168),
):
    user = _operator(request)
    return JSONResponse(
        dashboard_service.overview(hours, reviewer=user["username"]),
        headers={"Cache-Control": "no-store"},
    )


@router.put("/shadow-reviews/{event_id}")
async def resolve_shadow_review(
    event_id: str,
    body: ShadowReviewRequest,
    request: Request,
):
    user = _operator(request)
    try:
        review = audit_log_service.resolve_shadow_review(
            event_id, body.review_label, user["username"]
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="未找到含加密证据的可复核护栏事件") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail="请先打开取证详情并查看原始证据") from exc
    audit_log_service.record_safe(
        event_type="guardrail.shadow_review",
        module="guardrail",
        action="resolve_human_review",
        severity="warning",
        outcome="review",
        actor=user["username"],
        client_ip=request.client.host if request.client else "unknown",
        summary=f"人工复核样本：{review['reason_code']}",
        resource_id=event_id,
        metadata={
            "source_event_id": event_id,
            "review_label": review["review_label"],
            "reason_code": review["reason_code"],
        },
    )
    return JSONResponse(review, headers={"Cache-Control": "no-store"})


@router.get("/review-labels.csv")
async def export_review_labels(request: Request):
    user = _operator(request)
    reviews = audit_log_service.export_human_reviews()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "event_id", "content_hash", "occurred_at", "primary_verdict", "risk_code",
        "risk_score", "categories", "shadow_status", "shadow_decision",
        "is_disagreement", "human_label", "reason_code", "reviewer", "reviewed_at",
        "evidence_access_verified",
    ])
    for review in reviews:
        writer.writerow([
            review["event_id"], review.get("content_hash"), review["occurred_at"],
            review["primary_verdict"], review.get("risk_code"), review.get("risk_score"),
            json.dumps(review.get("categories", []), ensure_ascii=False),
            review.get("shadow_status"), review.get("shadow_decision"),
            review.get("is_disagreement"), review["review_label"],
            review.get("reason_code"), review.get("reviewer"), review.get("reviewed_at"),
            review.get("evidence_reviewed"),
        ])
    audit_log_service.record_safe(
        event_type="guardrail.review_export",
        module="guardrail",
        action="export_human_review_labels",
        outcome="success",
        actor=user["username"],
        client_ip=request.client.host if request.client else "unknown",
        summary=f"导出 {len(reviews)} 条人工复核标签元数据",
        metadata={"exported_count": len(reviews), "raw_content_included": False},
    )
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=aigc_human_review_labels.csv",
            "Cache-Control": "no-store",
        },
    )
