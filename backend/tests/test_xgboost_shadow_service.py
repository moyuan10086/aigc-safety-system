"""Tests for the fail-open XGBoost shadow evaluator."""

import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services import xgboost_shadow_service


class XGBoostShadowServiceTests(unittest.TestCase):
    def setUp(self):
        xgboost_shadow_service.reset_for_tests()

    def tearDown(self):
        xgboost_shadow_service.reset_for_tests()

    def test_disabled_path_is_explicit(self):
        with patch.object(
            xgboost_shadow_service.config, "GUARDRAIL_ENABLE_XGBOOST_SHADOW", False
        ):
            result = xgboost_shadow_service.evaluate("普通内容", "safe")
        self.assertEqual(result["status"], "disabled")
        self.assertIsNone(result["decision"])

    def test_shadow_result_does_not_replace_primary_verdict(self):
        fake = SimpleNamespace(
            audit_dict=lambda _text: {
                "decision": "fail",
                "confidence": 0.93,
                "alert": False,
                "risk_type": "prompt_injection",
                "route": "local",
            }
        )
        with patch.object(
            xgboost_shadow_service.config, "GUARDRAIL_ENABLE_XGBOOST_SHADOW", True
        ), patch.object(
            xgboost_shadow_service.config,
            "GUARDRAIL_XGBOOST_SHADOW_SHA256",
            "a" * 64,
        ), patch.object(xgboost_shadow_service, "_get_auditor", return_value=fake):
            result = xgboost_shadow_service.evaluate("普通内容", "safe")
        self.assertEqual(result["decision"], "fail")
        self.assertFalse(result["agreement"])
        self.assertEqual(result["status"], "ok")

    def test_digest_mismatch_fails_closed_for_artifact_and_open_for_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "model.json"
            model.write_text("trusted model fixture", encoding="utf-8")
            with patch.object(
                xgboost_shadow_service.config, "GUARDRAIL_ENABLE_XGBOOST_SHADOW", True
            ), patch.object(
                xgboost_shadow_service.config,
                "GUARDRAIL_XGBOOST_SHADOW_MODULE_PATH",
                str(root),
            ), patch.object(
                xgboost_shadow_service.config,
                "GUARDRAIL_XGBOOST_SHADOW_MODEL_PATH",
                str(model),
            ), patch.object(
                xgboost_shadow_service.config,
                "GUARDRAIL_XGBOOST_SHADOW_SHA256",
                "0" * 64,
            ):
                result = xgboost_shadow_service.evaluate("审核文本", "unsafe")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["error_code"], "model_digest_mismatch")

    def test_warmup_does_not_block_requests(self):
        def slow_load():
            time.sleep(0.2)
            return SimpleNamespace(audit_dict=lambda _text: {"decision": "pass"})

        with patch.object(
            xgboost_shadow_service.config, "GUARDRAIL_ENABLE_XGBOOST_SHADOW", True
        ), patch.object(xgboost_shadow_service, "_create_auditor", side_effect=slow_load):
            xgboost_shadow_service.start_warmup()
            started = time.perf_counter()
            result = xgboost_shadow_service.evaluate("普通内容", "safe")
            elapsed = time.perf_counter() - started
            time.sleep(0.25)
        self.assertEqual(result["status"], "warming")
        self.assertLess(elapsed, 0.1)


if __name__ == "__main__":
    unittest.main()
