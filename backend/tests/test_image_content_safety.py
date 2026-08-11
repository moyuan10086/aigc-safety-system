import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from services import mllm_service


class TestImageContentSafetyNormalization(unittest.TestCase):
    def test_content_safety_includes_independent_nudenet_shadow_evidence(self):
        scores = {code: 0.0 for code in mllm_service.CONTENT_SAFETY_CATEGORIES}
        specialist = {
            "provider": "nudenet",
            "status": "detected",
            "adult_score": 0.91,
            "regions": [{"class": "BUTTOCKS_EXPOSED", "score": 0.91, "box": [1, 2, 3, 4]}],
            "latency_ms": 12,
            "model_version": "3.4.2/320n",
            "shadow_only": True,
            "error_code": None,
        }
        with TemporaryDirectory() as directory:
            sample = Path(directory) / "sample.jpg"
            sample.write_bytes(b"synthetic-image-fixture")
            with patch.object(
                mllm_service,
                "_request_content_safety",
                return_value=(
                    '{"verdict":"safe","risk_score":0.0,"category_scores":'
                    + __import__("json").dumps(scores)
                    + ',"categories":[],"summary":"no visible risk"}'
                ),
            ), patch.object(mllm_service.nudenet_service, "analyze", return_value=specialist):
                result = mllm_service.analyze_content_safety(str(sample))

        self.assertEqual(result["specialist_evidence"]["nudenet"], specialist)
        self.assertEqual(result["verdict"], "safe")
        self.assertEqual(result["category_scores"]["adult_content"], 0.0)

    def test_content_safety_calls_unsafe_bench_as_independent_evidence(self):
        scores = {code: 0.0 for code in mllm_service.CONTENT_SAFETY_CATEGORIES}
        unsafe_bench = {
            "provider": "unsafe_bench",
            "status": "detected",
            "risk_score": 0.88,
            "categories": ["violence"],
        }
        with TemporaryDirectory() as directory:
            sample = Path(directory) / "sample.jpg"
            sample.write_bytes(b"synthetic-image-fixture")
            with (
                patch.object(mllm_service.config, "UNSAFE_BENCH_PRIMARY", False),
                patch.object(
                    mllm_service,
                    "_request_content_safety",
                    return_value=(
                        '{"verdict":"safe","risk_score":0.0,"category_scores":'
                        + __import__("json").dumps(scores)
                        + ',"categories":[],"summary":"no visible risk"}'
                    ),
                ),
                patch.object(mllm_service.nudenet_service, "analyze", return_value={"status": "not_configured"}),
                patch.object(mllm_service.unsafe_bench_service, "analyze", return_value=unsafe_bench) as analyze,
            ):
                result = mllm_service.analyze_content_safety(str(sample))

        analyze.assert_called_once_with(str(sample))
        self.assertEqual(result["specialist_evidence"]["unsafe_bench"], unsafe_bench)
        self.assertEqual(result["verdict"], "safe")

    def test_unsafe_bench_can_be_configured_as_primary_with_mllm_auxiliary(self):
        scores = {code: 0.0 for code in mllm_service.CONTENT_SAFETY_CATEGORIES}
        unsafe_bench = {
            "provider": "unsafe_bench",
            "model": "multiheaded",
            "status": "detected",
            "risk_score": 0.71,
            "categories": [],
        }
        with TemporaryDirectory() as directory:
            sample = Path(directory) / "sample.jpg"
            sample.write_bytes(b"synthetic-image-fixture")
            with (
                patch.object(mllm_service.config, "UNSAFE_BENCH_PRIMARY", True),
                patch.object(mllm_service, "_request_content_safety", return_value=(
                    '{"verdict":"safe","risk_score":0.0,"category_scores":'
                    + __import__("json").dumps(scores)
                    + ',"categories":[],"summary":"no visible risk"}'
                )),
                patch.object(mllm_service.nudenet_service, "analyze", return_value={"status": "not_configured"}),
                patch.object(mllm_service.unsafe_bench_service, "analyze", return_value=unsafe_bench),
                patch.object(mllm_service.perspectivevision_service, "analyze", return_value={"status": "not_detected"}),
            ):
                result = mllm_service.analyze_content_safety(str(sample))

        self.assertEqual(result["primary_engine"], "unsafe_bench")
        self.assertEqual(result["auxiliary_engine"], "mllm")
        self.assertEqual(result["verdict"], "review")
        self.assertEqual(result["mllm_auxiliary"]["verdict"], "safe")

    def test_perspectivevision_escalates_primary_safe_result_to_review(self):
        scores = {code: 0.0 for code in mllm_service.CONTENT_SAFETY_CATEGORIES}
        with TemporaryDirectory() as directory:
            sample = Path(directory) / "sample.jpg"
            sample.write_bytes(b"synthetic-image-fixture")
            with (
                patch.object(mllm_service.config, "UNSAFE_BENCH_PRIMARY", True),
                patch.object(mllm_service, "_request_content_safety", return_value=(
                    '{"verdict":"safe","risk_score":0.0,"category_scores":'
                    + __import__("json").dumps(scores)
                    + ',"categories":[],"summary":"no visible risk"}'
                )),
                patch.object(mllm_service.nudenet_service, "analyze", return_value={"status": "not_configured"}),
                patch.object(mllm_service.unsafe_bench_service, "analyze", return_value={
                    "provider": "unsafe_bench",
                    "model": "multiheaded+q16",
                    "status": "not_detected",
                    "risk_score": 0.12,
                    "categories": [],
                }),
                patch.object(mllm_service.perspectivevision_service, "analyze", return_value={
                    "provider": "perspective_vision",
                    "status": "detected",
                    "categories": ["violence"],
                }) as perspective,
            ):
                result = mllm_service.analyze_content_safety(str(sample))

        perspective.assert_called_once_with(str(sample))
        self.assertEqual(result["verdict"], "review")
        self.assertFalse(result["safe"])
        self.assertEqual(result["secondary_engine"], "perspective_vision")
        self.assertEqual(result["secondary_categories"], ["violence"])

    def test_primary_detection_skips_perspectivevision(self):
        scores = {code: 0.0 for code in mllm_service.CONTENT_SAFETY_CATEGORIES}
        with TemporaryDirectory() as directory:
            sample = Path(directory) / "sample.jpg"
            sample.write_bytes(b"synthetic-image-fixture")
            with (
                patch.object(mllm_service.config, "UNSAFE_BENCH_PRIMARY", True),
                patch.object(mllm_service, "_request_content_safety", return_value=(
                    '{"verdict":"safe","risk_score":0.0,"category_scores":'
                    + __import__("json").dumps(scores)
                    + ',"categories":[],"summary":"no visible risk"}'
                )),
                patch.object(mllm_service.nudenet_service, "analyze", return_value={"status": "not_configured"}),
                patch.object(mllm_service.unsafe_bench_service, "analyze", return_value={
                    "provider": "unsafe_bench",
                    "model": "multiheaded+q16",
                    "status": "detected",
                    "risk_score": 0.91,
                    "categories": ["violence"],
                }),
                patch.object(mllm_service.perspectivevision_service, "analyze") as perspective,
                patch.object(mllm_service.perspectivevision_service, "not_run", return_value={
                    "provider": "perspective_vision",
                    "status": "not_run",
                    "error_code": "primary_risk_detected",
                }),
            ):
                result = mllm_service.analyze_content_safety(str(sample))

        perspective.assert_not_called()
        self.assertEqual(result["verdict"], "unsafe")
        self.assertEqual(
            result["specialist_evidence"]["perspective_vision"]["status"],
            "not_run",
        )

    def test_perspectivevision_failure_escalates_primary_safe_result(self):
        result = mllm_service._apply_perspective_secondary(
            {
                "verdict": "safe",
                "safe": True,
                "risk_score": 0.1,
                "summary": "primary safe",
            },
            {"status": "inconclusive", "error_code": "timeout"},
        )

        self.assertEqual(result["verdict"], "review")
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["error_code"], "perspectivevision_inconclusive")

    def test_extracts_first_valid_json_object_from_mixed_model_output(self):
        payload = mllm_service._json_object(
            '审核结果如下：\n```json\n{"verdict":"review","risk_score":0.7,"categories":[]}\n```\n补充说明 {not-json}'
        )

        self.assertEqual(payload["verdict"], "review")
        self.assertEqual(payload["risk_score"], 0.7)

    def test_whitelists_categories_and_clamps_scores(self):
        result = mllm_service.normalize_content_safety({
            "verdict": "unsafe",
            "risk_score": 4,
            "categories": [
                {"code": "weapon_display", "confidence": 0.92, "severity": "high", "evidence": "桌面可见枪械"},
                {"code": "invented_category", "confidence": 1, "severity": "critical"},
                {"code": "weapon_display", "confidence": 0.7, "severity": "low"},
            ],
            "summary": "发现高风险内容",
        }, model="test-model")

        self.assertEqual(result["verdict"], "unsafe")
        self.assertEqual(result["risk_score"], 1.0)
        self.assertEqual(len(result["categories"]), 1)
        self.assertEqual(result["categories"][0]["label"], "疑似武器展示")
        self.assertEqual(result["model"], "test-model")

    def test_normalizes_legacy_graphic_violence_code(self):
        result = mllm_service.normalize_content_safety({
            "verdict": "unsafe",
            "risk_score": 0.8,
            "categories": [{
                "code": "graphic_violence",
                "confidence": 0.82,
                "severity": "high",
            }],
        }, model="test-model")

        self.assertEqual(result["categories"][0]["code"], "violence")
        self.assertEqual(result["categories"][0]["label"], "疑似暴力血腥")
        self.assertEqual(result["categories"][0]["confidence"], 0.82)

    def test_unexplained_unsafe_result_is_sent_to_review(self):
        result = mllm_service.normalize_content_safety({
            "verdict": "unsafe",
            "risk_score": 0.8,
            "categories": [],
        })

        self.assertEqual(result["verdict"], "review")
        self.assertTrue(result["requires_human_review"])
        self.assertFalse(result["safe"])

    def test_safe_result_with_category_is_not_auto_allowed(self):
        result = mllm_service.normalize_content_safety({
            "verdict": "safe",
            "risk_score": 0.1,
            "categories": [
                {"code": "marketing_violation", "confidence": 0.62, "severity": "medium", "evidence": "承诺保本收益"},
            ],
        })

        self.assertEqual(result["verdict"], "review")
        self.assertEqual(result["risk_score"], 0.62)

    def test_preserves_explicit_scores_for_every_safety_category(self):
        scores = {code: 0.05 for code in mllm_service.CONTENT_SAFETY_CATEGORIES}
        scores["adult_content"] = 0.82
        result = mllm_service.normalize_content_safety({
            "verdict": "unsafe",
            "risk_score": 0.82,
            "category_scores": scores,
            "categories": [{
                "code": "adult_content",
                "confidence": 0.82,
                "severity": "high",
                "evidence": "可见成人内容",
            }],
        })

        self.assertEqual(result["category_scores"]["adult_content"], 0.82)
        self.assertEqual(result["missing_category_scores"], [])
        self.assertEqual(result["score_coverage"], 1.0)

    def test_incomplete_category_scores_fail_closed(self):
        with TemporaryDirectory() as directory:
            sample = Path(directory) / "sample.jpg"
            sample.write_bytes(b"synthetic-image-fixture")
            with patch.object(mllm_service, "_request_content_safety", return_value=(
                '{"verdict":"safe","risk_score":0.0,'
                '"category_scores":{"violence":0.0},"categories":[],"summary":"未见风险"}'
            )):
                result = mllm_service.analyze_content_safety(str(sample))

        self.assertEqual(result["verdict"], "review")
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["error_code"], "incomplete_category_scores")
        self.assertLess(result["score_coverage"], 1.0)

    def test_model_failure_fails_closed_to_human_review(self):
        with TemporaryDirectory() as directory:
            sample = Path(directory) / "sample.jpg"
            sample.write_bytes(b"synthetic-image-fixture")
            with patch.object(mllm_service, "_request_content_safety", side_effect=RuntimeError("upstream failed")):
                result = mllm_service.analyze_content_safety(str(sample))

        self.assertEqual(result["verdict"], "review")
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["error_code"], "model_unavailable")
        self.assertEqual(len(result["content_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
