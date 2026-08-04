"""Local, evidence-first AI provenance inspection.

This module deliberately does not claim SynthID/C2PA support.  It only verifies
the platform's namespaced marker and reports metadata observations as context.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

MARKER_KEY = "aigc_safety_provenance"
MAX_IMAGE_BYTES = 12 * 1024 * 1024


class ProvenanceError(ValueError):
    pass


def _marker_status(value: Any) -> tuple[str, dict[str, Any] | None, str | None]:
    if value is None:
        return "not_found", None, None
    try:
        marker = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return "invalid_or_tampered", None, "declared_local_marker_malformed"
    if not isinstance(marker, dict) or marker.get("schema") != "aigc-safety-provenance/v1":
        return "invalid_or_tampered", None, "declared_local_marker_schema_invalid"
    if marker.get("source_type") not in {"ai_generated", "ai_assisted", "human_created"}:
        return "invalid_or_tampered", None, "declared_local_marker_source_invalid"
    safe = {k: str(marker[k])[:128] for k in ("schema", "source_type", "issuer", "event_ref") if k in marker}
    return "confirmed_source", safe, None


def verify(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    try:
        size = file_path.stat().st_size
    except OSError as exc:
        raise ProvenanceError("image_unavailable") from exc
    if size <= 0 or size > MAX_IMAGE_BYTES:
        raise ProvenanceError("image_size_not_supported")
    digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
    try:
        with Image.open(file_path) as image:
            image.verify()
        with Image.open(file_path) as image:
            info = dict(image.info)
            exif = image.getexif()
            marker_state, marker, marker_error = _marker_status(info.get(MARKER_KEY))
            metadata = {
                "format": image.format,
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "has_exif": bool(exif),
                "has_icc_profile": bool(info.get("icc_profile")),
                "has_xmp": bool(info.get("xmp")),
                "has_comment": bool(info.get("comment")),
                "local_marker": marker,
            }
    except Exception as exc:
        raise ProvenanceError("image_invalid") from exc

    state = marker_state
    if state == "not_found" and (metadata["width"] < 16 or metadata["height"] < 16):
        state = "inconclusive"
    return {
        "overall_state": state,
        "state_label": {
            "confirmed_source": "已确认来源证据",
            "not_found": "未发现兼容来源证据",
            "inconclusive": "证据不足，无法判断",
            "invalid_or_tampered": "来源声明无效或疑似篡改",
        }[state],
        "content_hash": digest,
        "size_bytes": size,
        "source_evidence": {
            "local_marker": {"status": marker_state, "error": marker_error},
            "content_credentials": {
                "status": "not_found",
                "supported": False,
                "note": "C2PA/Content Credentials parser 尚未启用",
            },
            "watermark": {"status": "not_found", "supported": False},
        },
        "content_detection": {
            "status": "not_run",
            "note": "来源验证不替代 Deepfake、MLLM 或红线审核",
        },
        "audit_evidence": {
            "hash_algorithm": "SHA-256",
            "raw_image_retained": False,
            "evidence_access": "metadata_only",
        },
        "metadata": metadata,
        "limitations": [
            "未发现来源证据不等于确认非 AI",
            "本地 marker 是兼容性证据，不代表 Google SynthID 或 C2PA 签名",
        ],
    }
