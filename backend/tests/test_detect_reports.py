import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import detect


class DetectReportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.reports_dir = Path(self.temp_dir.name)
        self.reports_patch = patch.object(detect, "REPORTS_DIR", self.reports_dir)
        self.reports_patch.start()
        app = FastAPI()
        app.include_router(detect.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.reports_patch.stop()
        self.temp_dir.cleanup()

    def _write_report(self, report_id: str, payload: dict) -> None:
        report = {"id": report_id, "created_at": "2026-08-05T05:00:00", **payload}
        (self.reports_dir / f"{report_id}.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8"
        )

    def test_history_keeps_authenticity_and_content_risk_independent(self):
        self._write_report(
            "both-risk-tracks",
            {
                "deepfake": {"label": "fake", "score": 0.91},
                "content_safety": {
                    "verdict": "review",
                    "risk_score": 0.94,
                    "categories": [{"code": "personal_data"}],
                },
            },
        )
        self._write_report("safe-text", {"rag": {"safe": True, "risk_level": "low"}})
        self._write_report("mllm-fake", {"mllm": {"verdict": "fake", "confidence": 0.82}})
        self._write_report("no-result", {})

        response = self.client.get("/api/detect/history")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 4)
        self.assertEqual(body["fake_count"], 2)
        self.assertEqual(body["risk_count"], 1)
        self.assertEqual(body["clear_count"], 1)
        risky = next(item for item in body["reports"] if item["id"] == "both-risk-tracks")
        self.assertEqual(risky["content_safety_verdict"], "review")
        self.assertEqual(risky["content_safety_categories"], ["personal_data"])

    def test_markdown_export_contains_both_review_tracks(self):
        self._write_report(
            "dual-track",
            {
                "filename": "sample.jpg",
                "deepfake": {"label": "real", "score": 0.12, "confidence": 0.88},
                "mllm": {"verdict": "uncertain", "confidence": 0.61},
                "content_safety": {
                    "verdict": "review",
                    "risk_score": 0.94,
                    "model": "gpt-5.4-mini",
                    "categories": [
                        {
                            "code": "personal_data",
                            "label": "个人敏感信息",
                            "confidence": 0.94,
                            "severity": "high",
                        }
                    ],
                },
            },
        )

        response = self.client.get("/api/detect/report/dual-track/download/md")

        self.assertEqual(response.status_code, 200)
        text = response.content.decode("utf-8")
        self.assertIn("多模态内容安全与真实性审计报告", text)
        self.assertIn("真实性与来源", text)
        self.assertIn("视觉内容安全", text)
        self.assertIn("个人敏感信息: 0.94 (high)", text)
        self.assertIn("gpt-5.4-mini", text)


if __name__ == "__main__":
    unittest.main()
