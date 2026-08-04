"""Tests for tenant API keys, quotas and the versioned external API."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from routers.api_v1 import router as api_v1_router
from routers.auth import router as auth_router
from services import api_access_service, audit_log_service, auth_service, guardrail_service


SAFE_RESULT = {
    "verdict": "safe",
    "decision": "allow",
    "risk_level": "low",
    "risk_score": 0.02,
    "intent": "normal",
    "categories": [],
    "evidence": [],
    "actions": ["allow"],
    "checks": [],
    "risk_code": "SAFE",
    "action": "allow",
    "redline_answer": "",
    "scores": {"rules": 0.0},
    "engine": {"name": "test"},
}


class ApiAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.password = "Api-Admin-2026"
        self.config = patch.multiple(
            config,
            API_KEY_DB_PATH=str(root / "api_keys.db"),
            API_KEY_HASH_SECRET="test-api-key-hash-secret",
            API_KEY_DEFAULT_RATE_LIMIT=60,
            API_KEY_DEFAULT_DAILY_QUOTA=5000,
            API_KEY_MAX_RATE_LIMIT=600,
            API_KEY_MAX_DAILY_QUOTA=100000,
            AUDIT_LOG_DB_PATH=str(root / "audit.db"),
            AUDIT_STORE_RAW_CONTENT=True,
            AUDIT_CONTENT_KEY="test-evidence-key",
            AUTH_USERNAME="operator",
            AUTH_DISPLAY_NAME="审核员",
            AUTH_ROLE="operator",
            AUTH_PASSWORD_HASH=auth_service.hash_password(self.password, iterations=100_000),
            AUTH_SESSION_SECRET="test-session-secret-with-enough-entropy",
            AUTH_SESSION_TTL_SECONDS=3600,
            AUTH_COOKIE_SECURE=False,
        )
        self.config.start()
        api_access_service.reset_for_tests()
        audit_log_service.reset_for_tests()
        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(api_v1_router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        api_access_service.reset_for_tests()
        audit_log_service.reset_for_tests()
        self.config.stop()
        self.temp_dir.cleanup()

    def _issue(self, **overrides):
        values = {
            "tenant_id": "competition-demo",
            "name": "现场演示客户端",
            "scopes": ["guardrail:check", "usage:read"],
            "rate_limit_per_minute": 20,
            "daily_quota": 100,
        }
        values.update(overrides)
        return api_access_service.issue_key(**values)

    def test_plaintext_key_is_returned_once_and_never_stored(self):
        issued = self._issue()
        raw_key = issued["key"]
        self.assertTrue(raw_key.startswith(f"{issued['key_prefix']}_"))
        self.assertEqual(api_access_service.authenticate(raw_key)["tenant_id"], "competition-demo")

        with closing(sqlite3.connect(config.API_KEY_DB_PATH)) as connection:
            row = connection.execute("SELECT key_hash, key_prefix FROM api_keys").fetchone()
        self.assertNotEqual(row[0], raw_key)
        self.assertNotIn(raw_key, Path(config.API_KEY_DB_PATH).read_bytes().decode("latin1"))
        self.assertEqual(row[1], issued["key_prefix"])

        listed = api_access_service.list_keys()
        self.assertNotIn("key", listed[0])
        self.assertNotIn("key_hash", listed[0])

    def test_v1_requires_key_enforces_scope_and_records_tenant_usage(self):
        self.assertEqual(self.client.post("/api/v1/guardrail/check", json={"prompt": "hello"}).status_code, 401)

        insufficient = self._issue(scopes=["usage:read"])
        denied = self.client.post(
            "/api/v1/guardrail/check",
            headers={"X-API-Key": insufficient["key"]},
            json={"prompt": "hello"},
        )
        self.assertEqual(denied.status_code, 403)

        issued = self._issue(tenant_id="tenant-a")
        with patch.object(guardrail_service, "check", return_value=SAFE_RESULT):
            response = self.client.post(
                "/api/v1/guardrail/check",
                headers={"Authorization": f"Bearer {issued['key']}"},
                json={"prompt": "正常的产品咨询"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["api_version"], "v1")
        self.assertEqual(payload["data"]["risk_code"], "SAFE")

        authenticated = api_access_service.authenticate(issued["key"])
        initial_usage = api_access_service.usage(authenticated)
        synthetic_latency_ms = initial_usage["totals"]["p95_latency_ms"] + 400
        api_access_service.record_usage(
            authenticated,
            operation="guardrail.check",
            status_code=500,
            latency_ms=synthetic_latency_ms,
        )
        usage = api_access_service.usage(authenticated)
        self.assertEqual(usage["tenant_id"], "tenant-a")
        self.assertEqual(usage["totals"]["requests"], 2)
        self.assertEqual(usage["totals"]["failure_rate"], 50.0)
        self.assertEqual(usage["totals"]["p95_latency_ms"], synthetic_latency_ms)
        self.assertEqual(usage["by_operation"][0]["operation"], "guardrail.check")
        operator_usage = api_access_service.operator_usage(days=7, tenant_id="tenant-a")
        self.assertEqual(operator_usage["totals"]["tenants"], 1)
        self.assertEqual(operator_usage["totals"]["failure_rate"], 50.0)
        self.assertEqual(operator_usage["totals"]["p95_latency_ms"], synthetic_latency_ms)
        self.assertEqual(operator_usage["by_tenant"][0]["tenant_id"], "tenant-a")
        self.assertEqual(operator_usage["by_key"][0]["key_id"], issued["key_id"])

    def test_rate_limit_daily_quota_and_revocation(self):
        rate_key = self._issue(scopes=["usage:read"], rate_limit_per_minute=1)
        headers = {"X-API-Key": rate_key["key"]}
        self.assertEqual(self.client.get("/api/v1/catalog", headers=headers).status_code, 200)
        limited = self.client.get("/api/v1/catalog", headers=headers)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["detail"]["code"], "API_RATE_LIMITED")

        quota_key = self._issue(scopes=["usage:read"], rate_limit_per_minute=20, daily_quota=1)
        quota_headers = {"X-API-Key": quota_key["key"]}
        self.assertEqual(self.client.get("/api/v1/catalog", headers=quota_headers).status_code, 200)
        exhausted = self.client.get("/api/v1/catalog", headers=quota_headers)
        self.assertEqual(exhausted.status_code, 429)
        self.assertEqual(exhausted.json()["detail"]["code"], "API_DAILY_QUOTA_EXCEEDED")

        self.assertTrue(api_access_service.revoke_key(quota_key["key_id"]))
        self.assertIsNone(api_access_service.authenticate(quota_key["key"]))

    def test_operator_can_issue_list_and_revoke_without_key_disclosure(self):
        login = self.client.post(
            "/api/auth/login",
            json={"username": "operator", "password": self.password},
        )
        self.assertEqual(login.status_code, 200)
        create = self.client.post(
            "/api/auth/api-keys",
            json={
                "tenant_id": "partner-01",
                "name": "合作方测试",
                "scopes": ["guardrail:check", "usage:read"],
                "rate_limit_per_minute": 30,
                "daily_quota": 500,
            },
        )
        self.assertEqual(create.status_code, 200)
        issued = create.json()
        self.assertIn("key", issued)

        listed = self.client.get("/api/auth/api-keys").json()["items"]
        self.assertEqual(len(listed), 1)
        self.assertNotIn("key", listed[0])
        self.assertNotIn("key_hash", listed[0])
        self.assertEqual(self.client.get("/api/auth/api-usage?days=7").status_code, 200)

        revoked = self.client.delete(f"/api/auth/api-keys/{issued['key_id']}")
        self.assertEqual(revoked.status_code, 200)
        self.assertIsNone(api_access_service.authenticate(issued["key"]))

    def test_hash_secret_rotation_keeps_existing_key_during_grace_window(self):
        issued = self._issue()
        old_secret = config.API_KEY_HASH_SECRET
        config.API_KEY_HASH_SECRET = "new-api-key-hash-secret"
        config.API_KEY_HASH_PREVIOUS_SECRET = old_secret
        self.assertEqual(api_access_service.authenticate(issued["key"])["key_id"], issued["key_id"])
        config.API_KEY_HASH_PREVIOUS_SECRET = ""
        self.assertEqual(api_access_service.authenticate(issued["key"])["key_id"], issued["key_id"])

    def test_image_content_safety_api_requires_scope_and_returns_normalized_result(self):
        fixture = Path(__file__).parents[2] / "docs" / "evidence" / "c2pa-fixtures" / "c2pa-rs-update-manifest.jpg"
        denied = self._issue(scopes=["usage:read"])
        response = self.client.post(
            "/api/v1/images/content-safety",
            headers={"X-API-Key": denied["key"]},
            files={"image": (fixture.name, fixture.read_bytes(), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 403)

        result = {
            "verdict": "review", "safe": False, "risk_score": 0.95,
            "categories": [{"code": "weapon_display", "label": "疑似武器展示", "confidence": 0.95}],
            "summary": "可见武器展示", "policy_version": "image-safety-v1",
        }
        issued = self._issue(scopes=["image:content-safety"])
        with patch("services.mllm_service.analyze_content_safety", return_value=result):
            response = self.client.post(
                "/api/v1/images/content-safety",
                headers={"Authorization": f"Bearer {issued['key']}"},
                files={"image": (fixture.name, fixture.read_bytes(), "image/jpeg")},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["api_version"], "v1")
        self.assertEqual(payload["data"], result)

    def test_provenance_external_api_requires_scope_and_returns_safe_summary(self):
        fixture = Path(__file__).parents[2] / "docs" / "evidence" / "c2pa-fixtures" / "c2pa-rs-update-manifest.jpg"
        denied = self._issue(scopes=["usage:read"])
        response = self.client.post(
            "/api/v1/images/provenance/verify",
            headers={"Authorization": f"Bearer {denied['key']}"},
            files={"image": (fixture.name, fixture.read_bytes(), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 403)

        issued = self._issue(scopes=["image:provenance"])
        response = self.client.post(
            "/api/v1/images/provenance/verify",
            headers={"X-API-Key": issued["key"]},
            files={"image": (fixture.name, fixture.read_bytes(), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["api_version"], "v1")
        self.assertEqual(payload["data"]["overall_state"], "confirmed_source")
        self.assertEqual(payload["data"]["source_evidence"]["content_credentials"]["status"], "valid")
        self.assertFalse(payload["data"]["audit_evidence"]["raw_image_retained"])
        self.assertNotIn("manifest_bytes", str(payload))


if __name__ == "__main__":
    unittest.main()
