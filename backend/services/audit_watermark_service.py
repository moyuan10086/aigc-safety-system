"""Reversible CRT audit watermarking for controlled evidence copies.

The original uploaded evidence is never modified.  The returned PNG and its
sidecar are demonstration/audit artifacts and must be retained together.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

M_PIXEL_REM = 127
MAX_PAYLOAD_BYTES = 2048
ALLOWED_FIELDS = {"event_id", "sample_id", "content_hash_prefix", "generated_at", "platform_version"}


class AuditWatermarkError(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_payload(payload: dict[str, Any]) -> dict[str, str]:
    if not isinstance(payload, dict) or set(payload) - ALLOWED_FIELDS:
        raise AuditWatermarkError("payload_fields_not_allowed")
    if not {"event_id", "sample_id"} <= set(payload):
        raise AuditWatermarkError("payload_fields_missing")
    safe = {key: str(payload.get(key, ""))[:160] for key in ALLOWED_FIELDS if key in payload}
    if any("password" in value.lower() or "api_key" in value.lower() for value in safe.values()):
        raise AuditWatermarkError("payload_contains_secret_like_text")
    encoded = json.dumps(safe, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise AuditWatermarkError("payload_too_large")
    return safe


def _bits(text: str) -> list[int]:
    raw = text.encode("utf-8") + b"\x00"
    return [(byte >> shift) & 1 for byte in raw for shift in range(7, -1, -1)]


def _decode(bits: list[int]) -> str:
    data = bytearray()
    for offset in range(0, len(bits) - 7, 8):
        value = sum(bits[offset + i] << (7 - i) for i in range(8))
        if value == 0:
            break
        data.append(value)
    return bytes(data).decode("utf-8")


def embed(original_path: str | Path, output_path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    source = Path(original_path)
    output = Path(output_path)
    safe_payload = _validate_payload(payload)
    safe_payload.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    text = json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    bits = _bits(text)
    with Image.open(source) as image:
        image = image.convert("L")
        original_pixel_hash = hashlib.sha256(image.tobytes()).hexdigest()
        if image.width * image.height < len(bits):
            raise AuditWatermarkError("image_capacity_insufficient")
        pixels = list(image.get_flattened_data())
        quotients: list[int] = []
        embedded: list[int] = []
        for index, pixel in enumerate(pixels):
            quotients.append(pixel // M_PIXEL_REM)
            remainder = pixel % M_PIXEL_REM
            bit = bits[index] if index < len(bits) else 0
            embedded.append(remainder if remainder % 2 == bit else remainder + M_PIXEL_REM)
        result = Image.new("L", image.size)
        result.putdata(embedded)
        output.parent.mkdir(parents=True, exist_ok=True)
        result.save(output, format="PNG")
    sidecar = {
        "schema": "aigc-safety-crt-audit/v1",
        "width": image.width,
        "height": image.height,
        "payload": safe_payload,
        "payload_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "original_sha256": original_pixel_hash,
        "quotients": quotients,
    }
    return {"watermarked_path": str(output), "sidecar": sidecar, "payload": safe_payload}


def decode(watermarked_path: str | Path, sidecar: dict[str, Any]) -> dict[str, Any]:
    path = Path(watermarked_path)
    if sidecar.get("schema") != "aigc-safety-crt-audit/v1":
        raise AuditWatermarkError("sidecar_schema_invalid")
    quotients = sidecar.get("quotients")
    with Image.open(path) as image:
        image = image.convert("L")
        pixels = list(image.get_flattened_data())
        if len(quotients or []) != len(pixels):
            raise AuditWatermarkError("sidecar_dimensions_mismatch")
        bits = [pixel % 2 for pixel in pixels]
        try:
            text = _decode(bits)
            payload = _validate_payload(json.loads(text))
        except (UnicodeDecodeError, json.JSONDecodeError, AuditWatermarkError) as exc:
            raise AuditWatermarkError("watermark_invalid_or_tampered") from exc
        recovered = [int(q) * M_PIXEL_REM + (pixel % M_PIXEL_REM) for q, pixel in zip(quotients, pixels)]
        restored = Image.new("L", image.size)
        restored.putdata(recovered)
        recovered_hash = hashlib.sha256(restored.tobytes()).hexdigest()
    return {
        "payload": payload,
        "payload_integrity": hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest() == sidecar.get("payload_sha256"),
        "recovered_sha256": recovered_hash,
        "original_sha256": sidecar.get("original_sha256"),
        "recovered_matches_original": recovered_hash == sidecar.get("original_sha256"),
        "tamper_suspected": False,
    }
