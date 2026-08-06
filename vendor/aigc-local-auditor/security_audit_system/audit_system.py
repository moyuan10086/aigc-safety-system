from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
ROOT = BASE_DIR.parents[0]
for path in (BASE_DIR, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ai_security_audit.hybrid import HybridSafetyAuditor


@dataclass(frozen=True)
class AuditOutput:
    decision: str
    confidence: float
    alert: bool
    latency_ms: float
    risk_type: str
    route: str
    votes: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SecurityAuditSystem:
    """Local AI safety audit system.

    The public decision is binary: pass/fail. Low-confidence or routed samples
    are marked with alert=true for human review, without changing decision.
    """

    def __init__(
        self,
        config_path: str | Path | None = None,
        *,
        model_path: str | Path | None = None,
        alert_confidence_threshold: float | None = None,
        enable_alert: bool | None = None,
        include_votes: bool | None = None,
    ) -> None:
        self.base_dir = BASE_DIR
        config = self._load_config(config_path)
        raw_model_path = Path(model_path or config.get("model_path", "models/hybrid_safety_model_xgboost_color.json"))
        if not raw_model_path.is_absolute():
            raw_model_path = self.base_dir / raw_model_path
        self.model_path = raw_model_path
        self.alert_confidence_threshold = float(
            alert_confidence_threshold
            if alert_confidence_threshold is not None
            else config.get("alert_confidence_threshold", 0.60)
        )
        self.enable_alert = bool(config.get("enable_alert", True) if enable_alert is None else enable_alert)
        self.include_votes = bool(config.get("include_votes", True) if include_votes is None else include_votes)
        self._auditor = HybridSafetyAuditor.load(self.model_path)

    def audit(self, text: str) -> AuditOutput:
        start = time.perf_counter()
        text = str(text or "")
        guard = self._local_guard(text)
        result = self._auditor.audit_request(text, include_evidence=False)
        latency_ms = (time.perf_counter() - start) * 1000
        decision = guard["decision"] if guard else self._binary_decision(result.decision)
        confidence = max(float(result.confidence), float(guard["confidence"])) if guard else float(result.confidence)
        alert = False if guard else self._should_alert(result)
        votes = [
            {
                "source": vote.source,
                "decision": self._binary_decision(vote.decision),
                "confidence": round(float(vote.confidence), 4),
                "reason": vote.reason,
                "risk_type": vote.risk_type,
            }
            for vote in result.votes
        ]
        if guard:
            votes.insert(0, guard)
        return AuditOutput(
            decision=decision,
            confidence=round(confidence, 4),
            alert=alert,
            latency_ms=round(latency_ms, 4),
            risk_type=guard["risk_type"] if guard else result.risk_type,
            route=result.route,
            votes=votes if self.include_votes else [],
        )

    def audit_dict(self, text: str) -> dict[str, Any]:
        return self.audit(text).to_dict()

    def audit_json(self, text: str) -> str:
        return json.dumps(self.audit_dict(text), ensure_ascii=False, indent=2)

    def _should_alert(self, result: Any) -> bool:
        if not self.enable_alert:
            return False
        if result.decision == "alert":
            return True
        if float(result.confidence) < self.alert_confidence_threshold:
            return True
        return result.route in {"cloud", "human_review"}

    @staticmethod
    def _binary_decision(decision: str) -> str:
        return "fail" if decision == "alert" else str(decision)

    @staticmethod
    def _local_guard(text: str) -> dict[str, Any] | None:
        high_risk_object = r"(炸药|爆炸物|枪支|弹药|毒品|木马|勒索软件|非法集资|传销|诈骗|洗钱|偷拍视频|人肉|开盒)"
        harmful_intent = r"(如何|怎么|怎样|步骤|教程|制作|制造|获取|传播|规避|绕过|变现|实施|操作)"
        if re.search(harmful_intent, text) and re.search(high_risk_object, text):
            return {
                "source": "local_high_risk_guard",
                "decision": "fail",
                "confidence": 0.92,
                "reason": "high risk object with operational intent",
                "risk_type": "high_risk_instruction",
            }
        return None

    def _load_config(self, config_path: str | Path | None) -> dict[str, Any]:
        path = Path(config_path) if config_path else self.base_dir / "config.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
