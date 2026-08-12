import unittest

from services.secret_sharing_service import SecretSharingError, combine, protect, recover, split


class SecretSharingTests(unittest.TestCase):
    def test_threshold_shares_recover_secret(self):
        secret = b"audit evidence encryption key"
        shares = split(secret, threshold=3, share_count=5)

        self.assertEqual(len(shares), 5)
        self.assertEqual(combine(shares[:3]), secret)
        self.assertEqual(combine([shares[0], shares[2], shares[4]]), secret)

    def test_fewer_than_threshold_shares_cannot_recover_original(self):
        secret = b"private audit payload"
        shares = split(secret, threshold=3, share_count=5)

        with self.assertRaisesRegex(SecretSharingError, "threshold_not_met"):
            combine(shares[:2])

    def test_rejects_duplicate_or_invalid_shares(self):
        shares = split(b"secret", threshold=2, share_count=3)

        with self.assertRaisesRegex(SecretSharingError, "duplicate_share"):
            combine([shares[0], shares[0]])
        with self.assertRaisesRegex(SecretSharingError, "share_invalid"):
            combine(["not-a-share", shares[1]])

    def test_protects_and_recovers_audit_payload_with_threshold_shares(self):
        protected = protect({"event_id": "evt-1", "sample_id": "sample-1"}, threshold=2, share_count=3)

        self.assertNotIn("evt-1", protected["ciphertext"])
        self.assertEqual(recover(protected["ciphertext"], protected["nonce"], protected["shares"][:2]), {"event_id": "evt-1", "sample_id": "sample-1"})
        with self.assertRaisesRegex(SecretSharingError, "threshold_not_met"):
            recover(protected["ciphertext"], protected["nonce"], protected["shares"][:1])
