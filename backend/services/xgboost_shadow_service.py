"""Fail-open shadow evaluation for the trusted local XGBoost delivery package."""

from __future__ import annotations

import hashlib
import hmac
import importlib
import sys
import threading
import time
from pathlib import Path
from typing import Any

import config

ENGINE_NAME = "local_xgboost_hybrid_20260701"
_SAFE_ERROR_CODES = {
    "module_path_unavailable",
    "model_path_unavailable",
    "model_digest_required",
    "model_digest_mismatch",
    "invalid_model_decision",
}
_LOAD_LOCK = threading.Lock()
_PREDICT_LOCK = threading.Lock()
_AUDITOR: Any | None = None
_LOAD_ERROR: str | None = None
_WARMUP_STARTED = threading.Event()


def _result(status: str, **values: Any) -> dict[str, Any]:
    return {
        "status": status,
        "engine": ENGINE_NAME,
        "decision": None,
        "confidence": None,
        "alert": None,
        "agreement": None,
        "latency_ms": None,
        "risk_type": None,
        "route": None,
        "model_sha256": None,
        **values,
    }


def _safe_error_code(exc: Exception) -> str:
    value = str(exc).strip().lower()
    return value if value in _SAFE_ERROR_CODES else "shadow_evaluation_failed"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _create_auditor() -> Any:
    module_root = Path(config.GUARDRAIL_XGBOOST_SHADOW_MODULE_PATH).expanduser().resolve()
    model_path = Path(config.GUARDRAIL_XGBOOST_SHADOW_MODEL_PATH).expanduser().resolve()
    expected_digest = config.GUARDRAIL_XGBOOST_SHADOW_SHA256.strip().lower()
    if not module_root.is_dir():
        raise RuntimeError("module_path_unavailable")
    if not model_path.is_file():
        raise RuntimeError("model_path_unavailable")
    if len(expected_digest) != 64:
        raise RuntimeError("model_digest_required")
    actual_digest = _sha256(model_path)
    if not hmac.compare_digest(actual_digest, expected_digest):
        raise RuntimeError("model_digest_mismatch")

    module_root_value = str(module_root)
    if module_root_value not in sys.path:
        sys.path.insert(0, module_root_value)
    module = importlib.import_module("security_audit_system.audit_system")
    return module.SecurityAuditSystem(model_path=model_path, include_votes=True)


def _get_auditor() -> Any:
    global _AUDITOR, _LOAD_ERROR
    if _AUDITOR is not None:
        return _AUDITOR
    if _LOAD_ERROR:
        raise RuntimeError(_LOAD_ERROR)
    with _LOAD_LOCK:
        if _AUDITOR is not None:
            return _AUDITOR
        if _LOAD_ERROR:
            raise RuntimeError(_LOAD_ERROR)
        try:
            _AUDITOR = _create_auditor()
        except Exception as exc:
            _LOAD_ERROR = _safe_error_code(exc)
            raise RuntimeError(_LOAD_ERROR) from exc
        return _AUDITOR


def start_warmup() -> None:
    """Load the trusted model in a daemon thread before the first request."""
    if not config.GUARDRAIL_ENABLE_XGBOOST_SHADOW or _WARMUP_STARTED.is_set():
        return
    _WARMUP_STARTED.set()

    def load() -> None:
        try:
            _get_auditor()
        except RuntimeError:
            pass

    threading.Thread(target=load, name="xgboost-shadow-warmup", daemon=True).start()


def evaluate(text: str, primary_verdict: str) -> dict[str, Any]:
    """Return a metadata-only comparison; model failures never affect the main result."""
    if not config.GUARDRAIL_ENABLE_XGBOOST_SHADOW:
        return _result("disabled")
    if not text.strip():
        return _result("skipped")
    if _WARMUP_STARTED.is_set() and _AUDITOR is None and not _LOAD_ERROR:
        return _result("warming")

    started = time.perf_counter()
    try:
        auditor = _get_auditor()
        with _PREDICT_LOCK:
            output = auditor.audit_dict(text[:12_000])
        decision = str(output.get("decision", "")).lower()
        if decision not in {"pass", "fail"}:
            raise RuntimeError("invalid_model_decision")
        primary_binary = {"safe": "pass", "unsafe": "fail"}.get(primary_verdict)
        return _result(
            "ok",
            decision=decision,
            confidence=round(float(output.get("confidence", 0.0)), 4),
            alert=bool(output.get("alert", False)),
            agreement=(decision == primary_binary) if primary_binary else None,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            risk_type=str(output.get("risk_type", "unknown"))[:64],
            route=str(output.get("route", "local"))[:32],
            model_sha256=config.GUARDRAIL_XGBOOST_SHADOW_SHA256,
        )
    except Exception as exc:
        return _result(
            "unavailable",
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            error_code=_safe_error_code(exc),
        )


def reset_for_tests() -> None:
    global _AUDITOR, _LOAD_ERROR
    with _LOAD_LOCK:
        _AUDITOR = None
        _LOAD_ERROR = None
        _WARMUP_STARTED.clear()
