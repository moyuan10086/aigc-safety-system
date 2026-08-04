# Demo sample handling

`raw/` contains controlled originals used for local evaluation and is excluded from Git. Public UI assets under `frontend/public/demo-samples/` contain only selected non-sensitive samples or masked thumbnails.

The structured evidence file `../image-content-safety-local-20260805.json` records the source class, reference label, SHA-256, latency and real model result without embedding raw image bytes. User uploads are never added to this catalog automatically.

Synthetic identity documents must be marked `AI 合成演示样本 · 非真实证件`. C2PA validity is provenance evidence and must not be described as proof that image content is real, safe or AI-generated.

The benchmark has two independent axes: authenticity/provenance and visible content safety. A real photograph may still be unsafe, and an AI-generated image may be safe. Public images are admitted only when the per-image license and source URL are recorded. Dataset code licenses do not automatically grant redistribution rights for image pixels.

The 2026-08-05 synthetic additions cover fictional personal data exposure, phishing/credential collection, child schedule exposure and a non-graphic self-harm warning scene. All visible identities, organizations, addresses and credentials are fictional. Full-resolution originals remain under ignored `raw/`; the dashboard receives compressed derivatives only.
