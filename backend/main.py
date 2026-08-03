import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from routers.detect import router as detect_router
from routers.system import router as system_router
from routers.garak_scan import router as garak_router
from routers.kb import router as kb_router
from routers.guardrail import router as guardrail_router
from routers.auth import router as auth_router
from routers.audit import router as audit_router
from services import audit_log_service, auth_service
import config

app = FastAPI(title="AIGC 内容安全审核系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if peer in {"127.0.0.1", "::1"}:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        return forwarded or peer
    return peer


@app.middleware("http")
async def audit_http_requests(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "").strip()
    if not (8 <= len(request_id) <= 64 and request_id.replace("-", "").isalnum()):
        request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        if response is not None:
            response.headers["X-Request-ID"] = request_id
        path = request.url.path
        if path.startswith("/api/") and not path.startswith("/api/audit/") and path != "/api/health":
            status_code = response.status_code if response is not None else 500
            user = auth_service.verify_session(request.cookies.get("aigc_operator_session"))
            outcome = "success"
            severity = "info"
            if status_code >= 500:
                outcome, severity = "error", "high"
            elif status_code in {401, 403, 429}:
                outcome, severity = "denied", "warning"
            elif status_code >= 400:
                outcome, severity = "error", "warning"
            audit_log_service.record_safe(
                event_type="request.access",
                module=path.split("/")[2] if len(path.split("/")) > 2 else "system",
                action="api_request",
                severity=severity,
                outcome=outcome,
                actor=user["username"] if user else "anonymous",
                client_ip=_client_ip(request),
                method=request.method,
                path=path,
                status_code=status_code,
                latency_ms=round((time.perf_counter() - started) * 1000),
                summary=f"{request.method} {path} 返回 {status_code}",
                resource_id=request_id,
            )

app.include_router(detect_router)
app.include_router(system_router)
app.include_router(garak_router)
app.include_router(kb_router)
app.include_router(guardrail_router)
app.include_router(auth_router)
app.include_router(audit_router)

@app.get("/api/health", tags=["system"])
async def health_check():
    return {"status": "ok", "service": "aigc-safety-system"}

dist = Path(__file__).parent.parent / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = dist / "index.html"
        return FileResponse(str(index))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=True)
