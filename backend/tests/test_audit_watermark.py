import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services.audit_watermark_service import AuditWatermarkError, decode, embed


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
