"""Small Shamir secret-sharing implementation over GF(256)."""
from __future__ import annotations

import base64
import json
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import secrets


class SecretSharingError(ValueError):
    pass


def protect(payload: dict[str, str], *, threshold: int, share_count: int) -> dict[str, object]:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    key = os.urandom(32)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, raw, b"aigc-safety-audit-v3")
    return {
        "ciphertext": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
        "shares": split(key, threshold=threshold, share_count=share_count),
    }


def recover(ciphertext: str, nonce: str, shares: list[str]) -> dict[str, str]:
    try:
        encoded = base64.urlsafe_b64decode(ciphertext + "=" * (-len(ciphertext) % 4))
        raw_nonce = base64.urlsafe_b64decode(nonce + "=" * (-len(nonce) % 4))
    except (ValueError, TypeError) as exc:
        raise SecretSharingError("ciphertext_invalid") from exc
    key = combine(shares)
    try:
        raw = AESGCM(key).decrypt(raw_nonce, encoded, b"aigc-safety-audit-v3")
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SecretSharingError("ciphertext_invalid") from exc


def _mul(a: int, b: int) -> int:
    result = 0
    while b:
        if b & 1:
            result ^= a
        a = ((a << 1) ^ 0x11B) if a & 0x80 else a << 1
        b >>= 1
    return result & 0xFF


def _pow(a: int, power: int) -> int:
    result = 1
    while power:
        if power & 1:
            result = _mul(result, a)
        a = _mul(a, a)
        power >>= 1
    return result


def _inv(value: int) -> int:
    if value == 0:
        raise SecretSharingError("share_invalid")
    return _pow(value, 254)


def split(secret: bytes, *, threshold: int, share_count: int) -> list[str]:
    if not isinstance(secret, bytes) or not secret:
        raise SecretSharingError("secret_invalid")
    if threshold < 2 or share_count < threshold or share_count > 255:
        raise SecretSharingError("share_parameters_invalid")
    coefficients = [
        [byte] + [secrets.randbelow(256) for _ in range(threshold - 1)]
        for byte in secret
    ]
    shares = []
    for x in range(1, share_count + 1):
        values = bytearray()
        for polynomial in coefficients:
            value = 0
            for coefficient in reversed(polynomial):
                value = _mul(value, x) ^ coefficient
            values.append(value)
        raw = bytes([1, threshold, share_count, x]) + bytes(values)
        shares.append(base64.urlsafe_b64encode(raw).decode("ascii").rstrip("="))
    return shares


def combine(shares: list[str]) -> bytes:
    if not shares:
        raise SecretSharingError("threshold_not_met")
    decoded = []
    try:
        for share in shares:
            padded = share + "=" * (-len(share) % 4)
            raw = base64.urlsafe_b64decode(padded)
            if len(raw) < 5 or raw[0] != 1:
                raise SecretSharingError("share_invalid")
            decoded.append(raw)
    except (ValueError, TypeError) as exc:
        raise SecretSharingError("share_invalid") from exc
    threshold = decoded[0][1]
    count = decoded[0][2]
    if len(decoded) < threshold:
        raise SecretSharingError("threshold_not_met")
    if any(item[1] != threshold or item[2] != count or len(item) != len(decoded[0]) for item in decoded):
        raise SecretSharingError("share_invalid")
    indexes = [item[3] for item in decoded]
    if len(indexes) != len(set(indexes)):
        raise SecretSharingError("duplicate_share")
    result = bytearray(len(decoded[0]) - 4)
    for position in range(len(result)):
        value = 0
        for i, left in enumerate(decoded):
            basis = 1
            for j, right in enumerate(decoded):
                if i != j:
                    basis = _mul(basis, right[3] ^ left[3])
            basis = _inv(basis)
            numerator = 1
            for j, right in enumerate(decoded):
                if i != j:
                    numerator = _mul(numerator, right[3])
            value ^= _mul(left[4 + position], _mul(numerator, basis))
        result[position] = value
    return bytes(result)
