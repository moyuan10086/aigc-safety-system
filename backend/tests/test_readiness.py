"""Tests for competition-demo readiness and the guarded active probe."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from routers.system import router
from services import audit_log_service, auth_service, guarded_chat_service, readiness_service


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.audit_db = root / "audit.db"
        self.frontend_index = root / "frontend" / "index.html"
        self.frontend_index.parent.mkdir()
        self.frontend_index.write_text("<!doctype html>", encoding="utf-8")
        self.lexicon = root / "lexicon"
        self.lexicon.mkdir()
        self.rag = root / "rag"
        self.rag.mkdir()
        self.deepfake = root / "model.ckpt"
        self.deepfake.write_bytes(b"test-weights")
        self.config_patch = patch.multiple(
            config,
            AUDIT_LOG_DB_PATH=str(self.audit_db),
            AUDIT_LOG_RETENTION_DAYS=90,
            AUDIT_STORE_RAW_CONTENT=True,
            AUDIT_CONTENT_KEY="readiness-content-key",
            AUTH_USERNAME="operator",
            AUTH_DISPLAY_NAME="审核员",
            AUTH_ROLE="operator",
            AUTH_PASSWORD_HASH=auth_service.hash_password(
                "test-password", iterations=100_000
            ),
            AUTH_OPERATORS_JSON="",
            AUTH_SESSION_SECRET="readiness-session-secret-with-enough-entropy",
            AUTH_SESSION_TTL_SECONDS=3600,
            CHAT_MODEL_API_KEY="chat-secret",
            CHAT_MODEL_BASE_URL="https://model.invalid/v1",
            CHAT_MODEL_NAME="competition-chat",
            MLLM_API_KEY="mllm-secret",
            MLLM_BASE_URL="https://mllm.invalid/v1",
            MLLM_MODEL="competition-mllm",
            DEEPFAKE_MODEL_PATH=str(self.deepfake),
            CHROMA_PATH=str(self.rag),
            LEXICON_PATH=str(self.lexicon),
            GUARDRAIL_ENABLE_RAG=True,
            GUARDRAIL_ENABLE_QWEN_CLASSIFIER=True,
            GUARDRAIL_QWEN_API_KEY="qwen-secret",
            GUARDRAIL_QWEN_BASE_URL="https://qwen.invalid/v1",
            GUARDRAIL_QWEN_MODEL="qwen3guard-test",
            GUARDRAIL_ENABLE_SINGGUARD_CLASSIFIER=True,
            GUARDRAIL_SINGGUARD_API_KEY="singguard-secret",
            GUARDRAIL_SINGGUARD_BASE_URL="https://singguard.invalid/v1",
            GUARDRAIL_SINGGUARD_MODEL="singguard-test",
        )
        self.config_patch.start()
        self.path_patch = patch.multiple(
            readiness_service,
            FRONTEND_INDEX=self.frontend_index,
            BUNDLED_LEXICON=self.lexicon,
            DEEPFAKE_WEIGHTS=self.deepfake,
        )
        self.path_patch.start()
        self.face_patch = patch.object(
            readiness_service, "_face_detector_available", return_value=True
        )
        self.face_patch.start()
        audit_log_service.reset_for_tests()
        readiness_service.reset_for_tests()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        readiness_service.reset_for_tests()
        audit_log_service.reset_for_tests()
        self.face_patch.stop()
        self.path_patch.stop()
        self.config_patch.stop()
        self.temp_dir.cleanup()

    def _successful_guarded_run(self, prompt, max_tokens=None, evidence_capture=None):
        self.assertEqual(prompt, readiness_service.PROBE_PROMPT)
        self.assertEqual(max_tokens, 32)
        evidence_capture["model_output"] = "READY"
        components = {
            "rules": "ok",
            "rag": "ok",
            "mllm": "disabled",
            "qwen3guard": "ok",
            "singguard": "ok",
            "xgboost_shadow": "disabled",
        }
        return {
            "status": "completed",
            "model_called": True,
            "response": "READY",
            "quarantined": False,
            "input_guard": {
                "verdict": "safe",
                "engine": {"components": components},
            },
            "output_guard": {
                "verdict": "safe",
                "engine": {"components": components},
            },
            "final_guard": {"verdict": "safe"},
            "generation": {
                "called": True,
                "model": "competition-chat",
                "latency_ms": 12.5,
            },
        }

    def test_passive_snapshot_is_ready_and_exposes_only_safe_metadata(self):
        result = readiness_service.snapshot(refresh=True)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["summary"]["required_failed"], 0)
        self.assertTrue(all(item["status"] == "ready" for item in result["scenarios"]))
        self.assertEqual(
            result["privacy"],
            {
                "secrets_exposed": False,
                "paths_exposed": False,
                "raw_content_included": False,
            },
        )
        serialized = json.dumps(result, ensure_ascii=False)
        for forbidden in (
            "chat-secret",
            "mllm-secret",
            "qwen-secret",
            "singguard-secret",
            str(self.temp_dir.name),
            "https://model.invalid",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_optional_models_degrade_without_claiming_required_failure(self):
        with patch.multiple(
            config,
            CHAT_MODEL_API_KEY="",
            MLLM_API_KEY="",
            GUARDRAIL_ENABLE_QWEN_CLASSIFIER=False,
            GUARDRAIL_ENABLE_SINGGUARD_CLASSIFIER=False,
        ):
            result = readiness_service.snapshot(refresh=True)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["summary"]["required_failed"], 0)
        self.assertEqual(
            next(item for item in result["checks"] if item["id"] == "chat_model")[
                "status"
            ],
            "warn",
        )
        self.assertEqual(
            next(item for item in result["scenarios"] if item["id"] == "audit_forensics")[
                "status"
            ],
            "ready",
        )

    def test_deepfake_check_uses_the_weight_loaded_by_the_real_service(self):
        with patch.object(config, "DEEPFAKE_MODEL_PATH", "obsolete/model.torchscript"):
            result = readiness_service.snapshot(refresh=True)
        deepfake = next(
            item for item in result["checks"] if item["id"] == "deepfake_model"
        )
        self.assertEqual(deepfake["status"], "pass")

    def test_required_failure_is_not_ready(self):
        with patch.object(audit_log_service, "verify_chain", return_value=False):
            result = readiness_service.snapshot(refresh=True)
        self.assertEqual(result["status"], "not_ready")
        self.assertEqual(result["summary"]["required_failed"], 1)
        audit = next(item for item in result["checks"] if item["id"] == "audit_chain")
        self.assertEqual(audit["status"], "fail")

    def test_passive_snapshot_uses_short_cache(self):
        first = readiness_service.snapshot(refresh=True)
        self.assertFalse(first["cached"])
        with patch.object(readiness_service, "_build_snapshot") as build:
            second = readiness_service.snapshot()
        build.assert_not_called()
        self.assertTrue(second["cached"])

    def test_active_probe_requires_operator_calls_model_once_and_encrypts_evidence(self):
        self.assertEqual(self.client.post("/api/system/readiness/probe").status_code, 401)
        token = auth_service.create_session(auth_service.current_user())
        self.client.cookies.set("aigc_operator_session", token)

        with patch.object(
            guarded_chat_service,
            "run",
            side_effect=self._successful_guarded_run,
        ) as run:
            first = self.client.post("/api/system/readiness/probe")
            second = self.client.post("/api/system/readiness/probe")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        run.assert_called_once()
        data = first.json()
        self.assertEqual(data["status"], "ready")
        self.assertTrue(data["model_called"])
        self.assertEqual(data["attempts"], 1)
        self.assertEqual(data["max_attempts"], 2)
        self.assertFalse(data["recovered_after_retry"])
        self.assertEqual(data["input_verdict"], "safe")
        self.assertEqual(data["output_verdict"], "safe")
        self.assertEqual(
            data["output_sha256"], hashlib.sha256(b"READY").hexdigest()
        )
        self.assertFalse(data["privacy"]["raw_content_included"])
        self.assertTrue(second.json()["cached"])
        self.assertNotIn(readiness_service.PROBE_PROMPT, first.text)
        self.assertNotIn("READY", first.text)
        evidence = audit_log_service.get_evidence(data["evidence_event_id"])
        self.assertEqual(evidence["prompt"], readiness_service.PROBE_PROMPT)
        self.assertEqual(evidence["response"], "READY")
        self.assertTrue(audit_log_service.verify_chain())

    def test_active_probe_recovers_from_one_transient_gateway_failure(self):
        calls = 0

        def flaky_run(prompt, max_tokens=None, evidence_capture=None):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise guarded_chat_service.ModelGatewayError("temporary outage")
            return self._successful_guarded_run(prompt, max_tokens, evidence_capture)

        with patch.object(
            guarded_chat_service, "run", side_effect=flaky_run
        ) as run, patch.object(readiness_service.time, "sleep") as sleep:
            result, evidence = readiness_service.active_model_probe()

        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["model_called"])
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["max_attempts"], 2)
        self.assertTrue(result["recovered_after_retry"])
        self.assertEqual(evidence["response"], "READY")
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(readiness_service.PROBE_RETRY_DELAY_SECONDS)

    def test_active_probe_reports_safe_failure_after_bounded_retries(self):
        secret_error = "https://secret-gateway.invalid/token/private"
        with patch.object(
            guarded_chat_service,
            "run",
            side_effect=guarded_chat_service.ModelGatewayError(secret_error),
        ) as run, patch.object(readiness_service.time, "sleep") as sleep:
            result, evidence = readiness_service.active_model_probe()

        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["model_called"])
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["error_code"], "model_gateway_unavailable")
        self.assertFalse(result["recovered_after_retry"])
        self.assertEqual(evidence["response"], "")
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(readiness_service.PROBE_RETRY_DELAY_SECONDS)
        self.assertNotIn(secret_error, json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
