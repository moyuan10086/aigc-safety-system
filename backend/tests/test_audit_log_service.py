"""Tests for persistent audit filtering, integrity and encrypted evidence."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from routers.audit import router
from services import audit_log_service, auth_service


class AuditLogServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "audit.db"
        self.password = "Audit-Test-Password"
        self.config_patch = patch.multiple(
            config,
            AUDIT_LOG_DB_PATH=str(self.db_path),
            AUDIT_LOG_RETENTION_DAYS=90,
            AUDIT_STORE_RAW_CONTENT=True,
            AUDIT_CONTENT_KEY="test-audit-encryption-key",
            AUTH_USERNAME="operator",
            AUTH_DISPLAY_NAME="审核员",
            AUTH_ROLE="operator",
            AUTH_PASSWORD_HASH=auth_service.hash_password(self.password, iterations=100_000),
            AUTH_SESSION_SECRET="test-session-secret-with-enough-entropy",
            AUTH_SESSION_TTL_SECONDS=3600,
        )
        self.config_patch.start()
        audit_log_service.reset_for_tests()

    def tearDown(self):
        audit_log_service.reset_for_tests()
        self.config_patch.stop()
        self.temp_dir.cleanup()

    def test_records_filters_and_verifies_hash_chain(self):
        audit_log_service.record(
            event_type="request.access",
            module="system",
            action="api_request",
            summary="健康检查",
            client_ip="127.0.0.1",
        )
        audit_log_service.record(
            event_type="guardrail.chat",
            module="guardrail",
            action="guarded_model_generation",
            severity="high",
            outcome="blocked",
            summary="输出已隔离",
            risk_code="GR-BLOCK",
            risk_score=0.93,
        )

        result = audit_log_service.list_events(module="guardrail", page=1, page_size=10)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["risk_code"], "GR-BLOCK")
        stats = audit_log_service.statistics()
        self.assertEqual(stats["high_risk"], 1)
        self.assertEqual(stats["blocked"], 1)
        self.assertTrue(stats["chain_valid"])

    def test_raw_prompt_and_output_are_encrypted_at_rest(self):
        secret_prompt = "这是必须保留的原始提示词"
        dangerous_output = "这是被隔离的模型危险输出"
        event_id = audit_log_service.record(
            event_type="guardrail.chat",
            module="guardrail",
            action="guarded_model_generation",
            severity="high",
            outcome="blocked",
            summary="输出已隔离",
        )
        self.assertTrue(
            audit_log_service.store_evidence(
                event_id,
                prompt=secret_prompt,
                response=dangerous_output,
                dangerous=True,
            )
        )

        evidence = audit_log_service.get_evidence(event_id)
        self.assertEqual(evidence["prompt"], secret_prompt)
        self.assertEqual(evidence["response"], dangerous_output)
        self.assertTrue(evidence["encrypted_at_rest"])
        listed = audit_log_service.list_events(page=1, page_size=10)["items"][0]
        self.assertEqual(listed["has_evidence"], 1)

        with closing(sqlite3.connect(self.db_path)) as connection:
            ciphertext = connection.execute(
                "SELECT ciphertext FROM audit_evidence WHERE event_id = ?", (event_id,)
            ).fetchone()[0]
        self.assertNotIn(secret_prompt.encode("utf-8"), ciphertext)
        self.assertNotIn(dangerous_output.encode("utf-8"), ciphertext)

    def test_audit_endpoints_require_login_and_reveal_evidence(self):
        event_id = audit_log_service.record(
            event_type="guardrail.check",
            module="guardrail",
            action="check_prompt",
            summary="护栏判定",
        )
        audit_log_service.store_evidence(event_id, prompt="原始内容", dangerous=False)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        self.assertEqual(client.get("/api/audit/logs").status_code, 401)
        token = auth_service.create_session(auth_service.current_user())
        client.cookies.set("aigc_operator_session", token)
        response = client.get("/api/audit/logs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        reveal = client.get(f"/api/audit/logs/{event_id}/evidence")
        self.assertEqual(reveal.status_code, 200)
        self.assertEqual(reveal.json()["prompt"], "原始内容")
        self.assertEqual(reveal.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
