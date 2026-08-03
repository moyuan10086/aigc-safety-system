"""Verify production v1 auth, scope enforcement and usage for trajectories."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services import api_access_service  # noqa: E402


def _request(
    url: str,
    payload: dict[str, Any],
    api_key: str | None,
    timeout: float,
) -> tuple[int, dict[str, Any]]:
    headers = {"Content-Type": "application/json", "User-Agent": "aigc-p3-3-v1-smoke/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--endpoint",
        default="https://aigc.49.51.248.227.sslip.io/api/v1/guardrail/agent/trajectory/check",
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--output")
    args = parser.parse_args()

    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    wrong_scope = api_access_service.issue_key(
        tenant_id=f"p3-3-wrong-{suffix}",
        name="P3-3 production wrong-scope smoke",
        scopes=["guardrail:check"],
    )
    agent_scope = api_access_service.issue_key(
        tenant_id=f"p3-3-agent-{suffix}",
        name="P3-3 production agent-scope smoke",
        scopes=["guardrail:agent"],
    )
    payload = {
        "objective": "验证公开知识检索链",
        "session_id": f"prod-v1-smoke-{suffix}",
        "steps": [
            {
                "type": "action",
                "tool_name": "knowledge.search",
                "resource": "kb://redline",
                "arguments": {"query": "数据安全规范"},
            },
            {
                "type": "result",
                "tool_name": "knowledge.search",
                "resource": "kb://redline",
                "arguments": {"query": "数据安全规范"},
                "content": "检索到公开的数据安全管理要求。",
            },
        ],
    }

    try:
        unauthorized_status, unauthorized_body = _request(
            args.endpoint, payload, None, args.timeout
        )
        forbidden_status, forbidden_body = _request(
            args.endpoint, payload, wrong_scope["key"], args.timeout
        )
        allowed_status, allowed_body = _request(
            args.endpoint, payload, agent_scope["key"], args.timeout
        )
        client = api_access_service.authenticate(agent_scope["key"])
        usage = api_access_service.usage(client, days=1) if client else {}
        operation_count = sum(
            int(item.get("calls") or 0)
            for item in usage.get("by_operation", [])
            if item.get("operation") == "guardrail.agent_trajectory_check"
        )
    finally:
        wrong_revoked = api_access_service.revoke_key(wrong_scope["key_id"])
        agent_revoked = api_access_service.revoke_key(agent_scope["key_id"])

    data = allowed_body.get("data") or {}
    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "endpoint": args.endpoint,
        "content_policy": "API keys and raw trajectory content are excluded from this report.",
        "checks": {
            "unauthorized_status": unauthorized_status,
            "unauthorized_code": (unauthorized_body.get("detail") or {}).get("code"),
            "wrong_scope_status": forbidden_status,
            "wrong_scope_code": (forbidden_body.get("detail") or {}).get("code"),
            "allowed_status": allowed_status,
            "allowed_verdict": data.get("verdict"),
            "usage_operation": "guardrail.agent_trajectory_check",
            "usage_operation_count": operation_count,
            "temporary_keys_revoked": bool(wrong_revoked and agent_revoked),
        },
    }
    report["passed"] = (
        unauthorized_status == 401
        and forbidden_status == 403
        and allowed_status == 200
        and data.get("verdict") == "safe"
        and operation_count == 1
        and report["checks"]["temporary_keys_revoked"]
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
