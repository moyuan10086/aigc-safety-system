import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, PngImagePlugin

from services.provenance_service import verify


class ProvenanceServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, marker=None):
        path = self.root / "sample.png"
        info = PngImagePlugin.PngInfo()
        if marker is not None:
            info.add_text("aigc_safety_provenance", marker)
        Image.new("RGB", (32, 32), "white").save(path, pnginfo=info)
        return path

    def test_plain_image_is_not_found_not_non_ai(self):
        result = verify(self._write())
        self.assertEqual(result["overall_state"], "not_found")
        self.assertTrue(result["source_evidence"]["content_credentials"]["supported"])
        self.assertEqual(result["source_evidence"]["content_credentials"]["status"], "not_found")
        self.assertIn("不等于", result["limitations"][0])

    def test_valid_local_marker_confirms_source(self):
        marker = json.dumps({"schema":"aigc-safety-provenance/v1", "source_type":"ai_generated", "issuer":"test", "event_ref":"demo-1"})
        result = verify(self._write(marker))
        self.assertEqual(result["overall_state"], "confirmed_source")
        self.assertEqual(result["metadata"]["local_marker"]["source_type"], "ai_generated")

    def test_malformed_local_marker_is_invalid(self):
        result = verify(self._write("not-json"))
        self.assertEqual(result["overall_state"], "invalid_or_tampered")


if __name__ == "__main__":
    unittest.main()
