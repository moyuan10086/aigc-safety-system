"""Versioned, tenant-aware external API contracts."""

from __future__ import annotations

import asyncio
import io
import json
import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Form, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from routers import guardrail as guardrail_router
from services import api_access_service, audit_log_service, tenant_artifact_service

router = APIRouter(prefix="/api/v1", tags=["external-api-v1"])


class ContentCheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12_000)


class ScanCreateRequest(BaseModel):
    preset: str = Field(default="quick", pattern="^(quick|standard)$")


class ReportCreateRequest(BaseModel):
    scan_id: str = Field(min_length=16, max_length=64)
    title: str | None = Field(default=None, max_length=120)


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if peer in {"127.0.0.1", "::1"}:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        return forwarded or peer
    return peer


def _envelope(request: Request, data: Any) -> dict[str, Any]:
    return {
        "api_version": "v1",
        "request_id": getattr(request.state, "request_id", None),
        "data": data,
    }


async def _metered(
    request: Request,
    *,
    scope: str,
    operation: str,
    run: Callable[[], Awaitable[Any]],
    response_status: int = 200,
) -> dict[str, Any]:
    client = api_access_service.require_api_key(request, scope=scope)
    started = time.perf_counter()
    status_code = 200
    try:
        data = await run()
        if isinstance(data, Response):
            return data
        payload = _envelope(request, data)
        return JSONResponse(status_code=response_status, content=payload) if response_status != 200 else payload
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception:
        status_code = 500
        raise
    finally:
        latency_ms = round((time.perf_counter() - started) * 1000)
        api_access_service.record_usage(
            client,
            operation=operation,
            status_code=status_code,
            latency_ms=latency_ms,
            client_ip=_client_ip(request),
            request_id=getattr(request.state, "request_id", None),
        )
        audit_log_service.record_safe(
            event_type="api.v1.usage",
            module="api",
            action=operation,
            severity="info" if status_code < 400 else "warning",
            outcome="success" if status_code < 400 else "error",
            actor=f"api:{client['key_id']}",
            client_ip=_client_ip(request),
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            latency_ms=latency_ms,
            summary=f"外部 API v1 调用：{operation}",
            resource_id=getattr(request.state, "request_id", None),
            metadata={
                "api_version": "v1",
                "api_key_id": client["key_id"],
                "tenant_id": client["tenant_id"],
                "operation": operation,
            },
        )


@router.get("/catalog")
async def catalog(request: Request):
    async def run():
        client = request.state.api_client
        return {
            "tenant_id": client["tenant_id"],
            "key_id": client["key_id"],
            "scopes": client["scopes"],
            "limits": {
                "requests_per_minute": client["rate_limit_per_minute"],
                "daily_quota": client["daily_quota"],
            },
            "operations": [
                {"method": "POST", "path": "/api/v1/guardrail/check", "scope": "guardrail:check"},
                {"method": "POST", "path": "/api/v1/guardrail/chat", "scope": "guardrail:chat"},
                {"method": "POST", "path": "/api/v1/guardrail/agent/check", "scope": "guardrail:agent"},
                {"method": "POST", "path": "/api/v1/guardrail/agent/result/check", "scope": "guardrail:agent"},
                {"method": "POST", "path": "/api/v1/guardrail/agent/trajectory/check", "scope": "guardrail:agent"},
                {"method": "POST", "path": "/api/v1/content/check", "scope": "content:check"},
                {"method": "POST", "path": "/api/v1/images/face", "scope": "image:face"},
                {"method": "POST", "path": "/api/v1/images/deepfake", "scope": "image:deepfake"},
                {"method": "POST", "path": "/api/v1/images/mllm", "scope": "image:mllm"},
                {"method": "POST", "path": "/api/v1/images/content-safety", "scope": "image:content-safety"},
                {"method": "POST", "path": "/api/v1/images/provenance/verify", "scope": "image:provenance"},
                {"method": "POST", "path": "/api/v1/images/audit-watermark/embed", "scope": "image:audit-watermark"},
                {"method": "POST", "path": "/api/v1/images/audit-watermark/decode", "scope": "image:audit-watermark"},
                {"method": "POST", "path": "/api/v1/images/watermarks/check", "scope": "image:watermark"},
                {"method": "POST", "path": "/api/v1/images/invisible-watermark/embed", "scope": "image:watermark"},
                {"method": "POST", "path": "/api/v1/images/invisible-watermark/check", "scope": "image:watermark"},
                {"method": "GET", "path": "/api/v1/usage", "scope": "usage:read"},
                {"method": "POST", "path": "/api/v1/scans", "scope": "scan:run"},
                {"method": "GET", "path": "/api/v1/scans", "scope": "scan:read"},
                {"method": "GET", "path": "/api/v1/reports", "scope": "report:read"},
                {"method": "POST", "path": "/api/v1/reports", "scope": "report:write"},
            ],
        }

    return await _metered(request, scope="usage:read", operation="catalog.read", run=run)


@router.post("/guardrail/check")
async def guardrail_check(
    body: guardrail_router.GuardrailCheckRequest,
    request: Request,
):
    async def run():
        return await guardrail_router.check_guardrail(body, request)

    return await _metered(
        request,
        scope="guardrail:check",
        operation="guardrail.check",
        run=run,
    )


@router.post("/guardrail/chat")
async def guardrail_chat(
    body: guardrail_router.GuardedChatRequest,
    request: Request,
):
    async def run():
        return await guardrail_router.guarded_chat(body, request)

    return await _metered(
        request,
        scope="guardrail:chat",
        operation="guardrail.chat",
        run=run,
    )


@router.post("/guardrail/agent/check")
async def guardrail_agent_check(
    body: guardrail_router.AgentActionCheckRequest,
    request: Request,
):
    async def run():
        return await guardrail_router.check_agent_action(body, request)

    return await _metered(
        request,
        scope="guardrail:agent",
        operation="guardrail.agent_check",
        run=run,
    )


@router.post("/guardrail/agent/result/check")
async def guardrail_agent_result_check(
    body: guardrail_router.AgentResultCheckRequest,
    request: Request,
):
    async def run():
        return await guardrail_router.check_agent_result(body, request)

    return await _metered(
        request,
        scope="guardrail:agent",
        operation="guardrail.agent_result_check",
        run=run,
    )


@router.post("/guardrail/agent/trajectory/check")
async def guardrail_agent_trajectory_check(
    body: guardrail_router.AgentTrajectoryCheckRequest,
    request: Request,
):
    async def run():
        return await guardrail_router.check_agent_trajectory(body, request)

    return await _metered(
        request,
        scope="guardrail:agent",
        operation="guardrail.agent_trajectory_check",
        run=run,
    )


@router.post("/content/check")
async def content_check(body: ContentCheckRequest, request: Request):
    from services import rag_service

    async def run():
        return await asyncio.to_thread(rag_service.check_content, body.text)

    return await _metered(
        request,
        scope="content:check",
        operation="content.check",
        run=run,
    )


async def _run_image(file: UploadFile, detector: Callable[[str], Any]) -> Any:
    from services import upload_service

    path = await upload_service.save_image_upload(file, Path("uploads"))
    try:
        return await asyncio.to_thread(detector, path)
    finally:
        if os.path.exists(path):
            os.unlink(path)


@router.post("/images/face")
async def image_face(request: Request, image: UploadFile = File(...)):
    from services import face_service

    async def run():
        return await _run_image(image, face_service.inspect)

    return await _metered(request, scope="image:face", operation="image.face", run=run)


@router.post("/images/deepfake")
async def image_deepfake(request: Request, image: UploadFile = File(...)):
    from services import deepfake_service

    async def run():
        return await _run_image(image, deepfake_service.detect)

    return await _metered(request, scope="image:deepfake", operation="image.deepfake", run=run)


@router.post("/images/mllm")
async def image_mllm(request: Request, image: UploadFile = File(...)):
    from services import mllm_service

    async def run():
        return await _run_image(image, mllm_service.analyze)

    return await _metered(request, scope="image:mllm", operation="image.mllm", run=run)


@router.post("/images/content-safety")
async def image_content_safety(request: Request, image: UploadFile = File(...)):
    from services import mllm_service

    async def run():
        return await _run_image(image, mllm_service.analyze_content_safety)

    return await _metered(
        request,
        scope="image:content-safety",
        operation="image.content_safety",
        run=run,
    )


@router.post("/images/provenance/verify")
async def image_provenance(request: Request, image: UploadFile = File(...)):
    from fastapi import HTTPException
    from services import provenance_service

    async def run():
        try:
            result = await _run_image(image, provenance_service.verify)
        except provenance_service.ProvenanceError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        audit_log_service.record_safe(
            event_type="image.provenance_verify", module="provenance", action="verify",
            summary="外部 API 图片来源证据验证", content_hash=result.get("content_hash"),
            metadata={"overall_state": result.get("overall_state"), "api": "v1"},
        )
        return result

    return await _metered(request, scope="image:provenance", operation="image.provenance_verify", run=run)


@router.post("/images/audit-watermark/embed")
async def image_audit_watermark_embed(
    request: Request, image: UploadFile = File(...), payload: str = Form(...),
):
    from services import audit_watermark_service, upload_service

    async def run():
        try:
            body = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="payload_json_invalid") from exc
        source = await upload_service.save_image_upload(image, Path("uploads"))
        try:
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "audit-copy.png"
                artifact = await asyncio.to_thread(audit_watermark_service.embed, source, output, body)
                archive = io.BytesIO()
                with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                    bundle.write(output, "audit-copy.png")
                    bundle.writestr("audit-sidecar.json", json.dumps(artifact["sidecar"], ensure_ascii=False))
                audit_log_service.record_safe(
                    event_type="image.audit_watermark_embed", module="provenance", action="embed",
                    summary="生成可逆审计副本", metadata={"api": "v1", "event_id": artifact["payload"].get("event_id")},
                )
                return Response(
                    content=archive.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="audit-watermark-artifact.zip"', "Cache-Control": "no-store"},
                )
        except audit_watermark_service.AuditWatermarkError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            Path(source).unlink(missing_ok=True)

    return await _metered(request, scope="image:audit-watermark", operation="image.audit_watermark_embed", run=run)


@router.post("/images/audit-watermark/decode")
async def image_audit_watermark_decode(
    request: Request, image: UploadFile = File(...), sidecar: UploadFile = File(...),
):
    from services import audit_watermark_service, upload_service

    async def run():
        source = await upload_service.save_image_upload(image, Path("uploads"))
        try:
            raw = await sidecar.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="sidecar_too_large")
            result = await asyncio.to_thread(audit_watermark_service.decode, source, json.loads(raw))
            audit_log_service.record_safe(
                event_type="image.audit_watermark_decode", module="provenance", action="decode",
                summary="核验可逆审计副本", metadata={"api": "v1", "payload_integrity": result["payload_integrity"]},
            )
            return result
        except (audit_watermark_service.AuditWatermarkError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            Path(source).unlink(missing_ok=True)

    return await _metered(request, scope="image:audit-watermark", operation="image.audit_watermark_decode", run=run)


@router.post("/images/watermarks/check")
async def image_watermark_check(
    request: Request, image: UploadFile = File(...), provider: str = Form(...), consent: bool = Form(False),
):
    from services import watermark_provider_service

    async def run():
        try:
            return await _run_image(
                image,
                lambda path: watermark_provider_service.check(path, provider=provider, consent=consent),
            )
        except watermark_provider_service.WatermarkProviderError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return await _metered(request, scope="image:watermark", operation="image.watermark_check", run=run)


@router.post("/images/invisible-watermark/embed")
async def image_invisible_watermark_embed(
    request: Request, image: UploadFile = File(...), payload: str = Form(...),
):
    from services import invisible_watermark_service, upload_service

    async def run():
        try:
            body = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="payload_json_invalid") from exc
        source = await upload_service.save_image_upload(image, Path("uploads"))
        try:
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "platform-watermarked.png"
                artifact = await asyncio.to_thread(
                    invisible_watermark_service.embed, source, output, body
                )
                audit_log_service.record_safe(
                    event_type="image.invisible_watermark_embed",
                    module="provenance",
                    action="embed",
                    summary="生成平台签名隐形水印图片",
                    metadata={"api": "v1", "content_id": artifact["payload"].get("content_id")},
                )
                return Response(
                    content=output.read_bytes(),
                    media_type="image/png",
                    headers={
                        "Content-Disposition": 'attachment; filename="platform-watermarked.png"',
                        "Cache-Control": "no-store",
                    },
                )
        except invisible_watermark_service.InvisibleWatermarkError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            Path(source).unlink(missing_ok=True)

    return await _metered(
        request,
        scope="image:watermark",
        operation="image.invisible_watermark_embed",
        run=run,
    )


@router.post("/images/invisible-watermark/check")
async def image_invisible_watermark_check(request: Request, image: UploadFile = File(...)):
    from services import invisible_watermark_service

    async def run():
        result = await _run_image(image, invisible_watermark_service.check)
        audit_log_service.record_safe(
            event_type="image.invisible_watermark_check",
            module="provenance",
            action="verify",
            summary="核验平台签名隐形水印",
            metadata={"api": "v1", "status": result.get("status")},
        )
        return result

    return await _metered(
        request,
        scope="image:watermark",
        operation="image.invisible_watermark_check",
        run=run,
    )


@router.get("/usage")
async def usage(request: Request, days: int = Query(default=1, ge=1, le=31)):
    async def run():
        return api_access_service.usage(request.state.api_client, days=days)

    return await _metered(request, scope="usage:read", operation="usage.read", run=run)


def _artifact_http_error(error: tenant_artifact_service.ArtifactError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message})


@router.post("/scans")
async def create_scan(body: ScanCreateRequest, request: Request):
    async def run():
        try:
            return tenant_artifact_service.create_scan(request.state.api_client, preset=body.preset)
        except tenant_artifact_service.ArtifactError as exc:
            raise _artifact_http_error(exc) from exc

    return await _metered(
        request,
        scope="scan:run",
        operation="scan.create",
        run=run,
        response_status=202,
    )


@router.get("/scans")
async def list_scans(request: Request, limit: int = Query(default=50, ge=1, le=100)):
    async def run():
        return {"items": tenant_artifact_service.list_scans(request.state.api_client, limit=limit)}

    return await _metered(request, scope="scan:read", operation="scan.list", run=run)


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: str, request: Request):
    async def run():
        try:
            return tenant_artifact_service.get_scan(request.state.api_client, scan_id)
        except tenant_artifact_service.ArtifactError as exc:
            raise _artifact_http_error(exc) from exc

    return await _metered(request, scope="scan:read", operation="scan.read", run=run)


@router.post("/reports")
async def create_report(body: ReportCreateRequest, request: Request):
    async def run():
        try:
            return tenant_artifact_service.create_scan_report(
                request.state.api_client, scan_id=body.scan_id, title=body.title
            )
        except tenant_artifact_service.ArtifactError as exc:
            raise _artifact_http_error(exc) from exc

    return await _metered(request, scope="report:write", operation="report.create", run=run)


@router.get("/reports")
async def list_reports(request: Request, limit: int = Query(default=50, ge=1, le=100)):
    async def run():
        return {"items": tenant_artifact_service.list_reports(request.state.api_client, limit=limit)}

    return await _metered(request, scope="report:read", operation="report.list", run=run)


@router.get("/reports/{report_id}")
async def get_report(report_id: str, request: Request):
    async def run():
        try:
            return tenant_artifact_service.get_report(request.state.api_client, report_id)
        except tenant_artifact_service.ArtifactError as exc:
            raise _artifact_http_error(exc) from exc

    return await _metered(request, scope="report:read", operation="report.read", run=run)


@router.get("/reports/{report_id}/download")
async def download_report(report_id: str, request: Request):
    client = api_access_service.require_api_key(request, scope="report:read")
    started = time.perf_counter()
    status_code = 200
    try:
        content, filename = tenant_artifact_service.report_download(client, report_id)
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )
    except tenant_artifact_service.ArtifactError as exc:
        status_code = exc.status_code
        raise _artifact_http_error(exc) from exc
    except Exception:
        status_code = 500
        raise
    finally:
        latency_ms = round((time.perf_counter() - started) * 1000)
        api_access_service.record_usage(
            client,
            operation="report.download",
            status_code=status_code,
            latency_ms=latency_ms,
            client_ip=_client_ip(request),
            request_id=getattr(request.state, "request_id", None),
        )
