"""Local, evidence-first AI provenance inspection.

This module verifies C2PA Content Credentials and the platform's namespaced
marker. It never treats provenance alone as proof that media is AI-generated.
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
    # This legacy marker is unsigned metadata.  It may be useful as a routing
    # hint, but it cannot establish provenance because anyone can write it.
    return "inconclusive", safe, "declared_local_marker_unsigned"


def _c2pa_evidence(path: Path) -> dict[str, Any]:
    """Read embedded credentials locally and return a privacy-safe summary."""
    import c2pa

    reader = None
    try:
        reader = c2pa.Reader.try_create(str(path))
        if reader is None:
            return {"status": "not_found", "supported": True, "manifest_count": 0}
        document = json.loads(reader.json() or "{}")
        manifests = document.get("manifests", {}) if isinstance(document, dict) else {}
        active_label = document.get("active_manifest") if isinstance(document, dict) else None
        active = manifests.get(active_label, {}) if isinstance(manifests, dict) and active_label else {}
        assertions = active.get("assertions", []) if isinstance(active, dict) else []
        labels = [
            str(item.get("label"))[:120]
            for item in assertions
            if isinstance(item, dict) and item.get("label")
        ] if isinstance(assertions, list) else []
        validation_state = str(reader.get_validation_state() or "").lower()
        is_valid = bool(reader.is_valid)
        validation_failed = any(
            token in validation_state for token in ("invalid", "error", "untrusted")
        )
        # Some SDK/container combinations can remain structurally readable
        # (is_valid=True) while the asset/claim binding is invalid.  A reported
        # validation failure must take precedence over container readability.
        if validation_failed:
            status = "invalid_or_tampered"
        elif is_valid:
            status = "valid"
        else:
            status = "inconclusive"
        return {
            "status": status,
            "supported": True,
            "manifest_count": len(manifests) if isinstance(manifests, dict) else 0,
            "active_manifest": str(active_label)[:160] if active_label else None,
            "claim_generator": str(active.get("claim_generator"))[:160] if isinstance(active, dict) and active.get("claim_generator") else None,
            "assertion_labels": labels[:32],
            "validation_state": validation_state[:80] or None,
            "trust_verified": is_valid and not validation_failed,
            "remote_manifest_fetch": False,
            "note": "Content Credentials 提供来源与编辑历史，不单独证明内容一定由 AI 生成",
        }
    except Exception:
        return {"status": "inconclusive", "supported": True, "error": "manifest_parse_failed"}
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:
                pass


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

    content_credentials = _c2pa_evidence(file_path)
    credentials_state = content_credentials["status"]
    if "invalid_or_tampered" in {marker_state, credentials_state}:
        state = "invalid_or_tampered"
    elif credentials_state == "valid":
        state = "confirmed_source"
    elif "inconclusive" in {marker_state, credentials_state}:
        state = "inconclusive"
    else:
        state = "not_found"
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
            "local_marker": {
                "status": marker_state,
                "error": marker_error,
                "trust_verified": False,
                "note": "未签名本地标记只作为声明线索，不构成来源确认",
            },
            "content_credentials": content_credentials,
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
            "未签名本地 marker 不构成来源确认，也不代表 Google SynthID",
            "有效 C2PA 只证明可验证来源链，不单独证明内容一定由 AI 生成",
        ],
    }
