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

    def test_unsigned_local_marker_is_inconclusive(self):
        marker = json.dumps({"schema":"aigc-safety-provenance/v1", "source_type":"ai_generated", "issuer":"test", "event_ref":"demo-1"})
        result = verify(self._write(marker))
        local_marker = result["source_evidence"]["local_marker"]
        self.assertEqual(result["overall_state"], "inconclusive")
        self.assertEqual(local_marker["status"], "inconclusive")
        self.assertEqual(local_marker["error"], "declared_local_marker_unsigned")
        self.assertFalse(local_marker["trust_verified"])
        self.assertEqual(result["metadata"]["local_marker"]["source_type"], "ai_generated")

    def test_malformed_local_marker_is_invalid(self):
        result = verify(self._write("not-json"))
        self.assertEqual(result["overall_state"], "invalid_or_tampered")

    def test_valid_c2pa_fixture_is_confirmed_source(self):
        fixture = Path(__file__).parents[2] / "docs" / "evidence" / "c2pa-fixtures" / "c2pa-rs-update-manifest.jpg"
        result = verify(fixture)
        credentials = result["source_evidence"]["content_credentials"]
        self.assertEqual(result["overall_state"], "confirmed_source")
        self.assertEqual(credentials["status"], "valid")
        self.assertGreaterEqual(credentials["manifest_count"], 1)
        self.assertTrue(credentials["trust_verified"])
        self.assertFalse(credentials["remote_manifest_fetch"])

    def test_c2pa_parse_failure_is_inconclusive(self):
        fixture = Path(__file__).parents[2] / "docs" / "evidence" / "c2pa-fixtures" / "c2pa-rs-ocsp.jpg"
        result = verify(fixture)
        credentials = result["source_evidence"]["content_credentials"]
        self.assertEqual(credentials["status"], "inconclusive")
        self.assertEqual(result["overall_state"], "inconclusive")

    def test_tampered_c2pa_asset_is_invalid_even_when_container_is_readable(self):
        fixture = Path(__file__).parents[2] / "docs" / "evidence" / "c2pa-fixtures" / "c2pa-rs-update-manifest.jpg"
        tampered = bytearray(fixture.read_bytes())
        self.assertGreater(len(tampered), 20_000)
        tampered[20_000] ^= 1
        path = self.root / "tampered-c2pa.jpg"
        path.write_bytes(tampered)

        result = verify(path)
        credentials = result["source_evidence"]["content_credentials"]
        self.assertEqual(credentials["validation_state"], "invalid")
        self.assertEqual(credentials["status"], "invalid_or_tampered")
        self.assertFalse(credentials["trust_verified"])
        self.assertEqual(result["overall_state"], "invalid_or_tampered")


if __name__ == "__main__":
    unittest.main()
