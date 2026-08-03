"""Session-level risk correlation for multi-step Agent trajectories."""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

from services import (
    agent_guardrail_service,
    agent_result_guardrail_service,
    guardrail_service,
)

POLICY_VERSION = "agent-trajectory-policy-2026.08.04-p3.3"
_PROPAGATION_CATEGORIES = {
    "authorization_change",
    "credential_leakage",
    "data_egress",
    "hazardous_action_output",
    "malicious_code",
    "personal_data",
    "sensitive_data",
}


def canonical_trajectory(objective: str, steps: list[dict[str, Any]]) -> str:
    return json.dumps(
        {"objective": objective.strip(), "steps": steps},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def trajectory_digest(objective: str, steps: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_trajectory(objective, steps).encode("utf-8")).hexdigest()


def _check_message(step: dict[str, Any]) -> dict[str, Any]:
    content = str(step.get("content") or "")
    if step.get("direction") == "output":
        return guardrail_service.check(response=content, mode="response")
    return guardrail_service.check(prompt=content, mode="prompt")


def _check_step(step: dict[str, Any]) -> dict[str, Any]:
    step_type = step["step_type"]
    if step_type == "action":
        return agent_guardrail_service.check_action(
            tool_name=step["tool_name"],
            arguments=step.get("arguments") or {},
            resource=step["resource"],
            approval_token=None,
        )
    if step_type == "result":
        return agent_result_guardrail_service.check_result(
            tool_name=step["tool_name"],
            arguments=step.get("arguments") or {},
            resource=step["resource"],
            content=step["content"],
        )
    return _check_message(step)


def _step_summary(index: int, step: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    engine = result.get("engine") or {}
    summary = {
        "index": index,
        "type": step["step_type"],
        "direction": step.get("direction") if step["step_type"] == "message" else None,
        "verdict": result.get("verdict", "borderline"),
        "risk_score": round(float(result.get("risk_score") or 0.0), 3),
        "risk_code": str(result.get("risk_code") or "GR-REVIEW")[:80],
        "categories": [str(value)[:80] for value in result.get("categories", [])[:8]],
        "content_hash": result.get("content_hash") or (
            hashlib.sha256(str(step.get("content") or "").encode("utf-8")).hexdigest()
            if step["step_type"] == "message"
            else None
        ),
        "action_digest": result.get("action_digest"),
        "result_digest": result.get("result_digest"),
        "content_released": result.get("content_released"),
        "approval_required": bool((result.get("approval") or {}).get("required")),
        "approval_status": (result.get("approval") or {}).get("status"),
        "components": engine.get("components") or {},
    }
    return {key: value for key, value in summary.items() if value is not None}


def _component_counts(step_summaries: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for step in step_summaries:
        for component, status in step.get("components", {}).items():
            component_counts = counts.setdefault(str(component)[:80], {})
            status_text = str(status)[:40]
            component_counts[status_text] = component_counts.get(status_text, 0) + 1
    return counts


def check_trajectory(
    *,
    objective: str,
    steps: list[dict[str, Any]],
    session_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate a submitted trajectory without executing any represented action."""
    digest = trajectory_digest(objective, steps)
    session_id = session_id or f"traj-{secrets.token_hex(8)}"
    summaries: list[dict[str, Any]] = []
    prior_actions: dict[str, dict[str, Any]] = {}
    tainted_steps: list[int] = []
    cross_rules: list[dict[str, Any]] = []

    def add_rule(rule_id: str, indexes: list[int], message: str, score: float) -> None:
        if any(item["rule_id"] == rule_id and item["step_indexes"] == indexes for item in cross_rules):
            return
        cross_rules.append({
            "source": "trajectory_policy",
            "rule_id": rule_id,
            "step_indexes": indexes,
            "excerpt": message,
            "risk_score": score,
        })

    for index, step in enumerate(steps, start=1):
        result = _check_step(step)
        summary = _step_summary(index, step, result)
        summaries.append(summary)
        step_type = step["step_type"]
        digest_key = summary.get("action_digest")

        if step_type == "action" and digest_key:
            prior_actions[digest_key] = summary
            action_categories = set(summary.get("categories", []))
            if tainted_steps and action_categories.intersection(_PROPAGATION_CATEGORIES):
                add_rule(
                    "AGENT-TRAJECTORY-TAINT-TO-ACTION",
                    [tainted_steps[-1], index],
                    "受污染工具结果后出现外发、权限、凭证或高影响动作，阻断风险传播。",
                    0.98,
                )

        if step_type == "result":
            action = prior_actions.get(digest_key or "")
            if action is None:
                add_rule(
                    "AGENT-TRAJECTORY-ORPHAN-RESULT",
                    [index],
                    "轨迹中出现没有对应执行前门禁记录的工具结果，需要人工复核来源。",
                    0.55,
                )
            elif action.get("approval_required") and action.get("approval_status") != "valid":
                add_rule(
                    "AGENT-TRAJECTORY-EXECUTED-WITHOUT-APPROVAL",
                    [action["index"], index],
                    "高风险动作未获得有效审批却出现执行结果，判定为授权绕过。",
                    0.99,
                )
            if summary["verdict"] != "safe":
                tainted_steps.append(index)

        if step_type == "message" and step.get("direction") == "output" and tainted_steps:
            add_rule(
                "AGENT-TRAJECTORY-TAINT-TO-OUTPUT",
                [tainted_steps[-1], index],
                "受污染工具结果随后进入 Agent 输出，阻断间接提示词注入传播。",
                0.96,
            )

    non_safe = [step for step in summaries if step["verdict"] != "safe"]
    unsafe = [step for step in summaries if step["verdict"] == "unsafe"]
    max_step_score = max((float(step["risk_score"]) for step in summaries), default=0.0)
    correlation_score = max((float(rule["risk_score"]) for rule in cross_rules), default=0.0)
    risk_score = max(max_step_score, correlation_score)
    if len(non_safe) >= 2:
        risk_score = max(risk_score, 0.86)
        add_rule(
            "AGENT-TRAJECTORY-CUMULATIVE-RISK",
            [step["index"] for step in non_safe],
            "多个步骤连续触发风险，单步风险已累积升级为会话级阻断。",
            0.86,
        )
        correlation_score = max(
            float(rule["risk_score"]) for rule in cross_rules
        )

    blocking_rules = {
        "AGENT-TRAJECTORY-TAINT-TO-ACTION",
        "AGENT-TRAJECTORY-TAINT-TO-OUTPUT",
        "AGENT-TRAJECTORY-EXECUTED-WITHOUT-APPROVAL",
        "AGENT-TRAJECTORY-CUMULATIVE-RISK",
    }
    if unsafe or any(rule["rule_id"] in blocking_rules for rule in cross_rules):
        verdict, risk_code = "unsafe", "AGENT-TRAJECTORY-BLOCK"
    elif non_safe or cross_rules:
        verdict, risk_code = "borderline", "AGENT-TRAJECTORY-REVIEW"
    else:
        verdict, risk_code = "safe", "AGENT-TRAJECTORY-ALLOW"

    categories: list[str] = []
    for step in summaries:
        for category in step.get("categories", []):
            if category not in categories:
                categories.append(category)
    if cross_rules:
        categories.insert(0, "trajectory_risk")

    action_text = {
        "safe": "轨迹未发现跨步骤风险，可以继续执行后续受控流程。",
        "borderline": "轨迹存在来源或上下文缺口，暂停并转交审核员复核。",
        "unsafe": "轨迹存在污染传播、授权绕过或累积风险，阻断后续执行。",
    }[verdict]
    return {
        "verdict": verdict,
        "decision": verdict,
        "risk_level": "critical" if risk_score >= 0.95 else "high" if risk_score >= 0.7 else "medium" if risk_score >= 0.35 else "low",
        "risk_score": round(risk_score, 3),
        "risk_code": risk_code,
        "intent": "agent_trajectory",
        "session_id": session_id,
        "trajectory_digest": digest,
        "objective_hash": hashlib.sha256(objective.strip().encode("utf-8")).hexdigest(),
        "step_count": len(summaries),
        "non_safe_steps": len(non_safe),
        "categories": categories[:12],
        "steps": summaries,
        "cross_step_rules": cross_rules,
        "evidence": cross_rules,
        "checks": [{
            "category": "agent_trajectory",
            "score": round(risk_score, 3),
            "status": "blocked" if verdict == "unsafe" else "review" if verdict == "borderline" else "passed",
        }],
        "actions": [action_text],
        "action": action_text,
        "redline_answer": action_text,
        "risk_message": action_text,
        "scores": {
            "max_step_risk": round(max_step_score, 3),
            "cross_step_risk": round(correlation_score, 3),
        },
        "engine": {
            "name": "agent_trajectory_guardrail",
            "version": POLICY_VERSION,
            "tool_execution": "disabled",
            "approval_token_consumption": "disabled",
            "component_statuses": _component_counts(summaries),
        },
    }
