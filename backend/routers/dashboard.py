"""Authenticated operations-dashboard aggregation API."""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
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
    _operator(request)
    return JSONResponse(
        dashboard_service.overview(hours),
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
        raise HTTPException(status_code=404, detail="未找到可复核的影子分歧事件") from exc
    audit_log_service.record_safe(
        event_type="guardrail.shadow_review",
        module="guardrail",
        action="resolve_shadow_disagreement",
        severity="warning",
        outcome="review",
        actor=user["username"],
        client_ip=request.client.host if request.client else "unknown",
        summary=f"影子分歧复核：{review['reason_code']}",
        resource_id=event_id,
        metadata={
            "source_event_id": event_id,
            "review_label": review["review_label"],
            "reason_code": review["reason_code"],
        },
    )
    return JSONResponse(review, headers={"Cache-Control": "no-store"})
