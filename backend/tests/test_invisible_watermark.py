import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services.invisible_watermark_service import (
    InvisibleWatermarkError,
    check,
    embed,
)


class InvisibleWatermarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.png"
        image = Image.new("RGB", (256, 256))
        image.putdata(
            [
                ((x * 7 + y * 3) % 256, (x * 5 + y * 11) % 256, (x * 13 + y * 2) % 256)
                for y in range(256)
                for x in range(256)
            ]
        )
        image.save(self.source)
        self.secret = "test-invisible-watermark-signing-secret"

    def tearDown(self):
        self.tmp.cleanup()

    def test_embed_and_check_confirms_signed_platform_watermark(self):
        output = self.root / "watermarked.png"
        artifact = embed(
            self.source,
            output,
            {"content_id": "img-001", "content_type": "ai_generated"},
            secret=self.secret,
        )

        result = check(output, secret=self.secret)

        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(result["provider"], "aigc-safety")
        self.assertEqual(result["watermark_type"], "frequency-domain-dct")
        self.assertEqual(result["payload"]["content_id"], "img-001")
        self.assertTrue(result["signature_valid"])
        self.assertEqual(artifact["payload"]["content_type"], "ai_generated")
        self.assertNotEqual(self.source.read_bytes(), output.read_bytes())

    def test_plain_image_returns_no_signal_instead_of_human_created(self):
        result = check(self.source, secret=self.secret)

        self.assertEqual(result["status"], "no_signal")
        self.assertIsNone(result["payload"])
        self.assertIn("不代表非 AI", result["note"])

    def test_wrong_signing_key_marks_detected_signal_invalid(self):
        output = self.root / "watermarked.png"
        embed(
            self.source,
            output,
            {"content_id": "img-002", "content_type": "ai_generated"},
            secret=self.secret,
        )

        result = check(output, secret="different-signing-secret")

        self.assertEqual(result["status"], "invalid")
        self.assertFalse(result["signature_valid"])
        self.assertTrue(result["tamper_suspected"])

    def test_embed_rejects_unapproved_or_oversized_payload(self):
        with self.assertRaisesRegex(InvisibleWatermarkError, "payload_fields_not_allowed"):
            embed(
                self.source,
                self.root / "invalid.png",
                {"content_id": "img-003", "password": "secret"},
                secret=self.secret,
            )

