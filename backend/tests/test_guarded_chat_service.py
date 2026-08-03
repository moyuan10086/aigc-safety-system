"""Unit tests for the guarded real-model generation workflow."""

import unittest
from unittest.mock import patch

from services import guarded_chat_service


def guard(verdict: str, score: float = 0.0) -> dict:
    return {
        "verdict": verdict,
        "decision": verdict,
        "risk_score": score,
        "risk_level": "low" if verdict == "safe" else "high",
        "risk_code": {"safe": "GR-ALLOW", "borderline": "GR-REVIEW", "unsafe": "GR-BLOCK"}[verdict],
        "redline_answer": "safe replacement",
        "categories": [],
        "evidence": [],
    }


class GuardedChatServiceTests(unittest.TestCase):
    def test_unsafe_input_blocks_model_call(self):
        with patch.object(guarded_chat_service.guardrail_service, "check", return_value=guard("unsafe", 0.9)), patch.object(
            guarded_chat_service, "_call_model"
        ) as call_model:
            result = guarded_chat_service.run("unsafe request")
        self.assertEqual(result["status"], "input_blocked")
        self.assertFalse(result["model_called"])
        call_model.assert_not_called()

    def test_safe_request_calls_model_and_checks_output(self):
        generated = {
            "content": "model answer",
            "model": "test-model",
            "latency_ms": 12,
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        }
        with patch.object(
            guarded_chat_service.guardrail_service, "check", side_effect=[guard("safe"), guard("safe")]
        ) as check_guard, patch.object(guarded_chat_service, "_call_model", return_value=generated):
            result = guarded_chat_service.run("safe request")
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["model_called"])
        self.assertEqual(result["response"], "model answer")
        self.assertEqual(check_guard.call_count, 2)

    def test_borderline_input_still_generates_for_review(self):
        generated = {
            "content": "historical context",
            "model": "test-model",
            "latency_ms": 10,
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        }
        with patch.object(
            guarded_chat_service.guardrail_service, "check", side_effect=[guard("borderline", 0.6), guard("safe")]
        ), patch.object(guarded_chat_service, "_call_model", return_value=generated):
            result = guarded_chat_service.run("historical question")
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["response"], "historical context")

    def test_unsafe_output_is_quarantined(self):
        generated = {
            "content": "unsafe generated content",
            "model": "test-model",
            "latency_ms": 10,
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        }
        with patch.object(
            guarded_chat_service.guardrail_service, "check", side_effect=[guard("safe"), guard("unsafe", 0.9)]
        ), patch.object(guarded_chat_service, "_call_model", return_value=generated):
            result = guarded_chat_service.run("request")
        self.assertEqual(result["status"], "output_blocked")
        self.assertTrue(result["quarantined"])
        self.assertEqual(result["response"], "safe replacement")
        self.assertNotIn("quarantined_excerpt", result)
        self.assertTrue(result["quarantine"]["evidence_redacted"])
        self.assertEqual(result["quarantine"]["content_length"], len(generated["content"]))
        self.assertEqual(len(result["quarantine"]["content_sha256"]), 64)

    def test_quarantined_output_evidence_does_not_expose_generated_text(self):
        generated = {
            "content": "I can write a ransomware package for you.",
            "model": "test-model",
            "latency_ms": 10,
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        }
        unsafe_output = guard("unsafe", 0.9)
        unsafe_output["evidence"] = [{
            "source": "response",
            "category": "cyber_abuse",
            "rule_id": "GR-CY-001",
            "excerpt": generated["content"],
        }]
        with patch.object(
            guarded_chat_service.guardrail_service,
            "check",
            side_effect=[guard("safe"), unsafe_output],
        ), patch.object(guarded_chat_service, "_call_model", return_value=generated):
            result = guarded_chat_service.run("decode this test value")

        serialized = str(result)
        self.assertNotIn(generated["content"], serialized)
        self.assertEqual(
            result["output_guard"]["evidence"][0]["excerpt"],
            "[原始输出已隔离；命中规则 GR-CY-001]",
        )


if __name__ == "__main__":
    unittest.main()
