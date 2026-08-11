"""Compose audit, report and model state into one dashboard snapshot."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import config
from services import audit_log_service, guarded_chat_service, ip_region_service

REPORTS_DIR = Path(__file__).parents[1] / "reports"
DEEPFAKE_WEIGHTS = Path(__file__).parents[2] / "deepfake-detection" / "weights" / "model.ckpt"


def _report_statistics(start: datetime, end: datetime | None = None) -> dict[str, Any]:
    total = 0
    in_window = 0
    fake_count = 0
    risk_count = 0
    latest_at: str | None = None
    if not REPORTS_DIR.exists():
        return {
            "total": 0,
            "in_window": 0,
            "fake_count": 0,
            "risk_count": 0,
            "latest_at": None,
        }
    for path in REPORTS_DIR.glob("*.json"):
        total += 1
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            created_text = str(report.get("created_at") or "")
            created_at = datetime.fromisoformat(created_text.replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at >= start and (end is None or created_at <= end):
                in_window += 1
                deepfake = report.get("deepfake") or {}
                mllm = report.get("mllm") or {}
                rag = report.get("rag") or {}
                fake_count += int(deepfake.get("label") == "fake" or mllm.get("verdict") == "fake")
                risk_count += int(rag.get("safe") is False)
            normalized = created_at.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            if latest_at is None or normalized > latest_at:
                latest_at = normalized
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return {
        "total": total,
        "in_window": in_window,
        "fake_count": fake_count,
        "risk_count": risk_count,
        "latest_at": latest_at,
    }


def _model_states() -> list[dict[str, Any]]:
    chat = guarded_chat_service.model_status()
    return [
        {
            "id": "generator",
            "label": "文本生成模型",
            "model": chat.get("model") or config.CHAT_MODEL_NAME,
            "status": "configured" if chat.get("configured") else "unconfigured",
        },
        {
            "id": "qwen3guard",
            "label": "Qwen3Guard 分类器",
            "model": config.GUARDRAIL_QWEN_MODEL,
            "status": (
                "enabled"
                if config.GUARDRAIL_ENABLE_QWEN_CLASSIFIER and config.GUARDRAIL_QWEN_API_KEY
                else "degraded"
                if config.GUARDRAIL_ENABLE_QWEN_CLASSIFIER
                else "standby"
            ),
        },
        {
            "id": "singguard",
            "label": "SingGuard-NSFA 分类器",
            "model": config.GUARDRAIL_SINGGUARD_MODEL,
            "status": (
                "enabled"
                if config.GUARDRAIL_ENABLE_SINGGUARD_CLASSIFIER and config.GUARDRAIL_SINGGUARD_API_KEY
                else "degraded"
                if config.GUARDRAIL_ENABLE_SINGGUARD_CLASSIFIER
                else "standby"
            ),
        },
        {
            "id": "xgboost_shadow",
            "label": "XGBoost 影子评测",
            "model": "Local Hybrid Safety Model",
            "status": "enabled" if config.GUARDRAIL_ENABLE_XGBOOST_SHADOW else "standby",
        },
        {
            "id": "deepfake",
            "label": "Deepfake 检测",
            "model": "DFDet model.ckpt",
            "status": "configured" if DEEPFAKE_WEIGHTS.exists() else "degraded",
        },
        {
            "id": "rag",
            "label": "红线知识库审核（RAG）",
            "model": "RAG hybrid retrieval · ChromaDB vector store",
            "status": "enabled" if config.GUARDRAIL_ENABLE_RAG else "standby",
        },
    ]


def overview(hours: int = 24, *, reviewer: str | None = None, start: datetime | None = None, end: datetime | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    audit = audit_log_service.dashboard_statistics(hours=hours, now=now, start=start, end=end)
    history = audit_log_service.dashboard_statistics(hours=168, now=now)
    window_start = datetime.fromisoformat(audit["window"]["start"].replace("Z", "+00:00"))
    window_end = datetime.fromisoformat(audit["window"]["end"].replace("Z", "+00:00"))
    custom_window = start is not None or end is not None
    reports = _report_statistics(window_start, window_end if custom_window else None)
    shadow = audit_log_service.shadow_review_statistics(
        hours=audit["window"]["hours"], now=now, start=window_start, end=window_end if custom_window else None, reviewer=reviewer
    )
    models = _model_states()
    region_sources = audit["top_sources"] or history["top_sources"]
    audit.update({
        "generated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "reports": reports,
        "historical": {
            "window": history["window"],
            "summary": history["summary"],
            "timeline": history["timeline"],
            "risk_distribution": history["risk_distribution"],
            "recent_alerts": history["recent_alerts"],
            "top_sources": history["top_sources"],
        },
        "source_regions": ip_region_service.aggregate_source_regions(region_sources),
        "shadow_evaluation": {key: value for key, value in shadow.items() if key != "queue"},
        "shadow_reviews": shadow["queue"],
        "models": models,
        "service_health": {
            "api": "online",
            "audit_chain": "healthy" if audit["chain_valid"] else "degraded",
            "raw_evidence_vault": "enabled" if config.AUDIT_STORE_RAW_CONTENT else "disabled",
            "configured_models": sum(item["status"] in {"configured", "enabled"} for item in models),
            "total_models": len(models),
        },
        "data_sources": [
            "SQLite audit_events",
            "JSON detection reports",
            "runtime model configuration",
        ],
        "privacy": {
            "raw_content_included": False,
            "encrypted_evidence_retained": bool(config.AUDIT_STORE_RAW_CONTENT),
        },
    })
    return audit
