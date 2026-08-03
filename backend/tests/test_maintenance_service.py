"""Tests for online backup manifests and non-destructive maintenance."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from services import api_access_service, audit_log_service, maintenance_service, tenant_artifact_service


class MaintenanceServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.patch = patch.multiple(
            config,
            API_KEY_DB_PATH=str(root / "api.db"),
            API_KEY_HASH_SECRET="maintenance-secret",
            API_KEY_HASH_PREVIOUS_SECRET="",
            AUDIT_LOG_DB_PATH=str(root / "audit.db"),
            AUDIT_CONTENT_KEY="maintenance-evidence-key",
            AUDIT_CONTENT_PREVIOUS_KEY="",
            AUDIT_STORE_RAW_CONTENT=True,
            AUDIT_ARCHIVE_PATH=str(root / "archives"),
        )
        self.patch.start()
        api_access_service.reset_for_tests()
        audit_log_service.reset_for_tests()
        tenant_artifact_service.reset_for_tests()

    def tearDown(self):
        api_access_service.reset_for_tests()
        audit_log_service.reset_for_tests()
        tenant_artifact_service.reset_for_tests()
        self.patch.stop()
        self.temp_dir.cleanup()

    def test_online_backup_manifest_and_verify(self):
        event_id = audit_log_service.record(
            event_type="system.test", module="system", action="backup", summary="备份测试"
        )
        audit_log_service.store_evidence(event_id, prompt="保留原文", dangerous=True)
        disagreement_id = audit_log_service.record(
            event_type="guardrail.check",
            module="guardrail",
            action="check_prompt",
            outcome="allowed",
            summary="影子分歧",
            metadata={
                "shadow_evaluation": {
                    "status": "ok",
                    "decision": "fail",
                    "agreement": False,
                }
            },
        )
        audit_log_service.store_evidence(disagreement_id, prompt="复核样本")
        audit_log_service.resolve_shadow_review(disagreement_id, "safe", "operator")
        api_access_service.issue_key(
            tenant_id="tenant-a", name="backup-test", scopes=["usage:read"]
        )
        backup = maintenance_service.create_backup(label="unit-test")
        self.assertTrue(backup["audit_chain_valid"])
        self.assertEqual(backup["counts"]["audit_evidence"], 2)
        self.assertEqual(backup["counts"]["guardrail_shadow_reviews"], 1)
        verified = maintenance_service.verify_backup(backup["archive"])
        self.assertTrue(verified["valid"])
        self.assertTrue((Path(backup["path"]) / "audit.db").is_file())


if __name__ == "__main__":
    unittest.main()
