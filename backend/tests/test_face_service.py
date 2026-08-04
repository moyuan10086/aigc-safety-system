"""Tests for non-identifying face quality evidence."""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

from routers import detect
from services import face_service


class FaceServiceTests(unittest.TestCase):
    @staticmethod
    def _textured_image(width: int = 640, height: int = 640) -> np.ndarray:
        rng = np.random.default_rng(20260804)
        return rng.integers(40, 216, size=(height, width, 3), dtype=np.uint8)

    def test_single_centered_face_keeps_legacy_fields_and_adds_private_evidence(self):
        result = face_service.analyze_detected_faces(
            self._textured_image(),
            [(160, 120, 320, 360)],
        )

        self.assertEqual(result["status"], "detected")
        self.assertTrue(result["face_detected"])
        self.assertEqual(result["face_count"], 1)
        self.assertEqual(result["primary_face_index"], 0)
        self.assertEqual(result["quality"], "good")
        self.assertFalse(result["review_recommended"])
        self.assertEqual(result["boxes"][0], {"x": 160, "y": 120, "width": 320, "height": 360})
        self.assertGreater(result["largest_face_ratio"], 0.25)
        self.assertEqual(result["faces"][0]["quality"], "good")
        self.assertFalse(result["identity_analysis"])
        self.assertNotIn("embedding", str(result).lower())

    def test_multiple_faces_selects_largest_primary_and_requires_review(self):
        result = face_service.analyze_detected_faces(
            self._textured_image(),
            [(60, 90, 150, 180), (270, 110, 240, 280)],
        )

        self.assertEqual(result["face_count"], 2)
        self.assertEqual(result["primary_face_index"], 1)
        self.assertIn("multiple_faces", result["quality_flags"])
        self.assertTrue(result["review_recommended"])
        self.assertIn("检测到多张人脸，需要确认主要审核对象", result["review_reasons"])

    def test_no_face_never_reports_good_quality(self):
        result = face_service.analyze_detected_faces(self._textured_image(), [])

        self.assertEqual(result["status"], "not_detected")
        self.assertFalse(result["face_detected"])
        self.assertEqual(result["quality"], "review")
        self.assertIn("no_face", result["quality_flags"])
        self.assertIsNone(result["primary_face_index"])

    def test_edge_face_is_clamped_and_explained(self):
        result = face_service.analyze_detected_faces(
            self._textured_image(),
            [(-10, 0, 180, 200)],
        )

        face = result["faces"][0]
        self.assertEqual(face["box"], {"x": 0, "y": 0, "width": 170, "height": 200})
        self.assertEqual(face["edge_margin_ratio"], 0.0)
        self.assertIn("face_near_edge", face["quality_flags"])
        self.assertIn("人脸贴近图像边缘或存在截断", face["review_reasons"])

    def test_blurred_underexposed_face_has_global_and_local_reasons(self):
        image = np.zeros((640, 640, 3), dtype=np.uint8)
        result = face_service.analyze_detected_faces(image, [(160, 160, 320, 320)])

        self.assertIn("blurred", result["quality_flags"])
        self.assertIn("underexposed", result["quality_flags"])
        self.assertIn("face_blurred", result["faces"][0]["quality_flags"])
        self.assertIn("face_underexposed", result["faces"][0]["quality_flags"])

    def test_decode_failure_and_missing_detector_degrade_explicitly(self):
        with patch("cv2.imread", return_value=None):
            decode = face_service.inspect("invalid.png")
        self.assertEqual(decode["reason"], "image_decode_failed")
        self.assertEqual(decode["quality"], "review")
        self.assertEqual(decode["faces"], [])

        image = self._textured_image()
        with patch("cv2.imread", return_value=image), patch.object(
            face_service.Path,
            "exists",
            return_value=False,
        ):
            missing = face_service.inspect("valid.png")
        self.assertEqual(missing["reason"], "face_detector_missing")
        self.assertEqual(missing["image_width"], 640)
        self.assertTrue(missing["review_recommended"])

    def test_detector_uses_ascii_cache_when_package_path_is_non_ascii(self):
        class Detector:
            def __init__(self, path: str):
                self.path = path

            def empty(self) -> bool:
                return False

        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "中文目录"
            source_dir.mkdir()
            source = source_dir / "haarcascade_frontalface_default.xml"
            source.write_text("detector", encoding="utf-8")
            cache_root = Path(temp_dir) / "ascii-cache"

            class Data:
                haarcascades = str(source_dir)

            class Cv2:
                data = Data()
                CascadeClassifier = Detector

            with patch.object(face_service.tempfile, "gettempdir", return_value=str(cache_root)):
                detector = face_service._load_detector(Cv2)

        self.assertIsNotNone(detector)
        self.assertTrue(detector.path.isascii())
        self.assertIn("aigc-safety-face", detector.path)

    def test_router_wrapper_preserves_existing_callers(self):
        expected = {"status": "detected", "face_count": 1}
        with patch.object(face_service, "inspect", return_value=expected) as inspect:
            self.assertEqual(detect._inspect_faces("sample.jpg"), expected)
        inspect.assert_called_once_with("sample.jpg")


if __name__ == "__main__":
    unittest.main()
