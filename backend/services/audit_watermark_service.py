"""Reversible CRT audit watermarking for controlled evidence copies.

The original uploaded evidence is never modified.  The returned PNG and its
sidecar are demonstration/audit artifacts and must be retained together.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image
from services.secret_sharing_service import SecretSharingError, protect, recover

M_PIXEL_REM = 127
MAX_PAYLOAD_BYTES = 2048
ALLOWED_FIELDS = {
    "event_id", "sample_id", "content_hash_prefix", "generated_at", "platform_version",
    "task_id", "report_id", "operator_id", "reviewed_at", "custom_note",
    "deepfake", "provenance", "content_safety", "rag", "models", "policy_versions",
    "human_review",
}


class AuditWatermarkError(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) - ALLOWED_FIELDS:
        raise AuditWatermarkError("payload_fields_not_allowed")
    if not {"event_id", "sample_id"} <= set(payload):
        raise AuditWatermarkError("payload_fields_missing")
    safe: dict[str, Any] = {}
    for key in ALLOWED_FIELDS:
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, dict):
            safe[key] = json.loads(json.dumps(value, ensure_ascii=False))
        elif isinstance(value, list):
            safe[key] = [str(item)[:120] for item in value[:20]]
        else:
            safe[key] = str(value)[:500 if key == "custom_note" else 160]
    serialized = json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
    if any(token in serialized.lower() for token in ("password", "api_key", "secret_key", "access_token")):
        raise AuditWatermarkError("payload_contains_secret_like_text")
    encoded = serialized.encode("utf-8")
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
        if image.mode in {"RGB", "RGBA"}:
            sealed = protect(safe_payload, threshold=2, share_count=3)
            marker_payload = {
                "event_id": hashlib.sha256(sealed["ciphertext"].encode("ascii")).hexdigest()[:32],
                "sample_id": "sealed-audit-payload",
                "platform_version": "secret-sharing-2-of-3",
            }
            result = _embed_rgb(source, output, marker_payload)
            shares = sealed.pop("shares")
            result["sidecar"]["schema"] = "aigc-safety-reversible-audit/v3"
            result["sidecar"]["sealed_payload"] = sealed
            result["sidecar"]["secret_sharing"] = {"threshold": 2, "share_count": 3}
            result["sidecar"]["payload"] = None
            result["shares"] = shares
            return result
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


def _embed_rgb(source: Path, output: Path, safe_payload: dict[str, str]) -> dict[str, Any]:
    """Embed in blue-channel LSBs while preserving the image's color mode."""
    text = json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    bits = _bits(text)
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        pixels = list(rgba.get_flattened_data())
        original_hash = hashlib.sha256(bytes(value for pixel in pixels for value in pixel)).hexdigest()
        if len(pixels) < len(bits):
            raise AuditWatermarkError("image_capacity_insufficient")
        original_lsbs = [pixel[2] & 1 for pixel in pixels[: len(bits)]]
        marked = []
        for index, pixel in enumerate(pixels):
            if index < len(bits):
                blue = (pixel[2] & 0xFE) | bits[index]
                marked.append((pixel[0], pixel[1], blue, pixel[3]))
            else:
                marked.append(pixel)
        result = Image.new("RGBA", rgba.size)
        result.putdata(marked)
        if image.mode == "RGB":
            result = result.convert("RGB")
        output.parent.mkdir(parents=True, exist_ok=True)
        result.save(output, format="PNG")
    artifact_hash = _sha256(output)
    sidecar = {
        "schema": "aigc-safety-reversible-audit/v2",
        "algorithm": "blue-channel-lsb-reversible/v1",
        "width": result.width,
        "height": result.height,
        "mode": result.mode,
        "payload": safe_payload,
        "payload_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "original_sha256": original_hash,
        "artifact_sha256": artifact_hash,
        "embedded_bit_count": len(bits),
        "original_lsbs": base64.b64encode(bytes(original_lsbs)).decode("ascii"),
    }
    return {"watermarked_path": str(output), "sidecar": sidecar, "payload": safe_payload}


def decode(watermarked_path: str | Path, sidecar: dict[str, Any], *, shares: list[str] | None = None) -> dict[str, Any]:
    path = Path(watermarked_path)
    if sidecar.get("schema") == "aigc-safety-reversible-audit/v3":
        result = _decode_rgb(path, sidecar)
        try:
            sealed = sidecar.get("sealed_payload") or {}
            payload = recover(sealed["ciphertext"], sealed["nonce"], shares or [])
        except (KeyError, SecretSharingError) as exc:
            message = str(exc)
            raise AuditWatermarkError(message if message == "threshold_not_met" else "secret_sharing_recovery_failed") from exc
        result["payload"] = payload
        result["secret_sharing"] = {
            "threshold": sidecar.get("secret_sharing", {}).get("threshold", 2),
            "share_count": sidecar.get("secret_sharing", {}).get("share_count", 3),
            "recovered": True,
        }
        return result
    if sidecar.get("schema") == "aigc-safety-reversible-audit/v2":
        return _decode_rgb(path, sidecar)
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


def _decode_rgb(path: Path, sidecar: dict[str, Any]) -> dict[str, Any]:
    with Image.open(path) as image:
        if image.mode not in {"RGB", "RGBA"}:
            raise AuditWatermarkError("audit_image_mode_invalid")
        rgba = image.convert("RGBA")
        pixels = list(rgba.get_flattened_data())
        artifact_hash = _sha256(path)
        count = int(sidecar.get("embedded_bit_count", 0))
        if count <= 0 or count > len(pixels):
            raise AuditWatermarkError("sidecar_dimensions_mismatch")
        bits = [pixel[2] & 1 for pixel in pixels[:count]]
        original_lsbs = base64.b64decode(str(sidecar.get("original_lsbs", "")), validate=True)
        if len(original_lsbs) != count:
            raise AuditWatermarkError("sidecar_dimensions_mismatch")
        try:
            payload = _validate_payload(json.loads(_decode(bits)))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, AuditWatermarkError) as exc:
            raise AuditWatermarkError("watermark_invalid_or_tampered") from exc
        restored = []
        for index, pixel in enumerate(pixels):
            if index < count:
                blue = (pixel[2] & 0xFE) | original_lsbs[index]
                restored.append((pixel[0], pixel[1], blue, pixel[3]))
            else:
                restored.append(pixel)
        recovered = Image.new("RGBA", rgba.size)
        recovered.putdata(restored)
        recovered_hash = hashlib.sha256(bytes(value for pixel in restored for value in pixel)).hexdigest()
    payload_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    artifact_matches = artifact_hash == sidecar.get("artifact_sha256")
    recovered_matches = recovered_hash == sidecar.get("original_sha256")
    return {
        "payload": payload,
        "payload_integrity": hashlib.sha256(payload_text.encode("utf-8")).hexdigest() == sidecar.get("payload_sha256"),
        "recovered_sha256": recovered_hash,
        "original_sha256": sidecar.get("original_sha256"),
        "recovered_matches_original": recovered_matches,
        "artifact_matches_sidecar": artifact_matches,
        "tamper_suspected": not artifact_matches or not recovered_matches,
    }


def decode_archive(archive_path: str | Path) -> dict[str, Any]:
    """Validate an exported audit ZIP without trusting its filenames or paths."""
    package = Path(archive_path)
    if not zipfile.is_zipfile(package):
        raise AuditWatermarkError("audit_archive_invalid")
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        required = {"audit-copy.png", "audit-sidecar.json"}
        if not required <= names:
            raise AuditWatermarkError("audit_archive_files_missing")
        if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
            raise AuditWatermarkError("audit_archive_path_invalid")
        if archive.getinfo("audit-sidecar.json").file_size > 2 * 1024 * 1024:
            raise AuditWatermarkError("sidecar_too_large")
        try:
            sidecar = json.loads(archive.read("audit-sidecar.json"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuditWatermarkError("sidecar_json_invalid") from exc
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "audit-copy.png"
            image_path.write_bytes(archive.read("audit-copy.png"))
            share_names = sorted(name for name in names if name.startswith("key-share-") and name.endswith(".txt"))
            shares = [archive.read(name).decode("ascii").strip() for name in share_names]
            return decode(image_path, sidecar, shares=shares)
