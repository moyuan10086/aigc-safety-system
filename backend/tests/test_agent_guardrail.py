"""Tests for exact-action Agent approvals and the pre-execution API."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from routers.api_v1 import router as api_v1_router
from routers.auth import router as auth_router
from routers.guardrail import router as guardrail_router
from services import (
    agent_guardrail_service,
    api_access_service,
    audit_log_service,
    auth_service,
)


SAFE_SEMANTIC = {
    "verdict": "safe",
    "risk_score": 0.03,
    "categories": [],
    "evidence": [],
    "engine": {"components": {"rules": "ok", "singguard": "ok"}},
}


class AgentGuardrailTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.password = "Agent-Reviewer-2026"
        self.config = patch.multiple(
            config,
            AUDIT_LOG_DB_PATH=str(root / "audit.db"),
            AUDIT_STORE_RAW_CONTENT=True,
            AUDIT_CONTENT_KEY="test-agent-evidence-key",
            AUTH_USERNAME="operator",
            AUTH_DISPLAY_NAME="安全审核员",
            AUTH_ROLE="operator",
            AUTH_PASSWORD_HASH=auth_service.hash_password(
                self.password, iterations=100_000
            ),
            AUTH_OPERATORS_JSON="",
            AUTH_SESSION_SECRET="test-agent-session-secret",
            AUTH_SESSION_TTL_SECONDS=3600,
            AUTH_COOKIE_SECURE=False,
            AGENT_APPROVAL_SIGNING_SECRET="test-agent-approval-secret",
            AGENT_APPROVAL_TTL_SECONDS=300,
            AGENT_APPROVAL_MAX_TTL_SECONDS=900,
            API_KEY_DB_PATH=str(root / "api-keys.db"),
            API_KEY_HASH_SECRET="test-agent-api-key-secret",
            API_KEY_DEFAULT_RATE_LIMIT=60,
            API_KEY_DEFAULT_DAILY_QUOTA=5000,
            API_KEY_MAX_RATE_LIMIT=600,
            API_KEY_MAX_DAILY_QUOTA=100000,
        )
        self.config.start()
        audit_log_service.reset_for_tests()
        api_access_service.reset_for_tests()
        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(guardrail_router)
        app.include_router(api_v1_router)
        self.client = TestClient(app)
        self.semantic = patch.object(
            agent_guardrail_service,
            "_semantic_check",
            return_value=SAFE_SEMANTIC,
        )
        self.semantic.start()

    def tearDown(self):
        self.semantic.stop()
        self.client.close()
        audit_log_service.reset_for_tests()
        api_access_service.reset_for_tests()
        self.config.stop()
        self.temp_dir.cleanup()

    def _login(self):
        response = self.client.post(
            "/api/auth/login",
            json={"username": "operator", "password": self.password},
        )
        self.assertEqual(response.status_code, 200)

    @staticmethod
    def _dangerous_action(**overrides):
        body = {
            "tool_name": "database.drop_table",
            "resource": "prod://orders",
            "arguments": {"table": "stale_orders", "backup_id": "bk-20260804"},
        }
        body.update(overrides)
        return body

    def test_read_only_action_is_allowed_without_approval(self):
        response = self.client.post(
            "/api/guardrail/agent/check",
            json={
                "tool_name": "knowledge.search",
                "resource": "kb://redline",
                "arguments": {"query": "数据安全规范"},
            },
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["verdict"], "safe")
        self.assertEqual(result["risk_code"], "AGENT-ALLOW")
        self.assertFalse(result["approval"]["required"])
        self.assertTrue(audit_log_service.verify_chain())

    def test_high_risk_action_requires_and_consumes_exact_approval_once(self):
        action = self._dangerous_action()
        first = self.client.post("/api/guardrail/agent/check", json=action).json()
        self.assertEqual(first["verdict"], "borderline")
        self.assertEqual(first["approval"]["status"], "missing")

        self.assertEqual(
            self.client.post(
                "/api/guardrail/agent/approvals",
                json={**action, "reason": "已确认备份和回滚窗口"},
            ).status_code,
            401,
        )
        self._login()
        issued = self.client.post(
            "/api/guardrail/agent/approvals",
            json={**action, "reason": "已确认备份和回滚窗口"},
        )
        self.assertEqual(issued.status_code, 200)
        token = issued.json()["approval_token"]

        allowed = self.client.post(
            "/api/guardrail/agent/check",
            json={**action, "approval_token": token},
        ).json()
        self.assertEqual(allowed["verdict"], "safe")
        self.assertEqual(allowed["approval"]["status"], "valid")
        self.assertEqual(allowed["risk_code"], "AGENT-ALLOW-APPROVED")

        replay = self.client.post(
            "/api/guardrail/agent/check",
            json={**action, "approval_token": token},
        ).json()
        self.assertEqual(replay["verdict"], "unsafe")
        self.assertEqual(replay["approval"]["status"], "replayed")

    def test_mismatch_fails_closed_without_consuming_original_approval(self):
        self._login()
        action = self._dangerous_action()
        token = self.client.post(
            "/api/guardrail/agent/approvals",
            json={**action, "reason": "变更单已审批"},
        ).json()["approval_token"]
        mismatch = self.client.post(
            "/api/guardrail/agent/check",
            json={
                **action,
                "resource": "prod://customers",
                "approval_token": token,
            },
        ).json()
        self.assertEqual(mismatch["verdict"], "unsafe")
        self.assertEqual(mismatch["approval"]["status"], "mismatch")

        original = self.client.post(
            "/api/guardrail/agent/check",
            json={**action, "approval_token": token},
        ).json()
        self.assertEqual(original["verdict"], "safe")
        self.assertEqual(original["approval"]["status"], "valid")

    def test_irreversible_root_action_cannot_be_approved(self):
        self._login()
        action = {
            "tool_name": "shell.exec",
            "resource": "/",
            "arguments": {"command": "rm -rf /"},
        }
        blocked = self.client.post("/api/guardrail/agent/check", json=action).json()
        self.assertEqual(blocked["verdict"], "unsafe")
        self.assertEqual(blocked["risk_code"], "AGENT-BLOCK-IRREVERSIBLE")
        approval = self.client.post(
            "/api/guardrail/agent/approvals",
            json={**action, "reason": "不应签发"},
        )
        self.assertEqual(approval.status_code, 400)

    def test_sensitive_arguments_are_encrypted_not_logged_in_plaintext(self):
        secret = "plain-agent-secret-should-not-leak"
        response = self.client.post(
            "/api/guardrail/agent/check",
            json={
                "tool_name": "credential.read",
                "resource": "vault://service-a",
                "arguments": {"password": secret},
            },
        )
        self.assertEqual(response.status_code, 200)
        event = audit_log_service.get_event(response.json()["audit_event_id"])
        self.assertNotIn(secret, str(event))
        self.assertNotIn(secret.encode(), Path(config.AUDIT_LOG_DB_PATH).read_bytes())
        evidence = audit_log_service.get_evidence(response.json()["audit_event_id"])
        self.assertIn(secret, evidence["prompt"])
        self.assertTrue(evidence["encrypted_at_rest"])

    def test_external_api_requires_dedicated_scope_and_records_usage(self):
        insufficient = api_access_service.issue_key(
            tenant_id="tenant-a",
            name="no-agent",
            scopes=["guardrail:check"],
        )
        denied = self.client.post(
            "/api/v1/guardrail/agent/check",
            headers={"X-API-Key": insufficient["key"]},
            json={
                "tool_name": "knowledge.search",
                "resource": "kb://redline",
                "arguments": {},
            },
        )
        self.assertEqual(denied.status_code, 403)

        issued = api_access_service.issue_key(
            tenant_id="tenant-agent",
            name="agent-gateway",
            scopes=["guardrail:agent"],
        )
        allowed = self.client.post(
            "/api/v1/guardrail/agent/check",
            headers={"Authorization": f"Bearer {issued['key']}"},
            json={
                "tool_name": "knowledge.search",
                "resource": "kb://redline",
                "arguments": {"query": "规则"},
            },
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["data"]["verdict"], "safe")
        usage = api_access_service.usage(api_access_service.authenticate(issued["key"]))
        self.assertEqual(usage["by_operation"][0]["operation"], "guardrail.agent_check")


if __name__ == "__main__":
    unittest.main()
