# Bundled Local Auditor

This directory is the repository-owned copy of the local text safety auditor used by
`backend/services/xgboost_shadow_service.py`. It is loaded only as an observational
Shadow evaluator and never changes the primary `safe`, `borderline`, or `unsafe`
verdict.

The model contains a serialized pickle payload. Treat it as trusted code and verify
it before deployment:

```bash
sha256sum -c MODEL_SHA256
```

Update the model, `MODEL_SHA256`, `backend/config.py`, `backend/.env.example`, and the
CI environment in the same reviewed change.
