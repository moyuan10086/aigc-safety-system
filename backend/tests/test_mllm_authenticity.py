import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from services import mllm_service


class MllmAuthenticityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.image = Path(self.temp_dir.name) / "sample.jpg"
        self.image.write_bytes(b"image-fixture")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_low_evidence_binary_claim_is_normalized_to_uncertain(self):
        result = mllm_service.normalize_authenticity(
            {"verdict": "fake", "confidence": 0.95, "evidence": []},
            model="test-model",
        )

        self.assertEqual(result["verdict"], "uncertain")
        self.assertTrue(result["requires_human_review"])
        self.assertEqual(result["model"], "test-model")

    def test_analyze_reads_current_main_system_model_config(self):
        raw = (
            '{"verdict":"fake","confidence":0.9,"evidence":["边缘异常"],'
            '"regions":[],"explanation":"发现局部异常"}'
        )
        with patch.object(config, "MLLM_MODEL", "runtime-vision-model"), patch.object(
            mllm_service, "_request_authenticity", return_value=raw
        ):
            result = mllm_service.analyze(str(self.image))

        self.assertEqual(result["model"], "runtime-vision-model")
        self.assertEqual(result["verdict"], "fake")
        self.assertTrue(result["model_called"])
        self.assertEqual(result["status"], "completed")

    def test_invalid_output_fails_closed(self):
        with patch.object(mllm_service, "_request_authenticity", return_value="not json"):
            result = mllm_service.analyze(str(self.image))

        self.assertEqual(result["verdict"], "uncertain")
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["error_code"], "invalid_model_output")
        self.assertTrue(result["model_called"])

    def test_model_failure_fails_closed_without_raising(self):
        with patch.object(
            mllm_service, "_request_authenticity", side_effect=RuntimeError("upstream down")
        ):
            result = mllm_service.analyze(str(self.image))

        self.assertEqual(result["verdict"], "uncertain")
        self.assertEqual(result["error_code"], "model_unavailable")
        self.assertFalse(result["model_called"])
        self.assertEqual(len(result["content_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
