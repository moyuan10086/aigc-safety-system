import unittest

from services import mllm_service


class TestImageContentSafetyNormalization(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
