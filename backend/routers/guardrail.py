"""Large-model safety guardrail API."""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from services import guardrail_service

router = APIRouter(prefix="/api/guardrail", tags=["guardrail"])


class GuardrailCheckRequest(BaseModel):
    prompt: str = Field(default="", max_length=12_000)
    response: str = Field(default="", max_length=12_000)
    mode: str = Field(default="both", max_length=16)

    @model_validator(mode="after")
    def validate_content(self):
        if not self.prompt.strip() and not self.response.strip():
            raise ValueError("prompt or response must contain non-whitespace text")
        return self


class GuardrailCheckResponse(BaseModel):
    verdict: str
    decision: str
    risk_level: str
    risk_score: float
    intent: str
    categories: list[str]
    evidence: list[dict[str, Any]]
    actions: list[str]
    checks: list[dict[str, Any]]
    risk_code: str
    action: str
    redline_answer: str
    scores: dict[str, float]
    engine: dict[str, Any]


@router.post("/check", response_model=GuardrailCheckResponse)
async def check_guardrail(request: GuardrailCheckRequest):
    try:
        return await asyncio.to_thread(
            guardrail_service.check,
            request.prompt,
            request.response,
            request.mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
