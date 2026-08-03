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
        event_id = audit_log_service.record(
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
        disagreement_id = audit_log_service.record(
            event_type="guardrail.check",
            module="guardrail",
            action="check_prompt",
            outcome="allowed",
            client_ip="203.0.113.11",
            summary="护栏判定：GR-ALLOW",
            risk_code="GR-ALLOW",
            risk_score=0.0,
            content_hash="a" * 64,
            metadata={
                "categories": [],
                "shadow_evaluation": {
                    "status": "ok",
                    "decision": "fail",
                    "confidence": 0.72,
                    "alert": True,
                    "agreement": False,
                    "latency_ms": 11.25,
                    "risk_type": "unknown_risk",
                },
            },
        )
        audit_log_service.store_evidence(disagreement_id, prompt="结构化复核测试原文")
        return event_id, disagreement_id

    def test_dashboard_requires_operator_and_returns_safe_aggregates(self):
        _, disagreement_id = self._seed()
        self.assertEqual(self.client.get("/api/dashboard/overview").status_code, 401)
        token = auth_service.create_session(auth_service.current_user())
        self.client.cookies.set("aigc_operator_session", token)
        response = self.client.get("/api/dashboard/overview?hours=24")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        data = response.json()
        self.assertEqual(data["summary"]["total_events"], 3)
        self.assertEqual(data["summary"]["blocked"], 1)
        self.assertEqual(data["summary"]["p95_latency_ms"], 400)
        self.assertEqual(data["summary"]["unique_clients"], 2)
        self.assertEqual(data["risk_distribution"][0], {"name": "cyber_abuse", "value": 1})
        self.assertTrue(data["timeline"])
        self.assertFalse(data["privacy"]["raw_content_included"])
        self.assertNotIn("prompt", response.text.lower())
        self.assertEqual(data["shadow_evaluation"]["disagreement_count"], 1)
        self.assertEqual(data["shadow_evaluation"]["false_positive_candidates"], 1)
        self.assertEqual(data["shadow_evaluation"]["pending_reviews"], 1)
        self.assertEqual(data["shadow_reviews"][0]["event_id"], disagreement_id)
        self.assertNotIn("结构化复核测试原文", response.text)

    def test_operator_resolves_shadow_disagreement_with_structured_label(self):
        _, disagreement_id = self._seed()
        self.assertEqual(
            self.client.put(
                f"/api/dashboard/shadow-reviews/{disagreement_id}",
                json={"review_label": "safe"},
            ).status_code,
            401,
        )
        token = auth_service.create_session(auth_service.current_user())
        self.client.cookies.set("aigc_operator_session", token)
        response = self.client.put(
            f"/api/dashboard/shadow-reviews/{disagreement_id}",
            json={"review_label": "safe"},
        )
        self.assertEqual(response.status_code, 200)
        review = response.json()
        self.assertEqual(review["reason_code"], "shadow_false_positive")
        self.assertNotIn("prompt", response.text.lower())

        overview = self.client.get("/api/dashboard/overview?hours=24").json()
        self.assertEqual(overview["shadow_evaluation"]["pending_reviews"], 0)
        self.assertEqual(overview["shadow_evaluation"]["reviewed_count"], 1)
        self.assertEqual(overview["shadow_reviews"][0]["review_label"], "safe")
        evidence = audit_log_service.get_evidence(disagreement_id)
        self.assertEqual(evidence["prompt"], "结构化复核测试原文")


if __name__ == "__main__":
    unittest.main()
