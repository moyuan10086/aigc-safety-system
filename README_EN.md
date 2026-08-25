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
- Model weights and OCR dependencies listed in `backend/pyproject.toml`

### Configuration

```bash
cp backend/.env.example backend/.env
```

Keep API keys and model endpoints in the local `.env` file. Do not commit secrets, uploaded files, model weights, or evidence databases.

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
- [`docs/goal-acceptance-audit-20260804.md`](docs/goal-acceptance-audit-20260804.md): acceptance record

## Contact

Project contact: `2572045628@qq.com`

## License

This project is licensed under the [MIT License](LICENSE).
