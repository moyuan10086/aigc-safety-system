import os
from pathlib import Path
from dotenv import load_dotenv
import socket

load_dotenv(Path(__file__).parent / ".env")

# MLLM API (OpenAI-compatible)
MLLM_API_KEY = os.getenv("MLLM_API_KEY", "")
MLLM_BASE_URL = os.getenv("MLLM_BASE_URL", "https://api.openai.com/v1")
MLLM_MODEL = os.getenv("MLLM_MODEL", "gpt-4o")

# Text guardrail feature switches. Rule-based checks are always enabled; local
# RAG and remote MLLM analysis are optional enrichment layers.
GUARDRAIL_ENABLE_RAG = os.getenv("GUARDRAIL_ENABLE_RAG", "true").lower() in {
    "1", "true", "yes", "on"
}
GUARDRAIL_ENABLE_MLLM = os.getenv("GUARDRAIL_ENABLE_MLLM", "false").lower() in {
    "1", "true", "yes", "on"
}

# Deepfake detection model path
DEEPFAKE_MODEL_PATH = os.getenv("DEEPFAKE_MODEL_PATH", "../deepfake-detection/weights/model.ckpt")

# ChromaDB path
CHROMA_PATH = os.getenv("CHROMA_PATH", "./rag_db")

# Sensitive lexicon path
LEXICON_PATH = os.getenv("LEXICON_PATH", "../../数字人前端/backend/Sensitive-lexicon/Vocabulary")


def _check_proxy(host: str = "127.0.0.1", port: int = 7897) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


PROXY_URL = "http://127.0.0.1:7897" if _check_proxy() else None
