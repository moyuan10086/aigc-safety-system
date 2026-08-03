"""Minimal API surface for secret-free guardrail regression."""

from __future__ import annotations

import sys
import os
from pathlib import Path

from fastapi import FastAPI

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

for switch in (
    "GUARDRAIL_ENABLE_RAG",
    "GUARDRAIL_ENABLE_MLLM",
    "GUARDRAIL_ENABLE_QWEN_CLASSIFIER",
    "GUARDRAIL_ENABLE_SINGGUARD_CLASSIFIER",
    "GUARDRAIL_ENABLE_XGBOOST_SHADOW",
):
    os.environ[switch] = "false"

from routers.guardrail import router as guardrail_router  # noqa: E402
from services import audit_log_service  # noqa: E402

# Regression runs contain synthetic attacks and intentionally have no
# production encryption key. Do not persist requests from this minimal app.
def _do_not_persist(**_values: object) -> str:
    return ""


audit_log_service.record_safe = _do_not_persist

app = FastAPI(title="AIGC guardrail offline evaluation")
app.include_router(guardrail_router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "guardrail-evaluation"}
