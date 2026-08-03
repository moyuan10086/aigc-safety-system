import secrets

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
import config

router = APIRouter(prefix="/api/system")

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
