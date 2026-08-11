"""Signed platform-owned invisible image watermark.

This is a local DCT-domain watermark for content issued by this platform.  It
is intentionally reported as a platform signal and must not be presented as
Google SynthID or another vendor's watermark.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

MAGIC = b"ASWM"
VERSION = 1
SIGNATURE_BYTES = 16
BLOCK_SIZE = 8
COEFFICIENT_A = (3, 2)
COEFFICIENT_B = (2, 3)
EMBED_STRENGTH = 36.0
MAX_PAYLOAD_BYTES = 320
ALLOWED_FIELDS = {
    "content_id",
    "content_type",
    "issued_at",
    "tenant_id",
    "model",
    "provider",
}


class InvisibleWatermarkError(ValueError):
    pass


def _configured_secret(secret: str | None) -> str:
    if secret:
        return secret
    import config

    value = getattr(config, "INVISIBLE_WATERMARK_SIGNING_SECRET", "")
    if not value:
        raise InvisibleWatermarkError("watermark_signing_secret_not_configured")
    return value


def _validate_payload(payload: dict[str, Any]) -> dict[str, str]:
    if not isinstance(payload, dict) or set(payload) - ALLOWED_FIELDS:
        raise InvisibleWatermarkError("payload_fields_not_allowed")
    if not {"content_id", "content_type"} <= set(payload):
        raise InvisibleWatermarkError("payload_fields_missing")
    if payload.get("content_type") not in {"ai_generated", "algorithmically_enhanced"}:
        raise InvisibleWatermarkError("content_type_invalid")
    safe = {key: str(value)[:160] for key, value in payload.items()}
    safe.setdefault("issued_at", datetime.now(timezone.utc).isoformat())
    raw = _payload_bytes(safe)
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise InvisibleWatermarkError("payload_too_large")
    return safe


def _payload_bytes(payload: dict[str, str]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _to_bits(data: bytes) -> list[int]:
    return [(byte >> shift) & 1 for byte in data for shift in range(7, -1, -1)]


def _from_bits(bits: list[int]) -> bytes:
    if len(bits) % 8:
        raise InvisibleWatermarkError("watermark_bitstream_invalid")
    return bytes(
        sum(bits[offset + index] << (7 - index) for index in range(8))
        for offset in range(0, len(bits), 8)
    )


def _block_origins(width: int, height: int):
    for y in range(0, height - BLOCK_SIZE + 1, BLOCK_SIZE):
        for x in range(0, width - BLOCK_SIZE + 1, BLOCK_SIZE):
            yield x, y


def _packet(payload: dict[str, str], secret: str) -> bytes:
    raw = _payload_bytes(payload)
    header = MAGIC + bytes([VERSION]) + len(raw).to_bytes(2, "big")
    signature = hmac.new(secret.encode("utf-8"), header + raw, hashlib.sha256).digest()[:SIGNATURE_BYTES]
    return header + raw + signature


def _read_bits(luma: np.ndarray, count: int) -> list[int]:
    bits: list[int] = []
    for x, y in _block_origins(luma.shape[1], luma.shape[0]):
        block = luma[y : y + BLOCK_SIZE, x : x + BLOCK_SIZE].astype(np.float32)
        coefficients = cv2.dct(block)
        bits.append(int(coefficients[COEFFICIENT_A] >= coefficients[COEFFICIENT_B]))
        if len(bits) == count:
            return bits
    raise InvisibleWatermarkError("image_capacity_insufficient")


def embed(
    original_path: str | Path,
    output_path: str | Path,
    payload: dict[str, Any],
    *,
    secret: str | None = None,
) -> dict[str, Any]:
    signing_secret = _configured_secret(secret)
    safe_payload = _validate_payload(payload)
    packet = _packet(safe_payload, signing_secret)
    bits = _to_bits(packet)

    source = Path(original_path)
    output = Path(output_path)
    with Image.open(source) as image:
        alpha = image.getchannel("A") if image.mode == "RGBA" else None
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    ycrcb = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)
    luma = ycrcb[:, :, 0].astype(np.float32)
    origins = list(_block_origins(luma.shape[1], luma.shape[0]))
    if len(origins) < len(bits):
        raise InvisibleWatermarkError("image_capacity_insufficient")

    for bit, (x, y) in zip(bits, origins):
        block = luma[y : y + BLOCK_SIZE, x : x + BLOCK_SIZE]
        coefficients = cv2.dct(block)
        a = float(coefficients[COEFFICIENT_A])
        b = float(coefficients[COEFFICIENT_B])
        signed_difference = (a - b) if bit else (b - a)
        if signed_difference < EMBED_STRENGTH:
            adjustment = (EMBED_STRENGTH - signed_difference) / 2 + 1
            if bit:
                coefficients[COEFFICIENT_A] += adjustment
                coefficients[COEFFICIENT_B] -= adjustment
            else:
                coefficients[COEFFICIENT_A] -= adjustment
                coefficients[COEFFICIENT_B] += adjustment
        luma[y : y + BLOCK_SIZE, x : x + BLOCK_SIZE] = cv2.idct(coefficients)

    ycrcb[:, :, 0] = np.clip(np.rint(luma), 0, 255).astype(np.uint8)
    result_rgb = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2RGB)
    result = Image.fromarray(result_rgb, mode="RGB")
    if alpha is not None:
        result.putalpha(alpha)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output, format="PNG")
    return {
        "watermarked_path": str(output),
        "payload": safe_payload,
        "watermark_type": "frequency-domain-dct",
        "provider": "aigc-safety",
        "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


def check(path: str | Path, *, secret: str | None = None) -> dict[str, Any]:
    try:
        signing_secret = _configured_secret(secret)
    except InvisibleWatermarkError:
        return {
            "status": "not_configured",
            "provider": "aigc-safety",
            "watermark_type": "frequency-domain-dct",
            "payload": None,
            "signature_valid": False,
            "tamper_suspected": False,
            "note": "平台隐形水印核验密钥未配置",
        }

    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    luma = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)[:, :, 0]
    header_size = len(MAGIC) + 3
    try:
        header = _from_bits(_read_bits(luma, header_size * 8))
    except InvisibleWatermarkError:
        return _no_signal()
    if header[:4] != MAGIC or header[4] != VERSION:
        return _no_signal()

    payload_length = int.from_bytes(header[5:7], "big")
    if payload_length <= 0 or payload_length > MAX_PAYLOAD_BYTES:
        return _invalid("检测到平台水印头，但载荷长度无效")
    packet_size = header_size + payload_length + SIGNATURE_BYTES
    try:
        packet = _from_bits(_read_bits(luma, packet_size * 8))
    except InvisibleWatermarkError:
        return _invalid("检测到平台水印头，但图片容量或数据不完整")
    raw_payload = packet[header_size : header_size + payload_length]
    signature = packet[-SIGNATURE_BYTES:]
    expected = hmac.new(
        signing_secret.encode("utf-8"), packet[:header_size] + raw_payload, hashlib.sha256
    ).digest()[:SIGNATURE_BYTES]
    if not hmac.compare_digest(signature, expected):
        return _invalid("检测到平台水印信号，但签名校验失败")
    try:
        payload = _validate_payload(json.loads(raw_payload.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError, InvisibleWatermarkError):
        return _invalid("平台水印载荷无法解析")
    return {
        "status": "confirmed",
        "provider": "aigc-safety",
        "watermark_type": "frequency-domain-dct",
        "payload": payload,
        "signature_valid": True,
        "tamper_suspected": False,
        "note": "已验证本平台签名隐形水印；该结果只证明由本平台标记，不代表第三方厂商来源",
    }


def _no_signal() -> dict[str, Any]:
    return {
        "status": "no_signal",
        "provider": "aigc-safety",
        "watermark_type": "frequency-domain-dct",
        "payload": None,
        "signature_valid": False,
        "tamper_suspected": False,
        "note": "未检出本平台隐形水印；不代表非 AI 生成",
    }


def _invalid(note: str) -> dict[str, Any]:
    return {
        "status": "invalid",
        "provider": "aigc-safety",
        "watermark_type": "frequency-domain-dct",
        "payload": None,
        "signature_valid": False,
        "tamper_suspected": True,
        "note": note,
    }
