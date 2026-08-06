"""Normalized third-party watermark provider contracts."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

PROVIDERS = {
    "aivo": {"watermark_type": "unknown", "verification_url": "https://www.aivo.my/"},
    "humantext": {"watermark_type": "synthid", "verification_url": "https://humantext.pro/zh/synthid-detector"},
}


class WatermarkProviderError(ValueError):
    pass


def check(path: str | Path, *, provider: str, consent: bool) -> dict[str, Any]:
    if provider not in PROVIDERS:
        raise WatermarkProviderError("provider_not_supported")
    if not consent:
        raise WatermarkProviderError("external_upload_consent_required")
    started = time.perf_counter()
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    definition = PROVIDERS[provider]
    # Neither provider currently exposes a configured, authorized server API.
    # Return an explicit capability boundary instead of scraping its website.
    return {
        "provider": provider,
        "status": "not_configured",
        "watermark_type": definition["watermark_type"],
        "confidence": None,
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "evidence": {"request_hash": digest, "verification_url": definition["verification_url"]},
        "privacy": {"external_upload": False, "retained_by_platform": False},
        "note": "未配置公开授权的服务端 API，可使用供应商页面进行独立复核",
    }
