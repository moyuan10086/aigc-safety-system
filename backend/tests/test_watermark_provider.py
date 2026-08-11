import tempfile
import unittest
from pathlib import Path

from services.watermark_provider_service import WatermarkProviderError, check


class WatermarkProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.image = Path(self.tmp.name) / "sample.png"
        self.image.write_bytes(b"test-image-content")

    def tearDown(self):
        self.tmp.cleanup()

    def test_requires_explicit_consent(self):
        with self.assertRaisesRegex(WatermarkProviderError, "consent_required"):
            check(self.image, provider="aivo", consent=False)

    def test_unconfigured_provider_is_not_not_detected(self):
        result = check(self.image, provider="aivo", consent=True)

        self.assertEqual(result["status"], "not_configured")
        self.assertFalse(result["privacy"]["external_upload"])
        self.assertIn("aivo.my", result["evidence"]["verification_url"])
