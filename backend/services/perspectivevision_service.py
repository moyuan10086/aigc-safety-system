"""Client adapter for the isolated PerspectiveVision-LLaVA reviewer."""

from __future__ import annotations

import hashlib
import io
import time
from pathlib import Path

import httpx
from PIL import Image

import config


CATEGORY_ALIASES = {
    "sexual": "adult_content",
    "adult_content": "adult_content",
    "violence": "violence",
    "violent": "violence",
    "shocking": "violence",
    "disturbing": "violence",
    "political": "political_sensitive",
    "illegal_activity": "illegal_activity",
    "illegal activities": "illegal_activity",
    "illegal activity": "illegal_activity",
    "self_harm": "self_harm",
    "self-harm": "self_harm",
    "spam": "marketing_violation",
    "deception": "marketing_violation",
}


def _base(status: str, *, latency_ms: int = 0, error_code: str | None = None) -> dict:
    return {
        "provider": "perspective_vision",
        "model": config.PERSPECTIVE_VISION_MODEL,
        "status": status,
        "latency_ms": latency_ms,
        "error_code": error_code,
        "categories": [],
        "privacy": {
            "external_upload": bool(config.PERSPECTIVE_VISION_ENDPOINT),
            "retained_by_platform": False,
        },
    }


def not_run(reason: str) -> dict:
    return _base("not_run", error_code=reason)


def _api_key() -> str:
    if config.PERSPECTIVE_VISION_API_KEY:
        return config.PERSPECTIVE_VISION_API_KEY
    if not config.PERSPECTIVE_VISION_API_KEY_FILE:
        return ""
    try:
        return Path(config.PERSPECTIVE_VISION_API_KEY_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _normalize_status(payload: dict) -> str:
    raw = str(payload.get("status") or payload.get("verdict") or "").strip().lower()
    if raw in {"unsafe", "detected", "risk", "risky"}:
        return "detected"
    if raw in {"safe", "not_detected", "clean"}:
        return "not_detected"
    return "inconclusive"


def _normalize_categories(payload: dict) -> list[str]:
    raw_categories = payload.get("categories")
    if not isinstance(raw_categories, list):
        raw_category = payload.get("category")
        raw_categories = [raw_category] if raw_category else []
    normalized: list[str] = []
    for item in raw_categories:
        raw_code = item.get("code") if isinstance(item, dict) else item
        code = CATEGORY_ALIASES.get(str(raw_code or "").strip().lower())
        if code and code not in normalized:
            normalized.append(code)
    return normalized


def _prepare_upload(image_path: Path) -> bytes:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        if max(image.size) > 1280:
            image.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue()


def analyze(image_path: str) -> dict:
    if not config.PERSPECTIVE_VISION_ENABLED:
        return _base("not_configured", error_code="disabled")
    if not config.PERSPECTIVE_VISION_ENDPOINT:
        return _base("not_configured", error_code="endpoint_missing")
    key = _api_key()
    if not key:
        return _base("not_configured", error_code="api_key_missing")

    started = time.perf_counter()
    image = Path(image_path)
    content_hash = hashlib.sha256(image.read_bytes()).hexdigest()
    try:
        upload_bytes = _prepare_upload(image)
        request_hash = hashlib.sha256(upload_bytes).hexdigest()
        with httpx.Client(timeout=config.PERSPECTIVE_VISION_TIMEOUT_SECONDS) as client:
            response = client.post(
                config.PERSPECTIVE_VISION_ENDPOINT,
                files={"file": (f"{image.stem}.jpg", upload_bytes, "image/jpeg")},
                headers={"X-API-Key": key, "X-Content-SHA256": request_hash},
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("provider response must be an object")
        status = _normalize_status(payload)
        result = _base(status, latency_ms=round((time.perf_counter() - started) * 1000))
        result.update({
            "categories": _normalize_categories(payload),
            "provider_category": payload.get("category"),
            "response_sha256": payload.get("response_sha256"),
            "model_revision": payload.get("model_revision"),
            "base_revision": payload.get("base_revision"),
            "content_hash": content_hash,
            "request_hash": request_hash,
            "request_bytes": len(upload_bytes),
        })
        if status == "inconclusive":
            result["error_code"] = str(payload.get("error_code") or "inconclusive_output")[:80]
        return result
    except httpx.TimeoutException:
        return _base(
            "inconclusive",
            latency_ms=round((time.perf_counter() - started) * 1000),
            error_code="timeout",
        )
    except Exception as exc:
        return _base(
            "inconclusive",
            latency_ms=round((time.perf_counter() - started) * 1000),
            error_code=type(exc).__name__,
        )
