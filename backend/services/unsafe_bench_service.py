"""Optional adapter for the official UnsafeBench/PerspectiveVision service.

UnsafeBench is primarily an evaluation framework. The platform therefore
keeps this expert behind an explicit endpoint switch instead of pretending the
benchmark repository is an online API. Results remain specialist evidence and
do not replace the primary content-safety decision.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import httpx

from config import (
    PROXY_URL,
    UNSAFE_BENCH_ENABLED,
    UNSAFE_BENCH_ENDPOINT,
    UNSAFE_BENCH_MODEL,
    UNSAFE_BENCH_TIMEOUT_SECONDS,
)

UNSAFEBENCH_CATEGORIES = (
    "sexual", "violence", "hateful", "shocking", "self_harm", "political",
    "illegal_activity", "deception", "spam", "harassment", "health",
)
UNSAFEBENCH_ALIASES = {"violent": "violence", "disturbing": "shocking"}


def _base(status: str, *, latency_ms: int = 0, error_code: str | None = None) -> dict:
    return {
        "provider": "unsafe_bench",
        "model": UNSAFE_BENCH_MODEL,
        "status": status,
        "latency_ms": latency_ms,
        "error_code": error_code,
        "privacy": {"external_upload": bool(UNSAFE_BENCH_ENDPOINT), "retained_by_platform": False},
    }


def _status_from_payload(payload: dict, risk_score: float | None) -> str:
    verdict = str(payload.get("verdict") or "").strip().lower()
    categories = payload.get("categories", [])
    if verdict in {"unsafe", "review", "risk", "risky"} or (risk_score is not None and risk_score >= 0.5):
        return "detected"
    if verdict in {"safe", "not_detected", "clean"} or (risk_score is not None and risk_score < 0.5):
        return "not_detected"
    if verdict in {"unsure", "uncertain", "inconclusive"}:
        return "inconclusive"
    return "detected" if isinstance(categories, list) and categories else "inconclusive"


def analyze(image_path: str) -> dict:
    if not UNSAFE_BENCH_ENABLED:
        return _base("not_configured", error_code="disabled")
    if not UNSAFE_BENCH_ENDPOINT:
        return _base("not_configured", error_code="endpoint_missing")

    started = time.perf_counter()
    content_hash = hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
    try:
        kwargs = {"timeout": UNSAFE_BENCH_TIMEOUT_SECONDS}
        if PROXY_URL:
            kwargs["proxy"] = PROXY_URL
        with httpx.Client(**kwargs) as client:
            with open(image_path, "rb") as handle:
                response = client.post(
                    UNSAFE_BENCH_ENDPOINT,
                    files={"file": (Path(image_path).name, handle, "application/octet-stream")},
                    headers={"X-Content-SHA256": content_hash},
                )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("provider response must be an object")
        risk_score = payload.get("risk_score")
        try:
            risk_score = max(0.0, min(1.0, float(risk_score))) if risk_score is not None else None
        except (TypeError, ValueError):
            risk_score = None
        verdict = str(payload.get("verdict") or "").strip().lower()
        status = _status_from_payload(payload, risk_score)
        result = _base(status, latency_ms=round((time.perf_counter() - started) * 1000))
        raw_scores = payload.get("category_scores", {})
        category_scores = {
            UNSAFEBENCH_ALIASES.get(str(code), str(code)): value
            for code, value in raw_scores.items()
        } if isinstance(raw_scores, dict) else {}
        raw_categories = payload.get("categories", [])
        categories = [UNSAFEBENCH_ALIASES.get(str(code), str(code)) for code in raw_categories] if isinstance(raw_categories, list) else []
        result.update({
            "verdict": verdict or None,
            "risk_score": risk_score,
            "category_scores": category_scores,
            "categories": categories,
            "q16_score": payload.get("q16_score"),
            "q16_verdict": payload.get("q16_verdict"),
            "supported_categories": list(UNSAFEBENCH_CATEGORIES),
            "content_hash": content_hash,
        })
        return result
    except httpx.TimeoutException:
        return _base("inconclusive", latency_ms=round((time.perf_counter() - started) * 1000), error_code="timeout")
    except Exception as exc:
        return _base("inconclusive", latency_ms=round((time.perf_counter() - started) * 1000), error_code=type(exc).__name__)
