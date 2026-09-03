<div align="center">

# AIGC Safety Review System

### Authenticity detection, content review, and security auditing for images, text, and Agents

[![GitHub](https://img.shields.io/badge/GitHub-moyuan10086%2Faigc--safety--system-181717?logo=github)](https://github.com/moyuan10086/aigc-safety-system)
[![Backend](https://img.shields.io/badge/backend-FastAPI-009688)](#technology-stack)
[![Frontend](https://img.shields.io/badge/frontend-Vue%203-42b883)](#technology-stack)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Image authenticity · AI provenance · content safety · RAG policy retrieval · LLM guardrails · Agent tool controls

</div>

[简体中文](README.md) | English

## Overview

AIGC Safety System is an auditable review platform for AI-generated and manipulated content. It combines per-face Deepfake analysis, multimodal explanations, provenance evidence, OCR/RAG policy review, LLM guardrails, Agent tool gates, and encrypted audit records in one workflow.

The system keeps authenticity, content safety, and provenance as separate evidence dimensions. A detected AI-generation signal is not treated as a policy violation, and a provenance signal is not treated as proof of authenticity.

## Highlights

- Per-face Deepfake analysis with CLIP ViT-L/14, YuNet five-point alignment, conservative thresholds, and explicit `review`/`inconclusive` states.
- Structured multimodal evidence with verdict, confidence, suspicious regions, and reviewer-facing explanations.
- Hybrid policy retrieval using multilingual MiniLM embeddings and Chinese lexical matching, with source and chunk metadata preserved for traceability.
- Layered guardrails for prompt input, model output, and Agent tool calls. FAST, STANDARD, and STRICT profiles select different expert combinations.
- Qwen3Guard for general content safety and SingGuard-NSFA for Agent-oriented risks such as prompt injection, sensitive-data theft, malicious code, dangerous tool use, and resource abuse.
- SHA-256, C2PA/Content Credentials, EXIF/XMP/IPTC/ICC metadata, encrypted evidence storage, and downloadable JSON/Markdown reports.

## Screenshots

| Image review | Runtime guardrails | Readiness status |
| :---: | :---: | :---: |
| ![Image review](docs/competition-materials/screenshots-20260814/01-detect-workspace-20260814.png) | ![Runtime guardrails](docs/competition-materials/screenshots-20260814/04-guardrail-current-20260814.png) | ![Readiness](docs/competition-materials/screenshots-20260814/03-settings-readiness-current-20260814.png) |

## Technology Stack

| Layer | Technologies |
| --- | --- |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| Frontend | Vue 3, TypeScript, Vite, Element Plus |
| Vision | PyTorch, CLIP, YuNet, OpenCV, Pillow |
| OCR/RAG | PaddleOCR, ChromaDB, Sentence-Transformers |
| Audit | SQLite, AES-GCM evidence storage, SHA-256 hash chain |

## Quick Start

### Requirements

- Python 3.11+
- Node.js 20+
- `uv` or an equivalent Python environment
- Runtime libraries for vision, YuNet, and OCR listed in `backend/pyproject.toml`; model weights must be provisioned separately as described below

### Configuration

```bash
cp backend/.env.example backend/.env
```

Keep API keys and model endpoints in the local `.env` file. Do not commit secrets, uploaded files, model weights, or evidence databases.

### Model weights and private dependencies

This repository publishes source code, configuration templates, and documentation only. It does not distribute model weights through Git. Some checkpoints are private project artifacts or are subject to third-party licenses and access controls. When distribution is authorized, host them in a private or gated Hugging Face / ModelScope repository, or in an internal artifact registry, rather than committing them to Git. The repository `.gitignore` excludes all `weights/` and cache directories.

| Capability | Runtime dependency | Provisioning |
| --- | --- | --- |
| Deepfake detection | Project-trained CLIP ViT-L/14 checkpoint | Download an authorized checkpoint from Hugging Face, ModelScope, or an internal registry, then set `DEEPFAKE_MODEL_PATH`; set `DEEPFAKE_FACE_MODEL_PATH` for a custom face detector when needed |
| Chinese semantic retrieval | Sentence-Transformers / MiniLM model | Download or mount it in the target environment through your organization's approved process; do not commit the cache |
| Qwen3Guard and SingGuard | Separate inference services and their model weights | Configure `*_BASE_URL`, `*_MODEL`, and `*_API_KEY`; keep weights on the inference-service host |
| XGBoost Shadow, NudeNet, and other optional modules | Local model files | Set the corresponding `*_MODEL_PATH`; an unconfigured module reports `unavailable` or `degraded` |

The application can still run without private weights, including the frontend, API, deterministic rules, audit, and review workflows. Weight-dependent capabilities report an explicit degraded state instead of fabricating a result. For Hugging Face or ModelScope hosting, use a private repository, access token, and pinned revision; download weights on the deployment host and point the relevant environment variable to the local path. Use only weights you are authorized to deploy and follow each model's license and service terms.

Public model repositories: [Hugging Face](https://huggingface.co/moyuan10086/aigc-safety-models) · [ModelScope](https://modelscope.cn/models/moyuan10086/aigc-safety-models)

### Clone (with submodules)

```bash
# Clone recursively to fetch detection model submodules
git clone --recursive https://github.com/moyuan10086/aigc-safety-system.git
cd aigc-safety-system

# If already cloned without submodules:
git submodule update --init --recursive
```

### Run locally

```bash
cd frontend
npm install
npm run build
cd ../backend
uv sync
uv run main.py
```

The default local endpoint is `http://localhost:8010`.

On Windows, `start.bat` can be used as a convenience launcher.

## Guardrail Profiles

| Profile | Components | Use case |
| --- | --- | --- |
| FAST | deterministic rules; XGBoost Shadow runs out of band | low-latency screening |
| STANDARD | rules, RAG, Qwen3Guard, SingGuard | default online review |
| STRICT | STANDARD plus MLLM review | complex or disputed cases |

Shadow evaluation records disagreement and confidence for analysis. It never overrides the production guardrail result. Component failures are surfaced as `unavailable`, `inconclusive`, or `degraded`; they are not silently converted into a safe decision.

## API

The public API is under `/api/v1` and requires a tenant-scoped API key. Main scopes include `guardrail:check`, `guardrail:agent`, `content:check`, `image:deepfake`, `image:provenance`, and `report:read`.

See [`docs/open-api-manual.md`](docs/open-api-manual.md) for request schemas and examples.

## Testing

```bash
cd backend
uv run pytest -q
cd ../frontend
npm run build
```

## Project Materials

The project received the Third Prize in the 19th National College Student Information Security Competition (作品赛) and the 3rd Great Wall Cup Cyber-Digital-Intelligence Security Competition (作品赛).

Watermarked competition materials are available in [`docs/competition-materials/`](docs/competition-materials/):

- [Presentation PDF](docs/competition-materials/项目演示文稿-获奖分享版.pdf)
- [Project report PDF](docs/competition-materials/项目作品报告-获奖分享版.pdf)
- [Screenshots](docs/competition-materials/screenshots-20260814/)
- [Demo video, 5:40](docs/competition-materials/演示视频-获奖分享版.mp4)

The sharing copies carry the repository URL and project contact watermark. The live demonstration URL is intentionally not published in this repository.

## Documentation

- [`docs/open-api-manual.md`](docs/open-api-manual.md): external API manual
- [`docs/operator-manual.md`](docs/operator-manual.md): operator and review workflow
- [`docs/provenance-api-quickstart.md`](docs/provenance-api-quickstart.md): provenance verification quick start
- [`docs/model-catalog.md`](docs/model-catalog.md): complete model catalog, provenance, and provisioning notes
- [`docs/goal-acceptance-audit-20260804.md`](docs/goal-acceptance-audit-20260804.md): acceptance record

## Contact

Project contact: `2572045628@qq.com`

## License

This project is licensed under the [MIT License](LICENSE).
