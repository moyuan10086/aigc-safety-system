"""Tenant isolation and lifecycle tests for external scan/report contracts."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from routers.api_v1 import router as api_v1_router
from services import api_access_service, audit_log_service, auth_service, tenant_artifact_service


class TenantArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.config = patch.multiple(
            config,
            API_KEY_DB_PATH=str(root / "api_keys.db"),
            API_KEY_HASH_SECRET="test-api-key-hash-secret",
            API_KEY_DEFAULT_RATE_LIMIT=60,
            API_KEY_DEFAULT_DAILY_QUOTA=5000,
            API_KEY_MAX_RATE_LIMIT=600,
            API_KEY_MAX_DAILY_QUOTA=100000,
            API_SCAN_MAX_CONCURRENCY=1,
            API_SCAN_MAX_ACTIVE_PER_KEY=1,
            AUDIT_LOG_DB_PATH=str(root / "audit.db"),
            AUDIT_STORE_RAW_CONTENT=True,
            AUDIT_CONTENT_KEY="test-evidence-key",
            AUTH_USERNAME="operator",
            AUTH_DISPLAY_NAME="审核员",
            AUTH_ROLE="operator",
            AUTH_PASSWORD_HASH=auth_service.hash_password("test-password", iterations=100_000),
            AUTH_SESSION_SECRET="test-session-secret-with-enough-entropy",
            AUTH_SESSION_TTL_SECONDS=3600,
            AUTH_COOKIE_SECURE=False,
        )
        self.config.start()
        api_access_service.reset_for_tests()
        audit_log_service.reset_for_tests()
        tenant_artifact_service.reset_for_tests()
        app = FastAPI()
        app.include_router(api_v1_router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        api_access_service.reset_for_tests()
        audit_log_service.reset_for_tests()
        tenant_artifact_service.reset_for_tests()
        self.config.stop()
        self.temp_dir.cleanup()

    def _issue(self, tenant: str, name: str):
        return api_access_service.issue_key(
            tenant_id=tenant,
            name=name,
            scopes=["scan:run", "scan:read", "report:write", "report:read"],
            rate_limit_per_minute=60,
            daily_quota=100,
        )

    def test_scan_is_async_and_report_is_key_isolated(self):
        owner = self._issue("tenant-a", "A")
        other = self._issue("tenant-b", "B")
        headers = {"X-API-Key": owner["key"]}
        with patch.object(tenant_artifact_service._EXECUTOR, "submit"):
            response = self.client.post("/api/v1/scans", headers=headers, json={"preset": "quick"})
        self.assertEqual(response.status_code, 202)
        scan_id = response.json()["data"]["scan_id"]
        self.assertEqual(response.json()["data"]["status"], "queued")

        with patch.object(tenant_artifact_service, "_run_garak_scan", return_value=[
            {"name": "Bullying", "passed": 2, "failed": 1, "errors": 0, "total": 3}
        ]):
            tenant_artifact_service._execute_scan(scan_id)

        completed = self.client.get(f"/api/v1/scans/{scan_id}", headers=headers)
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["data"]["status"], "completed")

        report = self.client.post(
            "/api/v1/reports",
            headers=headers,
            json={"scan_id": scan_id, "title": "现场扫描"},
        )
        self.assertEqual(report.status_code, 200)
        report_id = report.json()["data"]["report_id"]
        self.assertEqual(report.json()["data"]["payload"]["scan"]["result"]["real_execution"], True)
        self.assertNotIn("prompt", report.text)
        self.assertNotIn("response", report.text)

        forbidden = self.client.get(f"/api/v1/reports/{report_id}", headers={"X-API-Key": other["key"]})
        self.assertEqual(forbidden.status_code, 404)
        download = self.client.get(f"/api/v1/reports/{report_id}/download", headers=headers)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.headers["cache-control"], "no-store")
        self.assertEqual(download.json()["source"]["id"], scan_id)

    def test_active_scan_limit_and_invalid_preset(self):
        owner = self._issue("tenant-a", "A")
        headers = {"X-API-Key": owner["key"]}
        with patch.object(tenant_artifact_service._EXECUTOR, "submit"):
            first = self.client.post("/api/v1/scans", headers=headers, json={"preset": "quick"})
            second = self.client.post("/api/v1/scans", headers=headers, json={"preset": "standard"})
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["detail"]["code"], "SCAN_CONCURRENCY_LIMIT")
        invalid = self.client.post("/api/v1/scans", headers=headers, json={"preset": "full"})
        self.assertEqual(invalid.status_code, 422)


if __name__ == "__main__":
    unittest.main()
