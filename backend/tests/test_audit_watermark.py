import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from services.audit_watermark_service import AuditWatermarkError, decode, decode_archive, embed


class AuditWatermarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.png"
        Image.new("L", (128, 128), 180).save(self.source)

    def tearDown(self):
        self.tmp.cleanup()

    def test_embed_extract_and_recover_round_trip(self):
        output = self.root / "audit-copy.png"
        artifact = embed(
            self.source,
            output,
            {"event_id": "evt-1", "sample_id": "sample-1", "platform_version": "1.0"},
        )
        result = decode(output, artifact["sidecar"])

        self.assertEqual(result["payload"]["event_id"], "evt-1")
        self.assertTrue(result["payload_integrity"])
        self.assertTrue(result["recovered_matches_original"])
        self.assertNotEqual(self.source.read_bytes(), output.read_bytes())

    def test_tamper_is_detected(self):
        output = self.root / "audit-copy.png"
        artifact = embed(self.source, output, {"event_id": "evt-1", "sample_id": "sample-1"})
        with Image.open(output) as image:
            pixels = list(image.get_flattened_data())
            pixels[0] ^= 1
            image.putdata(pixels)
            image.save(output)

        with self.assertRaises(AuditWatermarkError):
            decode(output, artifact["sidecar"])

    def test_rejects_unapproved_payload_fields(self):
        with self.assertRaisesRegex(AuditWatermarkError, "payload_fields_not_allowed"):
            embed(
                self.source,
                self.root / "out.png",
                {"event_id": "1", "sample_id": "2", "api_key": "secret"},
            )

    def test_decode_archive_validates_generated_zip_package(self):
        output = self.root / "audit-copy.png"
        artifact = embed(self.source, output, {"event_id": "evt-zip", "sample_id": "sample-zip"})
        package = self.root / "audit-package.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.write(output, "audit-copy.png")
            archive.writestr("audit-sidecar.json", __import__("json").dumps(artifact["sidecar"], ensure_ascii=False))
            for index, share in enumerate(artifact.get("shares", []), 1):
                archive.writestr(f"key-share-{index}.txt", share)

        result = decode_archive(package)

        self.assertEqual(result["payload"]["event_id"], "evt-zip")
        self.assertTrue(result["recovered_matches_original"])

    def test_color_audit_copy_preserves_rgb_mode_and_recovers_original_pixels(self):
        source = self.root / "color-source.png"
        Image.new("RGB", (128, 128), (24, 96, 220)).save(source)
        output = self.root / "color-audit-copy.png"
        artifact = embed(source, output, {"event_id": "evt-color", "sample_id": "sample-color"})

        with Image.open(output) as image:
            self.assertEqual(image.mode, "RGB")
            self.assertNotEqual(image.getpixel((0, 0)), (180, 180, 180))
        self.assertNotIn("shares", artifact["sidecar"]["sealed_payload"])
        self.assertEqual(len(artifact["shares"]), 3)
        result = decode(output, artifact["sidecar"], shares=artifact["shares"][:2])

        self.assertTrue(result["recovered_matches_original"])

    def test_color_audit_copy_requires_threshold_shares(self):
        source = self.root / "threshold-source.png"
        Image.new("RGB", (128, 128), (20, 80, 160)).save(source)
        artifact = embed(source, self.root / "threshold-copy.png", {"event_id": "evt-threshold", "sample_id": "sample-threshold"})

        with self.assertRaisesRegex(AuditWatermarkError, "threshold_not_met"):
            decode(artifact["watermarked_path"], artifact["sidecar"], shares=artifact["shares"][:1])

    def test_structured_detection_summary_and_custom_note_are_encrypted_and_recovered(self):
        source = self.root / "structured-source.png"
        Image.new("RGB", (128, 128), (20, 80, 160)).save(source)
        payload = {
            "event_id": "evt-structured",
            "sample_id": "sample.png",
            "report_id": "report-001",
            "custom_note": "比赛现场复核样本",
            "deepfake": {"status": "completed", "label": "fake", "score": 0.82, "model": "xception"},
            "provenance": {"status": "completed", "state": "confirmed_source", "provider": "OpenAI"},
            "content_safety": {"status": "not_run", "verdict": None, "risk_score": None, "categories": []},
            "human_review": {"status": "pending", "verdict": None},
        }
        artifact = embed(source, self.root / "structured-copy.png", payload)

        self.assertNotIn("比赛现场复核样本", __import__("json").dumps(artifact["sidecar"], ensure_ascii=False))
        result = decode(artifact["watermarked_path"], artifact["sidecar"], shares=artifact["shares"][:2])

        self.assertEqual(result["payload"]["report_id"], "report-001")
        self.assertEqual(result["payload"]["deepfake"]["score"], 0.82)
        self.assertEqual(result["payload"]["content_safety"]["status"], "not_run")
        self.assertEqual(result["payload"]["custom_note"], "比赛现场复核样本")

    def test_custom_note_rejects_secret_like_content(self):
        source = self.root / "secret-source.png"
        Image.new("RGB", (128, 128), (20, 80, 160)).save(source)
        with self.assertRaisesRegex(AuditWatermarkError, "payload_contains_secret_like_text"):
            embed(source, self.root / "secret-copy.png", {
                "event_id": "evt-secret", "sample_id": "sample.png",
                "custom_note": "api_key=do-not-store-this",
            })
