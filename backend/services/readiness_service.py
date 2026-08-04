"""Build a safe competition-demo readiness snapshot and active model probe."""

from __future__ import annotations

import copy
import hashlib
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from services import audit_log_service, auth_service, guarded_chat_service

BACKEND_DIR = Path(__file__).parents[1]
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_INDEX = PROJECT_DIR / "frontend" / "dist" / "index.html"
BUNDLED_LEXICON = BACKEND_DIR / "Sensitive-lexicon" / "Vocabulary"
DEEPFAKE_WEIGHTS = PROJECT_DIR / "deepfake-detection" / "weights" / "model.ckpt"
PASSIVE_CACHE_SECONDS = 5.0
PROBE_CACHE_SECONDS = 30.0
PROBE_MAX_ATTEMPTS = 2
PROBE_RETRY_DELAY_SECONDS = 0.5
PROBE_PROMPT = "这是比赛演示运行自检。请只回答 READY。"

_PASSIVE_LOCK = threading.Lock()
_PROBE_LOCK = threading.Lock()
_PASSIVE_CACHE: tuple[float, dict[str, Any]] | None = None
_PROBE_CACHE: tuple[float, dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _runtime_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else BACKEND_DIR / path


def _public_model_name(value: str) -> str:
    cleaned = str(value or "").strip()
    if (
        not cleaned
        or "://" in cleaned
        or "\\" in cleaned
        or cleaned.startswith("/")
        or ".." in cleaned
    ):
        return "configured-model" if cleaned else "未配置"
    return cleaned[:160]


def _check(
    check_id: str,
    label: str,
    status: str,
    required: bool,
    message: str,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "required": required,
        "message": message,
    }


def _exists(value: str, *, directory: bool = False) -> bool:
    if not value:
        return False
    path = _runtime_path(value)
    return path.is_dir() if directory else path.exists()


def _audit_chain_check() -> tuple[str, str]:
    try:
        if audit_log_service.verify_chain():
            return "pass", "SHA-256 审计链校验通过"
        return "fail", "审计链校验失败，暂停现场演示"
    except Exception:
        return "fail", "审计数据库不可读，暂停现场演示"


def _face_detector_available() -> bool:
    try:
        import cv2

        source = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        return source.is_file()
    except Exception:
        return False


def _passive_checks() -> list[dict[str, Any]]:
    audit_status, audit_message = _audit_chain_check()
    auth_ready = auth_service.configured()
    vault_ready = bool(config.AUDIT_STORE_RAW_CONTENT and config.AUDIT_CONTENT_KEY)
    frontend_ready = FRONTEND_INDEX.is_file()
    bundled_lexicon_ready = BUNDLED_LEXICON.is_dir()
    configured_lexicon_ready = _exists(config.LEXICON_PATH, directory=True)
    rag_ready = _exists(config.CHROMA_PATH, directory=True)
    chat_ready = bool(
        config.CHAT_MODEL_API_KEY
        and config.CHAT_MODEL_BASE_URL
        and config.CHAT_MODEL_NAME
    )
    mllm_ready = bool(config.MLLM_API_KEY and config.MLLM_BASE_URL and config.MLLM_MODEL)
    deepfake_ready = DEEPFAKE_WEIGHTS.is_file() or _exists(config.DEEPFAKE_MODEL_PATH)
    face_ready = _face_detector_available()

    qwen_enabled = config.GUARDRAIL_ENABLE_QWEN_CLASSIFIER
    qwen_ready = bool(
        qwen_enabled
        and config.GUARDRAIL_QWEN_API_KEY
        and config.GUARDRAIL_QWEN_BASE_URL
        and config.GUARDRAIL_QWEN_MODEL
    )
    singguard_enabled = config.GUARDRAIL_ENABLE_SINGGUARD_CLASSIFIER
    singguard_ready = bool(
        singguard_enabled
        and config.GUARDRAIL_SINGGUARD_API_KEY
        and config.GUARDRAIL_SINGGUARD_BASE_URL
        and config.GUARDRAIL_SINGGUARD_MODEL
    )

    return [
        _check("api_runtime", "主 API", "pass", True, "FastAPI 运行时可响应"),
        _check(
            "operator_auth",
            "审核员身份",
            "pass" if auth_ready else "fail",
            True,
            "审核员身份与会话签名已配置" if auth_ready else "审核员身份配置不完整",
        ),
        _check("audit_chain", "审计链", audit_status, True, audit_message),
        _check(
            "evidence_vault",
            "加密证据库",
            "pass" if vault_ready else "fail",
            True,
            "AES-GCM 原始证据保留已启用" if vault_ready else "原始证据加密配置不完整",
        ),
        _check(
            "frontend_dist",
            "前端构建",
            "pass" if frontend_ready else "fail",
            True,
            "生产静态资源已生成" if frontend_ready else "未找到生产前端构建",
        ),
        _check(
            "rules_engine",
            "红线规则引擎",
            "pass" if bundled_lexicon_ready or configured_lexicon_ready else "fail",
            True,
            "敏感词库可读取" if bundled_lexicon_ready or configured_lexicon_ready else "敏感词库不可读取",
        ),
        _check(
            "face_detector",
            "人脸质量检测",
            "pass" if face_ready else "fail",
            True,
            "OpenCV 人脸检测器可用" if face_ready else "OpenCV 人脸检测器不可用",
        ),
        _check(
            "rag_knowledge",
            "红线知识检索",
            "pass" if config.GUARDRAIL_ENABLE_RAG and rag_ready else "disabled" if not config.GUARDRAIL_ENABLE_RAG else "warn",
            False,
            "RAG 知识库已启用" if config.GUARDRAIL_ENABLE_RAG and rag_ready else "RAG 已停用" if not config.GUARDRAIL_ENABLE_RAG else "RAG 路径不可用，规则引擎继续工作",
        ),
        _check(
            "chat_model",
            "安全对话模型",
            "pass" if chat_ready else "warn",
            False,
            f"{_public_model_name(config.CHAT_MODEL_NAME)} 已配置" if chat_ready else "生成模型未配置，实时护栏仅执行输入检查",
        ),
        _check(
            "mllm_model",
            "多模态审核模型",
            "pass" if mllm_ready else "warn",
            False,
            f"{_public_model_name(config.MLLM_MODEL)} 已配置" if mllm_ready else "多模态模型未配置，图片审核使用本地能力",
        ),
        _check(
            "deepfake_model",
            "Deepfake 模型",
            "pass" if deepfake_ready else "warn",
            False,
            "Deepfake 权重可读取" if deepfake_ready else "Deepfake 权重不可用，人脸质量检测仍可工作",
        ),
        _check(
            "qwen3guard",
            "Qwen3Guard 专家",
            "pass" if qwen_ready else "fail" if qwen_enabled else "disabled",
            False,
            "Qwen3Guard 已启用并配置" if qwen_ready else "Qwen3Guard 已启用但配置不完整" if qwen_enabled else "Qwen3Guard 当前停用",
        ),
        _check(
            "singguard",
            "SingGuard-NSFA 专家",
            "pass" if singguard_ready else "fail" if singguard_enabled else "disabled",
            False,
            "SingGuard-NSFA 已启用并配置" if singguard_ready else "SingGuard-NSFA 已启用但配置不完整" if singguard_enabled else "SingGuard-NSFA 当前停用",
        ),
    ]


def _scenario(
    scenario_id: str,
    label: str,
    checks: dict[str, dict[str, Any]],
    required_ids: list[str],
    optional_ids: list[str],
    ready_message: str,
) -> dict[str, Any]:
    required_failed = any(checks[item]["status"] == "fail" for item in required_ids)
    optional_degraded = any(
        checks[item]["status"] in {"warn", "fail", "disabled"} for item in optional_ids
    )
    status = "not_ready" if required_failed else "degraded" if optional_degraded else "ready"
    return {
        "id": scenario_id,
        "label": label,
        "status": status,
        "message": (
            "必需组件异常"
            if required_failed
            else "核心链路可用，部分增强能力降级"
            if optional_degraded
            else ready_message
        ),
    }


def _build_snapshot() -> dict[str, Any]:
    checks = _passive_checks()
    by_id = {item["id"]: item for item in checks}
    required_failed = sum(item["required"] and item["status"] == "fail" for item in checks)
    optional_degraded = sum(
        not item["required"] and item["status"] in {"warn", "fail", "disabled"}
        for item in checks
    )
    status = "not_ready" if required_failed else "degraded" if optional_degraded else "ready"
    scenarios = [
        _scenario(
            "guardrail",
            "实时安全护栏",
            by_id,
            ["api_runtime", "rules_engine", "audit_chain", "evidence_vault"],
            ["chat_model", "rag_knowledge", "qwen3guard", "singguard"],
            "输入、生成与输出护栏链路就绪",
        ),
        _scenario(
            "image_review",
            "图片与人脸审核",
            by_id,
            ["api_runtime", "face_detector", "audit_chain"],
            ["mllm_model", "deepfake_model"],
            "人脸、Deepfake 与多模态审核就绪",
        ),
        _scenario(
            "audit_forensics",
            "审计与取证",
            by_id,
            ["operator_auth", "audit_chain", "evidence_vault", "frontend_dist"],
            [],
            "登录、审计链与加密证据库就绪",
        ),
    ]
    return {
        "status": status,
        "generated_at": _utc_now(),
        "cache_ttl_seconds": PASSIVE_CACHE_SECONDS,
        "summary": {
            "total": len(checks),
            "passed": sum(item["status"] == "pass" for item in checks),
            "degraded": sum(item["status"] in {"warn", "disabled"} for item in checks),
            "failed": sum(item["status"] == "fail" for item in checks),
            "required_failed": required_failed,
        },
        "checks": checks,
        "scenarios": scenarios,
        "active_probe": {
            "available": by_id["chat_model"]["status"] == "pass",
            "requires_operator": True,
            "cache_ttl_seconds": PROBE_CACHE_SECONDS,
        },
        "privacy": {
            "secrets_exposed": False,
            "paths_exposed": False,
            "raw_content_included": False,
        },
    }


def snapshot(*, refresh: bool = False) -> dict[str, Any]:
    global _PASSIVE_CACHE
    now = time.monotonic()
    if not refresh and _PASSIVE_CACHE and now - _PASSIVE_CACHE[0] < PASSIVE_CACHE_SECONDS:
        result = copy.deepcopy(_PASSIVE_CACHE[1])
        result["cached"] = True
        return result
    with _PASSIVE_LOCK:
        now = time.monotonic()
        if not refresh and _PASSIVE_CACHE and now - _PASSIVE_CACHE[0] < PASSIVE_CACHE_SECONDS:
            result = copy.deepcopy(_PASSIVE_CACHE[1])
            result["cached"] = True
            return result
        result = _build_snapshot()
        _PASSIVE_CACHE = (now, copy.deepcopy(result))
        result["cached"] = False
        return result


def _expert_summary(guard: dict[str, Any] | None) -> dict[str, str]:
    components = ((guard or {}).get("engine") or {}).get("components") or {}
    allowed = ("rules", "rag", "mllm", "qwen3guard", "singguard", "xgboost_shadow")
    return {name: str(components.get(name, "not_run"))[:32] for name in allowed}


def active_model_probe() -> tuple[dict[str, Any], dict[str, str] | None]:
    """Run one real guarded generation and return only a metadata-safe result."""
    global _PROBE_CACHE
    now = time.monotonic()
    if _PROBE_CACHE and now - _PROBE_CACHE[0] < PROBE_CACHE_SECONDS:
        result = copy.deepcopy(_PROBE_CACHE[1])
        result["cached"] = True
        return result, None
    with _PROBE_LOCK:
        now = time.monotonic()
        if _PROBE_CACHE and now - _PROBE_CACHE[0] < PROBE_CACHE_SECONDS:
            result = copy.deepcopy(_PROBE_CACHE[1])
            result["cached"] = True
            return result, None
        evidence: dict[str, str] = {}
        attempts = 0
        try:
            while attempts < PROBE_MAX_ATTEMPTS:
                attempts += 1
                evidence = {}
                try:
                    guarded = guarded_chat_service.run(
                        PROBE_PROMPT,
                        max_tokens=32,
                        evidence_capture=evidence,
                    )
                    break
                except guarded_chat_service.ModelGatewayError:
                    if attempts >= PROBE_MAX_ATTEMPTS:
                        raise
                    time.sleep(PROBE_RETRY_DELAY_SECONDS)
            generation = guarded.get("generation") or {}
            input_guard = guarded.get("input_guard") or {}
            output_guard = guarded.get("output_guard") or {}
            final_guard = guarded.get("final_guard") or {}
            model_called = bool(guarded.get("model_called"))
            verdict = str(final_guard.get("verdict") or "unknown")
            probe_status = (
                "ready"
                if model_called and verdict == "safe"
                else "degraded"
                if model_called
                else "failed"
            )
            raw_output = evidence.get("model_output", "")
            public = {
                "status": probe_status,
                "checked_at": _utc_now(),
                "cached": False,
                "model_called": model_called,
                "attempts": attempts,
                "max_attempts": PROBE_MAX_ATTEMPTS,
                "recovered_after_retry": attempts > 1,
                "model": _public_model_name(
                    str(generation.get("model") or config.CHAT_MODEL_NAME)
                ),
                "latency_ms": generation.get("latency_ms"),
                "input_verdict": str(input_guard.get("verdict") or "unknown"),
                "output_verdict": str(output_guard.get("verdict") or "not_run"),
                "final_verdict": verdict,
                "quarantined": bool(guarded.get("quarantined")),
                "output_sha256": hashlib.sha256(raw_output.encode("utf-8")).hexdigest()
                if raw_output
                else None,
                "input_experts": _expert_summary(input_guard),
                "output_experts": _expert_summary(output_guard),
                "evidence_captured": bool(raw_output),
                "privacy": {
                    "secrets_exposed": False,
                    "paths_exposed": False,
                    "raw_content_included": False,
                },
            }
            captured = {"prompt": PROBE_PROMPT, "response": raw_output}
        except guarded_chat_service.ModelNotConfiguredError:
            public = {
                "status": "not_configured",
                "checked_at": _utc_now(),
                "cached": False,
                "model_called": False,
                "attempts": attempts,
                "max_attempts": PROBE_MAX_ATTEMPTS,
                "recovered_after_retry": False,
                "model": _public_model_name(config.CHAT_MODEL_NAME),
                "error_code": "model_not_configured",
                "evidence_captured": False,
                "privacy": {
                    "secrets_exposed": False,
                    "paths_exposed": False,
                    "raw_content_included": False,
                },
            }
            captured = {"prompt": PROBE_PROMPT, "response": ""}
        except guarded_chat_service.ModelGatewayError:
            public = {
                "status": "failed",
                "checked_at": _utc_now(),
                "cached": False,
                "model_called": False,
                "attempts": attempts,
                "max_attempts": PROBE_MAX_ATTEMPTS,
                "recovered_after_retry": False,
                "model": _public_model_name(config.CHAT_MODEL_NAME),
                "error_code": "model_gateway_unavailable",
                "evidence_captured": False,
                "privacy": {
                    "secrets_exposed": False,
                    "paths_exposed": False,
                    "raw_content_included": False,
                },
            }
            captured = {"prompt": PROBE_PROMPT, "response": ""}
        except Exception:
            public = {
                "status": "failed",
                "checked_at": _utc_now(),
                "cached": False,
                "model_called": False,
                "attempts": attempts,
                "max_attempts": PROBE_MAX_ATTEMPTS,
                "recovered_after_retry": False,
                "model": _public_model_name(config.CHAT_MODEL_NAME),
                "error_code": "model_probe_failed",
                "evidence_captured": False,
                "privacy": {
                    "secrets_exposed": False,
                    "paths_exposed": False,
                    "raw_content_included": False,
                },
            }
            captured = {"prompt": PROBE_PROMPT, "response": ""}
        _PROBE_CACHE = (time.monotonic(), copy.deepcopy(public))
        return public, captured


def reset_for_tests() -> None:
    global _PASSIVE_CACHE, _PROBE_CACHE
    with _PASSIVE_LOCK:
        _PASSIVE_CACHE = None
    with _PROBE_LOCK:
        _PROBE_CACHE = None
