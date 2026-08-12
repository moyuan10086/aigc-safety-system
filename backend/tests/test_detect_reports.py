import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import detect
from PIL import Image


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

    def test_full_audit_persists_results_without_running_detection_twice(self):
        rag_result = {
            "safe": False,
            "risk_level": "high",
            "matched_rules": ["RULE-001"],
        }
        with (
            patch.object(detect.rag_service, "check_content", return_value=rag_result) as check,
            patch.object(detect, "_gen_summary", return_value="# 综合分析\n\n需要人工复核。"),
        ):
            response = self.client.post(
                "/api/detect/full",
                data={"text": "待审核文本", "modules": "rag"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(check.call_count, 1)
        done_line = next(
            line for line in response.text.splitlines() if line.startswith("data:") and "report_id" in line
        )
        done = json.loads(done_line.removeprefix("data:").strip())
        report = json.loads((self.reports_dir / f"{done['report_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(report["rag"], rag_result)
        self.assertEqual(report["requested_modules"], ["rag"])
        self.assertEqual(report["report_title"], "红线知识库审核报告")
        self.assertEqual(report["summary"], "# 综合分析\n\n需要人工复核。")

    def test_provenance_only_report_does_not_claim_unrun_dimensions(self):
        report = {
            "filename": "source.png",
            "requested_modules": ["provenance"],
            "provenance": {"overall_state": "not_found", "content_hash": "abc"},
        }
        self.assertEqual(detect._report_modules(report), ["provenance"])
        self.assertEqual(detect._report_title(report), "AI 来源与内容凭证验证报告")
        self.assertNotIn("deepfake", report)
        self.assertNotIn("content_safety", report)

    def test_report_thumbnail_is_a_small_metadata_free_derivative(self):
        source = self.reports_dir / "source.jpg"
        image = Image.new("RGB", (1200, 800), "navy")
        image.save(source, exif=Image.Exif())
        thumbnail = detect._create_report_thumbnail(str(source), "00000000-0000-0000-0000-000000000001")
        output = self.reports_dir / "thumbnails" / "00000000-0000-0000-0000-000000000001.webp"
        self.assertTrue(output.is_file())
        self.assertLessEqual(max(thumbnail["width"], thumbnail["height"]), 480)
        self.assertTrue(thumbnail["derivative_only"])
        with Image.open(output) as generated:
            self.assertFalse(generated.getexif())

    def test_report_delete_requires_operator_and_removes_thumbnail(self):
        report_id = "00000000-0000-0000-0000-000000000002"
        self._write_report(report_id, {"requested_modules": ["provenance"]})
        thumbnail_dir = self.reports_dir / "thumbnails"
        thumbnail_dir.mkdir()
        (thumbnail_dir / f"{report_id}.webp").write_bytes(b"thumbnail")
        self.assertEqual(self.client.delete(f"/api/detect/report/{report_id}").status_code, 401)
        user = {"username": "operator", "display_name": "审核员", "role": "operator"}
        with patch.object(detect.auth_service, "verify_session", return_value=user), patch.object(
            detect.audit_log_service, "record_safe"
        ) as audit:
            response = self.client.delete(f"/api/detect/report/{report_id}")
        self.assertEqual(response.status_code, 200)
        self.assertFalse((self.reports_dir / f"{report_id}.json").exists())
        self.assertFalse((thumbnail_dir / f"{report_id}.webp").exists())
        audit.assert_called_once()

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
        self.assertIn("多维图片安全审核报告", text)
        self.assertIn("真实性与来源", text)
        self.assertIn("视觉内容安全", text)
        self.assertIn("个人敏感信息: 0.94 (high)", text)
        self.assertIn("gpt-5.4-mini", text)


if __name__ == "__main__":
    unittest.main()
