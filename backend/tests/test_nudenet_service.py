import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services import nudenet_service


class StubDetector:
    def __init__(self, detections=None, error=None):
        self.detections = detections or []
        self.error = error

    def detect(self, _image_path):
        if self.error:
            raise self.error
        return self.detections


class TestNudeNetService(unittest.TestCase):
    def test_reads_image_as_bytes_for_unicode_safe_paths(self):
        captured = []

        class CapturingDetector:
            def detect(self, image):
                captured.append(image)
                return []

        with TemporaryDirectory() as directory:
            sample = Path(directory) / "中文样本.jpg"
            sample.write_bytes(b"image-bytes")
            result = nudenet_service.analyze(
                str(sample), enabled=True, detector=CapturingDetector()
            )

        self.assertEqual(result["status"], "not_detected")
        self.assertEqual(captured, [b"image-bytes"])

    def test_disabled_detector_is_not_configured(self):
        result = nudenet_service.analyze("unused.jpg", enabled=False)

        self.assertEqual(result["status"], "not_configured")
        self.assertTrue(result["shadow_only"])
        self.assertEqual(result["regions"], [])
        self.assertEqual(result["license"], "AGPL-3.0")
        self.assertEqual(result["source_url"], "https://github.com/notAI-tech/NudeNet")

    def test_explicit_region_is_normalized_as_detected(self):
        detector = StubDetector([
            {"class": "FEMALE_BREAST_EXPOSED", "score": 0.86, "box": [10, 20, 30, 40]},
            {"class": "FACE_FEMALE", "score": 0.97, "box": [1, 2, 3, 4]},
        ])

        with TemporaryDirectory() as directory:
            sample = Path(directory) / "sample.jpg"
            sample.write_bytes(b"image-bytes")
            result = nudenet_service.analyze(
                str(sample), enabled=True, detector=detector, threshold=0.6
            )

        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["adult_score"], 0.86)
        self.assertEqual(len(result["regions"]), 1)
        self.assertEqual(result["regions"][0]["class"], "FEMALE_BREAST_EXPOSED")
        self.assertEqual(result["regions"][0]["box"], [10, 20, 30, 40])

    def test_benign_or_below_threshold_regions_are_not_detected(self):
        detector = StubDetector([
            {"class": "FACE_MALE", "score": 0.99, "box": [0, 0, 20, 20]},
            {"class": "BUTTOCKS_EXPOSED", "score": 0.3, "box": [5, 5, 10, 10]},
        ])

        with TemporaryDirectory() as directory:
            sample = Path(directory) / "sample.jpg"
            sample.write_bytes(b"image-bytes")
            result = nudenet_service.analyze(
                str(sample), enabled=True, detector=detector, threshold=0.6
            )

        self.assertEqual(result["status"], "not_detected")
        self.assertEqual(result["adult_score"], 0.3)
        self.assertEqual(result["regions"], [])

    def test_detector_failure_is_inconclusive_not_safe(self):
        with TemporaryDirectory() as directory:
            sample = Path(directory) / "sample.jpg"
            sample.write_bytes(b"not-an-image")
            result = nudenet_service.analyze(
                str(sample),
                enabled=True,
                detector=StubDetector(error=RuntimeError("runtime failed")),
            )

        self.assertEqual(result["status"], "inconclusive")
        self.assertIsNone(result["adult_score"])
        self.assertEqual(result["error_code"], "detector_unavailable")


if __name__ == "__main__":
    unittest.main()
