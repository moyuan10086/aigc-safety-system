from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
import config

router = APIRouter(prefix="/api/system")

@router.get("/info")
async def system_info():
    return JSONResponse({
        "mllm_model": config.MLLM_MODEL,
        "mllm_base_url": config.MLLM_BASE_URL,
        "deepfake_model_path": config.DEEPFAKE_MODEL_PATH,
        "chroma_path": config.CHROMA_PATH,
        "lexicon_path": config.LEXICON_PATH,
    })


class ConfigUpdate(BaseModel):
    mllm_base_url: str = ""
    mllm_model: str = ""
    mllm_api_key: str = ""
    deepfake_model_path: str = ""
    chroma_path: str = ""
    lexicon_path: str = ""


@router.post("/config")
async def update_config(body: ConfigUpdate):
    env_path = Path(__file__).parents[1] / ".env"
    lines = []
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
    if body.mllm_base_url: config.MLLM_BASE_URL = body.mllm_base_url
    if body.mllm_model: config.MLLM_MODEL = body.mllm_model
    if body.mllm_api_key: config.MLLM_API_KEY = body.mllm_api_key
    if body.deepfake_model_path: config.DEEPFAKE_MODEL_PATH = body.deepfake_model_path
    if body.chroma_path: config.CHROMA_PATH = body.chroma_path
    if body.lexicon_path: config.LEXICON_PATH = body.lexicon_path

    return {"status": "ok"}
