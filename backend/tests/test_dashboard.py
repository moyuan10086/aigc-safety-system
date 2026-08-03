"""Tests for real dashboard aggregation and access control."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from routers.audit import router as audit_router
from routers.dashboard import router as dashboard_router
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
        app.include_router(audit_router)
        app.include_router(dashboard_router)
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
        blocked = self.client.put(
            f"/api/dashboard/shadow-reviews/{disagreement_id}",
            json={"review_label": "safe"},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["detail"], "请先领取该复核样本")
        self.assertEqual(
            self.client.get(f"/api/audit/logs/{disagreement_id}/evidence").status_code,
            200,
        )
        claim = self.client.post(f"/api/dashboard/review-claims/{disagreement_id}")
        self.assertEqual(claim.status_code, 200)
        self.assertEqual(claim.json()["lease_seconds"], 900)
        claimed_overview = self.client.get("/api/dashboard/overview?hours=24").json()
        self.assertEqual(claimed_overview["shadow_reviews"][0]["claim_state"], "mine")
        self.assertFalse(claimed_overview["shadow_reviews"][0]["evidence_reviewed"])
        self.assertEqual(claimed_overview["shadow_evaluation"]["claimed_by_me_count"], 1)
        stale_evidence = self.client.put(
            f"/api/dashboard/shadow-reviews/{disagreement_id}",
            json={"review_label": "safe"},
        )
        self.assertEqual(stale_evidence.status_code, 409)
        self.assertIn("查看原始证据", stale_evidence.json()["detail"])
        evidence_response = self.client.get(f"/api/audit/logs/{disagreement_id}/evidence")
        self.assertEqual(evidence_response.status_code, 200)
        response = self.client.put(
            f"/api/dashboard/shadow-reviews/{disagreement_id}",
            json={"review_label": "safe"},
        )
        self.assertEqual(response.status_code, 200)
        review = response.json()
        self.assertEqual(review["reason_code"], "shadow_false_positive")
        self.assertIsNone(review["next_event_id"])
        self.assertNotIn("prompt", response.text.lower())

        immutable = self.client.put(
            f"/api/dashboard/shadow-reviews/{disagreement_id}",
            json={"review_label": "unsafe"},
        )
        self.assertEqual(immutable.status_code, 409)
        self.assertIn("标签不可覆盖", immutable.json()["detail"])

        overview = self.client.get("/api/dashboard/overview?hours=24").json()
        self.assertEqual(overview["shadow_evaluation"]["pending_reviews"], 0)
        self.assertEqual(overview["shadow_evaluation"]["reviewed_count"], 1)
        self.assertEqual(overview["shadow_evaluation"]["reviewer_reviewed_count"], 1)
        self.assertEqual(overview["shadow_reviews"][0]["review_label"], "safe")
        self.assertTrue(overview["shadow_reviews"][0]["evidence_reviewed"])
        evidence = audit_log_service.get_evidence(disagreement_id)
        self.assertEqual(evidence["prompt"], "结构化复核测试原文")
        access_events = audit_log_service.export_events(event_type="audit.evidence_access")
        claim_events = audit_log_service.export_events(event_type="guardrail.review_claim")
        review_events = audit_log_service.export_events(event_type="guardrail.shadow_review")
        self.assertEqual(len(access_events), 2)
        self.assertEqual(len(claim_events), 1)
        self.assertEqual(len(review_events), 1)
        self.assertEqual(review_events[0]["prev_hash"], access_events[0]["record_hash"])

    def test_general_evidence_sample_can_be_reviewed_and_disagreement_stays_first(self):
        _, disagreement_id = self._seed()
        general_id = audit_log_service.record(
            event_type="guardrail.check",
            module="guardrail",
            action="check_prompt",
            outcome="blocked",
            summary="普通危险样本",
            content_hash="b" * 64,
            metadata={"categories": ["cyber_abuse"]},
        )
        audit_log_service.store_evidence(
            general_id,
            prompt="这是不能出现在概览或导出里的原始提示词",
            response="这是不能出现在概览或导出里的危险模型输出",
            dangerous=True,
        )
        no_evidence_id = audit_log_service.record(
            event_type="guardrail.check",
            module="guardrail",
            action="check_prompt",
            outcome="allowed",
            summary="无证据事件",
        )
        token = auth_service.create_session(auth_service.current_user())
        self.client.cookies.set("aigc_operator_session", token)

        overview = self.client.get("/api/dashboard/overview?hours=24").json()
        self.assertEqual(overview["shadow_reviews"][0]["event_id"], disagreement_id)
        self.assertTrue(overview["shadow_reviews"][0]["is_disagreement"])
        self.assertEqual(overview["shadow_evaluation"]["eligible_samples"], 2)
        self.assertEqual(overview["shadow_evaluation"]["target_labels"], 200)
        self.assertFalse(next(item for item in overview["shadow_reviews"] if item["event_id"] == general_id)["evidence_reviewed"])

        blocked = self.client.put(
            f"/api/dashboard/shadow-reviews/{general_id}",
            json={"review_label": "unsafe"},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(self.client.post(f"/api/dashboard/review-claims/{general_id}").status_code, 200)
        with self.assertRaises(PermissionError):
            audit_log_service.claim_review_sample(general_id, "another-operator")
        self.assertEqual(self.client.get(f"/api/audit/logs/{general_id}/evidence").status_code, 200)
        with self.assertRaises(PermissionError):
            audit_log_service.resolve_shadow_review(general_id, "unsafe", "another-operator")
        other_operator_view = audit_log_service.shadow_review_statistics(
            reviewer="another-operator"
        )
        self.assertFalse(
            next(item for item in other_operator_view["queue"] if item["event_id"] == general_id)[
                "evidence_reviewed"
            ]
        )
        reviewed = self.client.put(
            f"/api/dashboard/shadow-reviews/{general_id}",
            json={"review_label": "unsafe"},
        )
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.json()["reason_code"], "human_confirmed_unsafe")
        self.assertEqual(reviewed.json()["next_event_id"], disagreement_id)
        next_overview = self.client.get("/api/dashboard/overview?hours=24").json()
        self.assertEqual(next_overview["shadow_reviews"][0]["event_id"], disagreement_id)
        self.assertEqual(next_overview["shadow_reviews"][0]["claim_state"], "mine")
        rejected = self.client.put(
            f"/api/dashboard/shadow-reviews/{no_evidence_id}",
            json={"review_label": "safe"},
        )
        self.assertEqual(rejected.status_code, 404)

        exported = self.client.get("/api/dashboard/review-labels.csv")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("human_label", exported.text.splitlines()[0])
        self.assertIn("review_claim_verified", exported.text.splitlines()[0])
        self.assertIn("evidence_access_verified", exported.text.splitlines()[0])
        self.assertIn(general_id, exported.text)
        self.assertIn(",True\r", exported.text)
        self.assertNotIn("这是不能出现在概览或导出里的原始提示词", exported.text)
        self.assertNotIn("这是不能出现在概览或导出里的危险模型输出", exported.text)
        self.assertTrue(audit_log_service.verify_chain())

    def test_expired_claim_can_be_taken_over_without_exposing_evidence(self):
        _, disagreement_id = self._seed()
        started = datetime.now(timezone.utc) - timedelta(seconds=100)
        first = audit_log_service.claim_review_sample(
            disagreement_id, "operator", now=started, lease_seconds=60
        )
        self.assertEqual(first["reviewer"], "operator")
        with self.assertRaises(PermissionError):
            audit_log_service.claim_review_sample(
                disagreement_id,
                "another-operator",
                now=started + timedelta(seconds=30),
                lease_seconds=60,
            )
        takeover = audit_log_service.claim_review_sample(
            disagreement_id,
            "another-operator",
            now=started + timedelta(seconds=61),
            lease_seconds=60,
        )
        self.assertEqual(takeover["reviewer"], "another-operator")
        audit_log_service.record(
            event_type="audit.evidence_access",
            module="audit",
            action="reveal_raw_evidence",
            outcome="success",
            actor="another-operator",
            resource_id=disagreement_id,
            summary="未形成领取审计事件的直接服务测试",
        )
        with self.assertRaises(PermissionError) as missing_claim_audit:
            audit_log_service.resolve_shadow_review(
                disagreement_id, "safe", "another-operator"
            )
        self.assertEqual(str(missing_claim_audit.exception), "review_claim_audit_required")
        overview = audit_log_service.shadow_review_statistics(
            reviewer="operator", now=datetime.now(timezone.utc)
        )
        self.assertEqual(overview["queue"][0]["claim_state"], "other")


if __name__ == "__main__":
    unittest.main()
