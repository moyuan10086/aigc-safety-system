import secrets

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
import config
from services import audit_log_service, auth_service, readiness_service

router = APIRouter(prefix="/api/system")
COOKIE_NAME = "aigc_operator_session"


def _operator(request: Request) -> dict[str, Any]:
    user = auth_service.verify_session(request.cookies.get(COOKIE_NAME))
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录审核员账号")
    return user

@router.get("/info")
async def system_info():
    return JSONResponse({
        "mllm_model": config.MLLM_MODEL,
        "chat_model": config.CHAT_MODEL_NAME,
        "mllm_configured": bool(config.MLLM_API_KEY),
        "chat_model_configured": bool(
            config.CHAT_MODEL_API_KEY
            and config.CHAT_MODEL_BASE_URL
            and config.CHAT_MODEL_NAME
        ),
        "deepfake_configured": bool(config.DEEPFAKE_MODEL_PATH),
        "rag_configured": bool(config.CHROMA_PATH),
        "lexicon_configured": bool(config.LEXICON_PATH),
        "config_writable": config.SYSTEM_CONFIG_WRITABLE,
    })


@router.get("/readiness")
async def system_readiness(refresh: bool = Query(default=False)):
    return JSONResponse(
        readiness_service.snapshot(refresh=refresh),
        headers={"Cache-Control": "no-store"},
    )


@router.post("/readiness/probe")
async def probe_model_readiness(request: Request):
    user = _operator(request)
    if not config.AUDIT_STORE_RAW_CONTENT or not config.AUDIT_CONTENT_KEY:
        raise HTTPException(status_code=503, detail="加密证据库未就绪，拒绝发起真实模型探测")
    result, evidence = readiness_service.active_model_probe()
    event_id = audit_log_service.record(
        event_type="system.readiness_probe",
        module="system",
        action="probe_guarded_model",
        severity="info" if result["status"] == "ready" else "warning",
        outcome="success" if result["status"] == "ready" else "error",
        actor=user["username"],
        client_ip=request.client.host if request.client else "unknown",
        summary=f"现场演示模型链路探测：{result['status']}",
        resource_id=request.state.request_id if hasattr(request.state, "request_id") else None,
        metadata={
            "status": result["status"],
            "cached": result["cached"],
            "model_called": result["model_called"],
            "attempts": result.get("attempts"),
            "max_attempts": result.get("max_attempts"),
            "recovered_after_retry": result.get("recovered_after_retry"),
            "model": result.get("model"),
            "latency_ms": result.get("latency_ms"),
            "input_verdict": result.get("input_verdict"),
            "output_verdict": result.get("output_verdict"),
            "output_sha256": result.get("output_sha256"),
            "input_experts": result.get("input_experts", {}),
            "output_experts": result.get("output_experts", {}),
            "inconclusive_components": {
                "input": result.get("input_inconclusive_components", []),
                "output": result.get("output_inconclusive_components", []),
                "final": result.get("final_inconclusive_components", []),
            },
            "error_code": result.get("error_code"),
        },
    )
    if evidence:
        audit_log_service.store_evidence(
            event_id,
            prompt=evidence["prompt"],
            response=evidence["response"],
            dangerous=bool(result.get("quarantined")),
        )
        result["evidence_event_id"] = event_id
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


class ConfigUpdate(BaseModel):
    mllm_base_url: str = ""
    mllm_model: str = ""
    mllm_api_key: str = ""
    deepfake_model_path: str = ""
    chroma_path: str = ""
    lexicon_path: str = ""


@router.post("/config")
async def update_config(
    body: ConfigUpdate,
    x_admin_token: str | None = Header(default=None),
):
    if not config.SYSTEM_CONFIG_WRITABLE:
        raise HTTPException(
            status_code=403,
            detail="运行时配置已关闭，请通过服务器环境变量更新",
        )
    if not config.SYSTEM_ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="服务器未配置管理令牌")
    if not x_admin_token or not secrets.compare_digest(
        x_admin_token, config.SYSTEM_ADMIN_TOKEN
    ):
        raise HTTPException(status_code=401, detail="管理令牌无效")
    env_path = Path(__file__).parents[1] / ".env"
    mapping = {
        "MLLM_BASE_URL": body.mllm_base_url,
        "MLLM_MODEL": body.mllm_model,
        "MLLM_API_KEY": body.mllm_api_key,
        "DEEPFAKE_MODEL_PATH": body.deepfake_model_path,
        "CHROMA_PATH": body.chroma_path,
        "LEXICON_PATH": body.lexicon_path,
    }
    existing = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k = line.split("=", 1)[0].strip()
                existing[k] = line
    for k, v in mapping.items():
        if v:
            existing[k] = f"{k}={v}"
    env_path.write_text("\n".join(existing.values()) + "\n", encoding="utf-8")

    # Update in-memory config
    if body.mllm_base_url:
        config.MLLM_BASE_URL = body.mllm_base_url
    if body.mllm_model:
        config.MLLM_MODEL = body.mllm_model
    if body.mllm_api_key:
        config.MLLM_API_KEY = body.mllm_api_key
    if body.deepfake_model_path:
        config.DEEPFAKE_MODEL_PATH = body.deepfake_model_path
    if body.chroma_path:
        config.CHROMA_PATH = body.chroma_path
    if body.lexicon_path:
        config.LEXICON_PATH = body.lexicon_path

    return {"status": "ok"}
