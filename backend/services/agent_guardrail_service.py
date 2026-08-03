"""Pre-execution guardrail for autonomous Agent tool actions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any

import config
from services import audit_log_service, guardrail_service

POLICY_VERSION = "agent-policy-2026.08.04-p3.1"
_SENSITIVE_KEY = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|session|credential)",
    re.IGNORECASE,
)
_READ_ONLY = re.compile(
    r"(?:^|[._:-])(?:get|list|read|search|fetch|query|view|inspect|describe|status|health)(?:$|[._:-])",
    re.IGNORECASE,
)
_DESTRUCTIVE = re.compile(
    r"(?:delete|remove|destroy|drop|truncate|format|erase|purge|wipe|rm\s|del\s)",
    re.IGNORECASE,
)
_EXECUTION = re.compile(
    r"(?:execute|exec|run|shell|terminal|command|script|deploy|restart|stop|kill)",
    re.IGNORECASE,
)
_PRIVILEGE = re.compile(
    r"(?:sudo|chmod|chown|grant|revoke|permission|privilege|role|iam|admin)",
    re.IGNORECASE,
)
_OUTBOUND = re.compile(
    r"(?:send|publish|upload|webhook|email|message|http[_-]?post|external)",
    re.IGNORECASE,
)
_IRREVERSIBLE = re.compile(
    r"(?:rm\s+-[a-z]*r[a-z]*f\s+(?:/|~|\$home)|"
    r"rm\s+-[a-z]*f[a-z]*r\s+(?:/|~|\$home)|"
    r"drop\s+(?:database|schema)\b|format\s+[a-z]:|mkfs(?:\.|\s)|"
    r"dd\s+.+\s+of=/dev/|delete\s+(?:all|everything)\b)",
    re.IGNORECASE,
)


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def canonical_action(tool_name: str, arguments: dict[str, Any], resource: str) -> str:
    payload = {
        "tool_name": tool_name.strip().lower(),
        "resource": resource.strip(),
        "arguments": arguments,
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def action_digest(tool_name: str, arguments: dict[str, Any], resource: str) -> str:
    return hashlib.sha256(
        canonical_action(tool_name, arguments, resource).encode("utf-8")
    ).hexdigest()


def _redact(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if depth >= 5:
        return "[MAX_DEPTH]"
    if isinstance(value, dict):
        return {
            str(item_key)[:80]: _redact(item_value, key=str(item_key), depth=depth + 1)
            for item_key, item_value in list(value.items())[:50]
        }
    if isinstance(value, list):
        return [_redact(item, depth=depth + 1) for item in value[:30]]
    if isinstance(value, str):
        return value[:500]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:200]


def _policy(tool_name: str, arguments: dict[str, Any], resource: str) -> dict[str, Any]:
    canonical = canonical_action(tool_name, arguments, resource)
    searchable = f"{tool_name}\n{resource}\n{canonical}".lower()
    normalized_resource = resource.strip().lower().replace("\\", "/")
    destructive = bool(_DESTRUCTIVE.search(searchable))
    root_scope = normalized_resource in {"/", "~", "*", "all", "c:/", "c:"}

    if _IRREVERSIBLE.search(searchable) or (destructive and root_scope):
        return {
            "tier": "prohibited",
            "risk_score": 0.99,
            "categories": ["agent_tool_abuse", "irreversible_action"],
            "evidence": [{
                "source": "policy",
                "rule_id": "AGENT-DENY-IRREVERSIBLE",
                "excerpt": "检测到整库、根目录或不可恢复的破坏性动作，策略强制阻断。",
            }],
        }

    factors: list[tuple[str, str, str]] = []
    if destructive:
        factors.append(("agent_tool_abuse", "AGENT-APPROVE-DESTRUCTIVE", "检测到删除或破坏性写操作。"))
    if _EXECUTION.search(searchable):
        factors.append(("agent_tool_abuse", "AGENT-APPROVE-EXEC", "检测到命令、脚本或服务执行操作。"))
    if _PRIVILEGE.search(searchable):
        factors.append(("authorization_change", "AGENT-APPROVE-PRIVILEGE", "检测到权限或角色变更。"))
    if _OUTBOUND.search(searchable):
        factors.append(("data_egress", "AGENT-APPROVE-OUTBOUND", "检测到数据外发或对外发布。"))
    if _SENSITIVE_KEY.search(searchable):
        factors.append(("sensitive_data", "AGENT-APPROVE-SECRET", "检测到凭证或敏感会话数据访问。"))

    if factors:
        return {
            "tier": "high",
            "risk_score": min(0.92, 0.68 + len(factors) * 0.06),
            "categories": list(dict.fromkeys(item[0] for item in factors)),
            "evidence": [
                {"source": "policy", "rule_id": rule_id, "excerpt": message}
                for _, rule_id, message in factors
            ],
        }
    if _READ_ONLY.search(tool_name):
        return {
            "tier": "low",
            "risk_score": 0.08,
            "categories": [],
            "evidence": [{
                "source": "policy",
                "rule_id": "AGENT-ALLOW-READONLY",
                "excerpt": "工具动作为明确的只读查询，未发现写入、外发或越权信号。",
            }],
        }
    return {
        "tier": "unknown",
        "risk_score": 0.46,
        "categories": ["agent_security"],
        "evidence": [{
            "source": "policy",
            "rule_id": "AGENT-REVIEW-UNKNOWN",
            "excerpt": "工具能力未命中只读白名单，需要审核员确认资源范围。",
        }],
    }


def _semantic_check(tool_name: str, arguments: dict[str, Any], resource: str) -> dict[str, Any]:
    redacted_arguments = _redact(arguments)
    resource_without_query = resource.split("?", 1)[0][:500]
    summary = json.dumps({
        "agent_tool": tool_name[:120],
        "resource_scope": resource_without_query,
        "arguments": redacted_arguments,
        "task": "pre-execution safety review",
    }, ensure_ascii=False, sort_keys=True)
    try:
        return guardrail_service.check(response=summary, mode="response")
    except Exception as exc:
        return {
            "verdict": "borderline",
            "risk_score": 0.4,
            "categories": ["agent_security"],
            "evidence": [{
                "source": "semantic",
                "rule_id": "AGENT-SEMANTIC-UNAVAILABLE",
                "excerpt": f"语义专家不可用：{type(exc).__name__}",
            }],
            "engine": {"components": {"semantic": "unavailable"}},
        }


def issue_approval(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    resource: str,
    approver: str,
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    if not config.AGENT_APPROVAL_SIGNING_SECRET:
        raise RuntimeError("Agent 审批签名密钥尚未配置")
    policy = _policy(tool_name, arguments, resource)
    if policy["tier"] == "prohibited":
        raise ValueError("不可恢复的破坏性动作不能签发审批凭证")
    ttl = int(ttl_seconds or config.AGENT_APPROVAL_TTL_SECONDS)
    max_ttl = max(60, int(config.AGENT_APPROVAL_MAX_TTL_SECONDS))
    ttl = max(60, min(ttl, max_ttl))
    issued_at = int(time.time())
    expires_at = issued_at + ttl
    digest = action_digest(tool_name, arguments, resource)
    token_id = secrets.token_hex(16)
    payload = {
        "kind": "agent_action_approval",
        "act": digest,
        "sub": approver,
        "iat": issued_at,
        "exp": expires_at,
        "jti": token_id,
    }
    body = _encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    signature = hmac.new(
        config.AGENT_APPROVAL_SIGNING_SECRET.encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256,
    ).digest()
    audit_log_service.register_agent_approval(
        token_id=token_id,
        action_digest=digest,
        approver=approver,
        issued_at=datetime.fromtimestamp(issued_at, timezone.utc).isoformat().replace("+00:00", "Z"),
        expires_at=datetime.fromtimestamp(expires_at, timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    return {
        "approval_token": f"{body}.{_encode(signature)}",
        "approval_id": token_id[:12],
        "action_digest": digest,
        "approver": approver,
        "expires_at": datetime.fromtimestamp(expires_at, timezone.utc).isoformat().replace("+00:00", "Z"),
        "single_use": True,
    }


def _consume_approval(token: str, digest: str) -> tuple[str, str | None]:
    try:
        body, signature_text = token.split(".", 1)
        expected = hmac.new(
            config.AGENT_APPROVAL_SIGNING_SECRET.encode("utf-8"),
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_decode(signature_text), expected):
            return "invalid", None
        payload = json.loads(_decode(body))
        if payload.get("kind") != "agent_action_approval":
            return "invalid", None
        if not hmac.compare_digest(str(payload.get("act", "")), digest):
            return "mismatch", str(payload.get("sub") or "") or None
        now = int(time.time())
        if int(payload.get("exp", 0)) <= now:
            return "expired", str(payload.get("sub") or "") or None
        now_text = datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")
        return audit_log_service.consume_agent_approval(
            token_id=str(payload["jti"]),
            action_digest=digest,
            now=now_text,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return "invalid", None


def check_action(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    resource: str,
    approval_token: str | None = None,
) -> dict[str, Any]:
    policy = _policy(tool_name, arguments, resource)
    semantic = _semantic_check(tool_name, arguments, resource)
    digest = action_digest(tool_name, arguments, resource)
    requires_approval = policy["tier"] in {"high", "unknown"}
    approval_status = "not_required" if not requires_approval else "missing"
    approver = None
    if approval_token:
        if not config.AGENT_APPROVAL_SIGNING_SECRET:
            approval_status = "invalid"
        else:
            approval_status, approver = _consume_approval(approval_token, digest)

    categories = list(policy["categories"])
    semantic_categories = [str(value) for value in semantic.get("categories", [])]
    for category in semantic_categories:
        if category not in categories:
            categories.append(category)

    if policy["tier"] == "prohibited":
        verdict, risk_code = "unsafe", "AGENT-BLOCK-IRREVERSIBLE"
    elif approval_token and approval_status != "valid":
        verdict, risk_code = "unsafe", "AGENT-BLOCK-AUTHORIZATION"
        categories.insert(0, "authorization_failure")
    elif requires_approval and approval_status != "valid":
        verdict, risk_code = "borderline", "AGENT-APPROVAL-REQUIRED"
    elif not requires_approval and semantic.get("verdict") in {"borderline", "unsafe"}:
        verdict, risk_code = "borderline", "AGENT-SEMANTIC-REVIEW"
    else:
        verdict = "safe"
        risk_code = "AGENT-ALLOW-APPROVED" if approval_status == "valid" else "AGENT-ALLOW"

    risk_score = max(float(policy["risk_score"]), float(semantic.get("risk_score") or 0.0))
    if approval_token and approval_status != "valid":
        risk_score = max(risk_score, 0.96)
    evidence = list(policy["evidence"])
    for item in semantic.get("evidence", [])[:4]:
        if not isinstance(item, dict):
            continue
        evidence.append({
            "source": str(item.get("source") or "semantic")[:40],
            "rule_id": str(item.get("rule_id") or item.get("ability") or "SEMANTIC")[:80],
            "excerpt": str(item.get("excerpt") or item.get("message") or "语义专家命中")[:220],
        })
    if approval_status == "valid":
        evidence.append({
            "source": "authorization",
            "rule_id": "AGENT-APPROVAL-VALID",
            "excerpt": "一次性审批凭证与工具、资源及参数摘要精确匹配，已原子消费。",
        })
    elif approval_token:
        evidence.append({
            "source": "authorization",
            "rule_id": f"AGENT-APPROVAL-{approval_status.upper()}",
            "excerpt": "审批凭证无效、过期、已使用或与当前动作不匹配。",
        })

    action_text = {
        "safe": "允许 Agent 执行当前精确动作，并继续保留执行结果审计。",
        "borderline": "暂停工具调用，需登录审核员签发与当前动作精确绑定的一次性凭证。",
        "unsafe": "阻断工具调用；该动作违反不可恢复操作或授权完整性策略。",
    }[verdict]
    semantic_engine = semantic.get("engine") or {}
    return {
        "verdict": verdict,
        "decision": verdict,
        "risk_level": "critical" if risk_score >= 0.95 else "high" if risk_score >= 0.7 else "medium" if risk_score >= 0.35 else "low",
        "risk_score": round(risk_score, 3),
        "intent": "agent_tool_execution",
        "categories": categories,
        "evidence": evidence[:10],
        "actions": [action_text],
        "checks": [{
            "category": category,
            "score": round(risk_score, 3),
            "status": "blocked" if verdict == "unsafe" else "review" if verdict == "borderline" else "passed",
        } for category in (categories or ["agent_security"])],
        "risk_code": risk_code,
        "action": action_text,
        "redline_answer": action_text,
        "scores": {
            "deterministic_policy": round(float(policy["risk_score"]), 3),
            "semantic_guardrail": round(float(semantic.get("risk_score") or 0.0), 3),
        },
        "approval": {
            "required": requires_approval,
            "status": approval_status,
            "valid": approval_status == "valid",
            "approver": approver,
            "single_use": True,
        },
        "action_digest": digest,
        "engine": {
            "name": "agent_execution_guardrail",
            "version": POLICY_VERSION,
            "components": {
                "policy": "ok",
                "semantic_guardrail": "ok" if semantic.get("verdict") else "unavailable",
                **(semantic_engine.get("components") or {}),
            },
        },
    }
