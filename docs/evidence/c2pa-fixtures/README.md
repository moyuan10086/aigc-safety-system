# C2PA fixture evidence

These public fixtures are used only for parser regression and production API verification.

- `c2pa-rs-update-manifest.jpg`: public C2PA SDK fixture. The service returned `valid`, `manifest_count=2`, `trust_verified=true`, and `overall_state=confirmed_source` in the production API test. This is evidence that the parser can read a valid C2PA container; it is not proof that the pictured content is AI-generated and it is not a production issuer trust decision for our platform.
- `c2pa-rs-ocsp.jpg`: public C2PA SDK fixture. The service returned `inconclusive` with `manifest_parse_failed`; this verifies the safe uncertainty path.
- `c2pa-rs-sample1.png`: public C2PA SDK sample without a manifest for this parser, retained as a negative control (`not_found`).

The images are public upstream test fixtures, not user images. They are not uploaded to ordinary logs or retained by the API after processing. SHA-256 values and the production response summary are recorded in `docs/evidence/c2pa-production-20260804.json`.
