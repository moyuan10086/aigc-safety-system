"""Authenticated operations-dashboard aggregation API."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from services import auth_service, dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
COOKIE_NAME = "aigc_operator_session"


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
