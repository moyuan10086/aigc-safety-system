import unittest

from services.model_output_normalizer import normalize_classifier_output


ALLOWED = {"jailbreak", "cyber_abuse", "sensitive_data"}


class ModelOutputNormalizerTests(unittest.TestCase):
    def test_json_verdict_and_scores_are_normalized(self):
        result = normalize_classifier_output(
            '{"verdict":"unsafe","categories":["jailbreak"],"scores":{"jailbreak":1.4},"reason":"test"}',
            allowed_categories=ALLOWED,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["verdict"], "unsafe")
        self.assertEqual(result["scores"], {"jailbreak": 1.0})
        self.assertEqual(result["parse_mode"], "json")

    def test_fenced_and_embedded_json_are_supported(self):
        fenced = normalize_classifier_output(
            'analysis...```json\n{"safety":"review","categories":"sensitive_data"}\n```',
            allowed_categories=ALLOWED,
        )
        self.assertEqual(fenced["status"], "ok")
        self.assertEqual(fenced["verdict"], "borderline")
        embedded = normalize_classifier_output(
            'Explanation: {"verdict":"safe","reason":"ok"}',
            allowed_categories=ALLOWED,
        )
        self.assertEqual(embedded["status"], "ok")
        self.assertEqual(embedded["verdict"], "safe")

    def test_malformed_output_is_inconclusive_and_raw_text_not_returned(self):
        raw = "model generated an unstructured explanation with secret-like text"
        result = normalize_classifier_output(raw, allowed_categories=ALLOWED)
        self.assertEqual(result["status"], "inconclusive")
        self.assertIsNone(result["verdict"])
        self.assertNotIn(raw, str(result))
        self.assertEqual(len(result["output_sha256"]), 64)

    def test_unknown_categories_are_dropped(self):
        result = normalize_classifier_output(
            '{"verdict":"safe","categories":["unknown","jailbreak"],"scores":{"unknown":0.9}}',
            allowed_categories=ALLOWED,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["categories"], ["jailbreak"])
        self.assertEqual(result["scores"], {})


if __name__ == "__main__":
    unittest.main()
