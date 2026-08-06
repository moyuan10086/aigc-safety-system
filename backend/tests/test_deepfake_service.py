import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import torch
from PIL import Image

from services import deepfake_service


class _FakeModel:
    def __init__(self, probabilities):
        self.logits = torch.log(torch.tensor(probabilities, dtype=torch.float32))

    def __call__(self, _batch):
        return SimpleNamespace(logits_labels=self.logits)


class DeepfakeServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.image = Path(self.temp_dir.name) / "sample.png"
        Image.new("RGB", (320, 240), "white").save(self.image)
        deepfake_service.reset_runtime_state()

    def tearDown(self):
        deepfake_service.reset_runtime_state()
        self.temp_dir.cleanup()

    @staticmethod
    def _crops(*, aligned=True, count=1):
        return [
            (
                Image.new("RGB", (256, 256), "white"),
                {
                    "box": {"x": index * 10, "y": 0, "width": 100, "height": 100},
                    "detector_score": 0.99,
                    "alignment_applied": aligned,
                    "preprocessing": "test",
                },
            )
            for index in range(count)
        ]

    def _run_with_probabilities(self, probabilities, *, aligned=True):
        crops = self._crops(aligned=aligned, count=len(probabilities))
        fake_model = _FakeModel(probabilities)

        def fake_load():
            deepfake_service._model = fake_model
            deepfake_service._preprocess = lambda _image: torch.zeros((3, 2, 2))

        with patch.object(deepfake_service, "_extract_faces", return_value=(crops, None if aligned else "landmark_alignment_unavailable")), patch.object(
            deepfake_service, "_load", side_effect=fake_load
        ):
            return deepfake_service.detect(str(self.image))

    def test_aggregates_maximum_fake_probability_across_faces(self):
        result = self._run_with_probabilities([[0.9, 0.1], [0.15, 0.85]])

        self.assertEqual(result["label"], "fake")
        self.assertAlmostEqual(result["score"], 0.85, places=4)
        self.assertEqual(result["face_count"], 2)
        self.assertEqual([face["label"] for face in result["faces"]], ["real", "fake"])
        self.assertEqual(result["aggregation"], "max_fake_probability")

    def test_middle_probability_is_sent_to_review(self):
        result = self._run_with_probabilities([[0.5, 0.5]])

        self.assertEqual(result["label"], "review")
        self.assertTrue(result["requires_human_review"])

    def test_unaligned_fallback_cannot_be_labeled_real(self):
        result = self._run_with_probabilities([[0.9, 0.1]], aligned=False)

        self.assertEqual(result["label"], "review")
        self.assertEqual(result["error_code"], "landmark_alignment_unavailable")
        self.assertFalse(result["faces"][0]["alignment_applied"])

    def test_no_face_is_inconclusive_without_loading_model(self):
        with patch.object(deepfake_service, "_extract_faces", return_value=([], "no_face_detected")), patch.object(
            deepfake_service, "_load"
        ) as load:
            result = deepfake_service.detect(str(self.image))

        load.assert_not_called()
        self.assertEqual(result["label"], "inconclusive")
        self.assertTrue(result["requires_human_review"])
        self.assertEqual(result["face_count"], 0)

    def test_digest_mismatch_is_rejected(self):
        artifact = Path(self.temp_dir.name) / "model.ckpt"
        artifact.write_bytes(b"checkpoint")

        with self.assertRaises(deepfake_service.DeepfakeServiceError) as raised:
            deepfake_service._verify(artifact, "0" * 64, "checkpoint")

        self.assertEqual(raised.exception.code, "checkpoint_digest_mismatch")

    def test_checkpoint_load_uses_weights_only(self):
        checkpoint = Path(self.temp_dir.name) / "model.ckpt"
        checkpoint.write_bytes(b"fixture")
        model = MagicMock()
        model.eval.return_value = None
        model.get_preprocessing.return_value = MagicMock()
        model.float.return_value = model
        model.to.return_value = model
        payload = {"hyper_parameters": {}, "state_dict": {}}

        with patch.object(deepfake_service, "_ensure_checkpoint", return_value=checkpoint), patch.object(
            deepfake_service.torch, "load", return_value=payload
        ) as load, patch.object(deepfake_service, "Config", return_value=MagicMock()), patch.object(
            deepfake_service, "DeepfakeDetectionModel", return_value=model
        ):
            deepfake_service._load()

        self.assertTrue(load.call_args.kwargs["weights_only"])
        self.assertEqual(deepfake_service.runtime_status()["state"], "loaded_unprobed")

    def test_deepfakebench_target_keeps_five_finite_points(self):
        points = deepfake_service._target_landmarks()

        self.assertEqual(points.shape, (5, 2))
        self.assertTrue(all(math.isfinite(float(value)) for value in points.flatten()))


if __name__ == "__main__":
    unittest.main()
