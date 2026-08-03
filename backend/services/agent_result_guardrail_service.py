"""Post-execution guardrail for content returned by Agent tools."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from services import agent_guardrail_service, guardrail_service

POLICY_VERSION = "agent-result-policy-2026.08.04-p3.2"

_INDIRECT_INJECTION = re.compile(
    r"(?:ignore|disregard|override|bypass).{0,40}(?:previous|prior|system|developer|safety).{0,30}(?:instruction|prompt|rule)"
    r"|(?:忽略|无视|覆盖|绕过).{0,24}(?:之前|先前|系统|开发者|安全).{0,20}(?:指令|提示词|规则)"
    r"|(?:system|developer)\s*(?:message|prompt)\s*[:：]"
    r"|(?:系统|开发者)(?:消息|提示词)\s*[:：]",
    re.IGNORECASE | re.DOTALL,
)
_SECRET = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|\b(?:api[_-]?key|access[_-]?token|secret|password|passwd)\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{8,}"
    r"|\bBearer\s+[A-Za-z0-9._~+/=-]{12,}",
    re.IGNORECASE,
)
_CHINESE_ID = re.compile(r"(?<!\d)[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?!\d)")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_DANGEROUS_COMMAND = re.compile(
    r"\brm\s+-[a-z]*r[a-z]*f\s+(?:/|~|\$home)"
    r"|\bdrop\s+(?:database|schema)\b"
    r"|\b(?:curl|wget)\b.{0,160}\|\s*(?:sh|bash)\b"
    r"|\bpowershell(?:\.exe)?\b.{0,80}-(?:enc|encodedcommand)\b"
    r"|\b(?:mkfs|format\s+[a-z]:|dd\s+.+\s+of=/dev/)\b",
    re.IGNORECASE | re.DOTALL,
)
_MALICIOUS_PAYLOAD = re.compile(
    r"(?:eval|exec)\s*\(\s*(?:base64_decode|atob)"
    r"|<script[^>]*>.*?(?:document\.cookie|fetch\s*\()"
    r"|(?:反弹|reverse)\s*(?:shell|外壳)",
    re.IGNORECASE | re.DOTALL,
)


def _deterministic_policy(content: str) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    categories: list[str] = []
    tier = "low"
    risk_score = 0.05

    def add(category: str, rule_id: str, message: str, *, block: bool, score: float) -> None:
        nonlocal tier, risk_score
        if category not in categories:
            categories.append(category)
        findings.append({"source": "policy", "rule_id": rule_id, "excerpt": message})
        tier = "block" if block else ("review" if tier == "low" else tier)
        risk_score = max(risk_score, score)

    if _INDIRECT_INJECTION.search(content):
        add(
            "prompt_injection",
            "AGENT-RESULT-INDIRECT-INJECTION",
            "工具返回内容包含试图覆盖上级指令的间接提示词注入信号。",
            block=False,
            score=0.72,
        )
    if _SECRET.search(content):
        add(
            "credential_leakage",
            "AGENT-RESULT-SECRET",
            "工具返回内容疑似包含凭证、访问令牌或私钥，禁止明文回传。",
            block=True,
            score=0.98,
        )
    if _CHINESE_ID.search(content) or _PHONE.search(content):
        add(
            "personal_data",
            "AGENT-RESULT-PII",
            "工具返回内容疑似包含身份证号或手机号，需要阻断并转人工取证。",
            block=True,
            score=0.94,
        )
    if _DANGEROUS_COMMAND.search(content):
        add(
            "hazardous_action_output",
            "AGENT-RESULT-DANGEROUS-COMMAND",
            "工具返回内容包含可直接触发破坏性执行的命令或管道。",
            block=True,
            score=0.99,
        )
    if _MALICIOUS_PAYLOAD.search(content):
        add(
            "malicious_code",
            "AGENT-RESULT-MALICIOUS-PAYLOAD",
            "工具返回内容包含疑似恶意载荷或远程执行片段。",
            block=True,
            score=0.97,
        )

    if not findings:
        findings.append({
            "source": "policy",
            "rule_id": "AGENT-RESULT-POLICY-PASS",
            "excerpt": "结果侧确定性策略未发现注入、凭证、隐私或危险执行信号。",
        })
    return {
        "tier": tier,
        "risk_score": risk_score,
        "categories": categories,
        "evidence": findings,
    }


def _semantic_check(content: str) -> dict[str, Any]:
    try:
        return guardrail_service.check(response=content, mode="response")
    except Exception as exc:
        return {
            "verdict": "borderline",
            "risk_score": 0.4,
            "categories": ["agent_security"],
            "evidence": [],
            "shadow_evaluation": {"status": "unavailable"},
            "engine": {
                "components": {"semantic": "unavailable"},
                "failure": type(exc).__name__,
            },
        }


def check_result(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    resource: str,
    content: str,
) -> dict[str, Any]:
    """Review a tool result before it is released back into an Agent context."""
    action_digest = agent_guardrail_service.action_digest(tool_name, arguments, resource)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    result_digest = hashlib.sha256(f"{action_digest}:{content_hash}".encode("ascii")).hexdigest()
    policy = _deterministic_policy(content)
    semantic = _semantic_check(content)

    categories = list(policy["categories"])
    for category in semantic.get("categories", []):
        category = str(category)[:80]
        if category and category not in categories:
            categories.append(category)

    semantic_verdict = str(semantic.get("verdict") or "borderline")
    if policy["tier"] == "block" or semantic_verdict == "unsafe":
        verdict, risk_code = "unsafe", "AGENT-RESULT-BLOCK"
    elif policy["tier"] == "review" or semantic_verdict == "borderline":
        verdict, risk_code = "borderline", "AGENT-RESULT-QUARANTINE"
    else:
        verdict, risk_code = "safe", "AGENT-RESULT-ALLOW"

    risk_score = max(float(policy["risk_score"]), float(semantic.get("risk_score") or 0.0))
    action_text = {
        "safe": "允许把当前工具结果回传给 Agent，并继续保留审计摘要。",
        "borderline": "隔离当前工具结果，等待审核员复核后再决定是否回传。",
        "unsafe": "阻断当前工具结果回传；危险原文只保留在加密证据库中。",
    }[verdict]
    evidence = list(policy["evidence"])
    for category in [str(value) for value in semantic.get("categories", [])][:4]:
        evidence.append({
            "source": "semantic",
            "rule_id": f"AGENT-RESULT-SEMANTIC-{category.upper()[:48]}",
            "excerpt": f"语义专家命中 {category[:80]} 风险类别；原始命中片段不在普通响应展示。",
        })

    released = verdict == "safe"
    semantic_engine = semantic.get("engine") or {}
    return {
        "verdict": verdict,
        "decision": verdict,
        "risk_level": "critical" if risk_score >= 0.95 else "high" if risk_score >= 0.7 else "medium" if risk_score >= 0.35 else "low",
        "risk_score": round(risk_score, 3),
        "intent": "agent_tool_result",
        "categories": categories,
        "evidence": evidence[:10],
        "actions": [action_text],
        "checks": [{
            "category": category,
            "score": round(risk_score, 3),
            "status": "blocked" if verdict == "unsafe" else "review" if verdict == "borderline" else "passed",
        } for category in (categories or ["agent_result_safety"])],
        "risk_code": risk_code,
        "action": action_text,
        "redline_answer": action_text,
        "risk_message": action_text,
        "content_released": released,
        "quarantined": not released,
        "released_content": content if released else action_text,
        "action_digest": action_digest,
        "content_hash": content_hash,
        "result_digest": result_digest,
        "scores": {
            "deterministic_policy": round(float(policy["risk_score"]), 3),
            "semantic_guardrail": round(float(semantic.get("risk_score") or 0.0), 3),
        },
        "shadow_evaluation": semantic.get("shadow_evaluation", {"status": "skipped"}),
        "engine": {
            "name": "agent_result_guardrail",
            "version": POLICY_VERSION,
            "components": {
                "result_policy": "ok",
                "semantic_guardrail": "ok" if semantic.get("verdict") else "unavailable",
                **(semantic_engine.get("components") or {}),
            },
        },
    }
