# Demo sample handling

`raw/` contains controlled originals used for local evaluation and is excluded from Git. Public UI assets under `frontend/public/demo-samples/` contain only selected non-sensitive samples or masked thumbnails.

The structured evidence file `../image-content-safety-local-20260805.json` records the source class, reference label, SHA-256, latency and real model result without embedding raw image bytes. User uploads are never added to this catalog automatically.

Synthetic identity documents must be marked `AI 合成演示样本 · 非真实证件`. C2PA validity is provenance evidence and must not be described as proof that image content is real, safe or AI-generated.
