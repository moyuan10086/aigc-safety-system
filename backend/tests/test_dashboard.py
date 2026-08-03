"""Tests for real dashboard aggregation and access control."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from routers.dashboard import router
from services import audit_log_service, auth_service


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "audit.db"
        self.config_patch = patch.multiple(
            config,
            AUDIT_LOG_DB_PATH=str(self.db_path),
            AUDIT_LOG_RETENTION_DAYS=90,
            AUDIT_STORE_RAW_CONTENT=True,
            AUDIT_CONTENT_KEY="dashboard-test-key",
            AUTH_USERNAME="operator",
            AUTH_DISPLAY_NAME="审核员",
            AUTH_ROLE="operator",
            AUTH_PASSWORD_HASH=auth_service.hash_password("test-password", iterations=100_000),
            AUTH_SESSION_SECRET="dashboard-session-secret-with-enough-entropy",
            AUTH_SESSION_TTL_SECONDS=3600,
        )
        self.config_patch.start()
        audit_log_service.reset_for_tests()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        audit_log_service.reset_for_tests()
        self.config_patch.stop()
        self.temp_dir.cleanup()

    def _seed(self):
        audit_log_service.record(
            event_type="request.access",
            module="guardrail",
            action="api_request",
            outcome="success",
            client_ip="203.0.113.10",
            latency_ms=100,
            summary="POST /api/guardrail/check 返回 200",
        )
        audit_log_service.record(
            event_type="guardrail.chat",
            module="guardrail",
            action="guarded_model_generation",
            severity="high",
            outcome="blocked",
            client_ip="203.0.113.10",
            latency_ms=400,
            summary="输出已隔离",
            risk_code="GR-BLOCK",
            risk_score=0.93,
            metadata={"categories": ["cyber_abuse"]},
        )

    def test_dashboard_requires_operator_and_returns_safe_aggregates(self):
        self._seed()
        self.assertEqual(self.client.get("/api/dashboard/overview").status_code, 401)
        token = auth_service.create_session(auth_service.current_user())
        self.client.cookies.set("aigc_operator_session", token)
        response = self.client.get("/api/dashboard/overview?hours=24")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        data = response.json()
        self.assertEqual(data["summary"]["total_events"], 2)
        self.assertEqual(data["summary"]["blocked"], 1)
        self.assertEqual(data["summary"]["p95_latency_ms"], 400)
        self.assertEqual(data["summary"]["unique_clients"], 1)
        self.assertEqual(data["risk_distribution"][0], {"name": "cyber_abuse", "value": 1})
        self.assertTrue(data["timeline"])
        self.assertFalse(data["privacy"]["raw_content_included"])
        self.assertNotIn("prompt", response.text.lower())


if __name__ == "__main__":
    unittest.main()
