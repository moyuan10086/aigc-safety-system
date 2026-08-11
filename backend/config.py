import os
from pathlib import Path
from dotenv import load_dotenv
import socket

load_dotenv(Path(__file__).parent / ".env")

# MLLM API (OpenAI-compatible)
MLLM_API_KEY = os.getenv("MLLM_API_KEY", "")
MLLM_BASE_URL = os.getenv("MLLM_BASE_URL", "https://api.openai.com/v1")
MLLM_MODEL = os.getenv("MLLM_MODEL", "gpt-4o")
MLLM_TIMEOUT_SECONDS = float(os.getenv("MLLM_TIMEOUT_SECONDS", "90"))

# Local adult-content specialist. It starts in shadow mode until thresholds are
# calibrated on a representative, lawfully obtained evaluation set.
NUDENET_ENABLED = os.getenv("NUDENET_ENABLED", "false").lower() in {"1", "true", "yes"}
NUDENET_MODEL_PATH = os.getenv("NUDENET_MODEL_PATH", "").strip()
NUDENET_SHADOW_ONLY = os.getenv("NUDENET_SHADOW_ONLY", "true").lower() in {"1", "true", "yes"}
NUDENET_THRESHOLD = max(0.0, min(1.0, float(os.getenv("NUDENET_THRESHOLD", "0.6"))))

# Optional official UnsafeBench/PerspectiveVision-compatible specialist. The
# repository is an evaluation framework, so production stays disabled until a
# separately deployed inference endpoint is configured.
UNSAFE_BENCH_ENABLED = os.getenv("UNSAFE_BENCH_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
UNSAFE_BENCH_ENDPOINT = os.getenv("UNSAFE_BENCH_ENDPOINT", "").strip()
UNSAFE_BENCH_MODEL = os.getenv("UNSAFE_BENCH_MODEL", "multiheaded").strip()
UNSAFE_BENCH_TIMEOUT_SECONDS = float(os.getenv("UNSAFE_BENCH_TIMEOUT_SECONDS", "30"))

# Text generation model. It can point to a dedicated local vLLM service while
# image analysis continues to use the MLLM settings above.
CHAT_MODEL_API_KEY = os.getenv("CHAT_MODEL_API_KEY", MLLM_API_KEY)
CHAT_MODEL_BASE_URL = os.getenv("CHAT_MODEL_BASE_URL", MLLM_BASE_URL)
CHAT_MODEL_NAME = os.getenv("CHAT_MODEL_NAME", MLLM_MODEL)
CHAT_MODEL_TIMEOUT_SECONDS = float(os.getenv("CHAT_MODEL_TIMEOUT_SECONDS", "60"))
CHAT_MODEL_MAX_TOKENS = int(os.getenv("CHAT_MODEL_MAX_TOKENS", "700"))
GUARDRAIL_CHAT_RATE_LIMIT = int(os.getenv("GUARDRAIL_CHAT_RATE_LIMIT", "10"))

# Public demos use server-managed configuration. Runtime writes are disabled by
# default and require an explicit administrator token when enabled.
SYSTEM_CONFIG_WRITABLE = os.getenv("SYSTEM_CONFIG_WRITABLE", "false").lower() in {
    "1", "true", "yes", "on"
}
SYSTEM_ADMIN_TOKEN = os.getenv("SYSTEM_ADMIN_TOKEN", "")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://aigc.49.51.248.227.sslip.io",
    ).split(",")
    if origin.strip()
]

# Operator authentication. Passwords are stored as PBKDF2 digests; the session
# secret signs HttpOnly cookies and must be unique in production.
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "")
AUTH_DISPLAY_NAME = os.getenv("AUTH_DISPLAY_NAME", "安全审核员")
AUTH_ROLE = os.getenv("AUTH_ROLE", "operator")
AUTH_PASSWORD_HASH = os.getenv("AUTH_PASSWORD_HASH", "")
# Optional JSON array of additional operators. The legacy AUTH_* account stays
# valid during migration so existing sessions and deployment scripts keep working.
AUTH_OPERATORS_JSON = os.getenv("AUTH_OPERATORS_JSON", "")
AUTH_SESSION_SECRET = os.getenv("AUTH_SESSION_SECRET", "")
AUTH_SESSION_TTL_SECONDS = int(os.getenv("AUTH_SESSION_TTL_SECONDS", "28800"))
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() in {
    "1", "true", "yes", "on"
}

# Short-lived, exact-action approvals for Agent tool execution. A dedicated
# secret can be rotated independently; deployments may fall back to the signed
# operator-session secret to keep the feature fail-closed and easy to operate.
AGENT_APPROVAL_SIGNING_SECRET = (
    os.getenv("AGENT_APPROVAL_SIGNING_SECRET", "") or AUTH_SESSION_SECRET
)
AGENT_APPROVAL_TTL_SECONDS = int(os.getenv("AGENT_APPROVAL_TTL_SECONDS", "300"))
AGENT_APPROVAL_MAX_TTL_SECONDS = int(
    os.getenv("AGENT_APPROVAL_MAX_TTL_SECONDS", "900")
)

# External API access. API keys are stored as one-way HMAC digests in a
# separate SQLite ledger; the plaintext key is returned only at issuance time.
API_KEY_HASH_SECRET = os.getenv("API_KEY_HASH_SECRET", "") or AUTH_SESSION_SECRET
API_KEY_HASH_PREVIOUS_SECRET = os.getenv("API_KEY_HASH_PREVIOUS_SECRET", "")
API_KEY_DB_PATH = os.getenv("API_KEY_DB_PATH", "audit_logs/api_keys.db")
API_KEY_DEFAULT_RATE_LIMIT = int(os.getenv("API_KEY_DEFAULT_RATE_LIMIT", "60"))
API_KEY_DEFAULT_DAILY_QUOTA = int(os.getenv("API_KEY_DEFAULT_DAILY_QUOTA", "5000"))
API_KEY_MAX_RATE_LIMIT = int(os.getenv("API_KEY_MAX_RATE_LIMIT", "600"))
API_KEY_MAX_DAILY_QUOTA = int(os.getenv("API_KEY_MAX_DAILY_QUOTA", "100000"))
API_SCAN_MAX_CONCURRENCY = int(os.getenv("API_SCAN_MAX_CONCURRENCY", "1"))
API_SCAN_MAX_ACTIVE_PER_KEY = int(os.getenv("API_SCAN_MAX_ACTIVE_PER_KEY", "1"))

# Structured, tamper-evident audit trail. Runtime data stays outside Git and is
# queried only through authenticated operator endpoints.
AUDIT_LOG_DB_PATH = os.getenv("AUDIT_LOG_DB_PATH", "audit_logs/audit.db")
AUDIT_LOG_RETENTION_DAYS = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "90"))
AUDIT_STORE_RAW_CONTENT = os.getenv("AUDIT_STORE_RAW_CONTENT", "true").lower() in {
    "1", "true", "yes", "on"
}
AUDIT_CONTENT_KEY = os.getenv("AUDIT_CONTENT_KEY", "") or AUTH_SESSION_SECRET
AUDIT_CONTENT_PREVIOUS_KEY = os.getenv("AUDIT_CONTENT_PREVIOUS_KEY", "")
AUDIT_ARCHIVE_PATH = os.getenv("AUDIT_ARCHIVE_PATH", "audit_archives")

# Text guardrail feature switches. Rule-based checks are always enabled; local
# RAG and remote MLLM analysis are optional enrichment layers.
GUARDRAIL_ENABLE_RAG = os.getenv("GUARDRAIL_ENABLE_RAG", "true").lower() in {
    "1", "true", "yes", "on"
}
GUARDRAIL_ENABLE_MLLM = os.getenv("GUARDRAIL_ENABLE_MLLM", "false").lower() in {
    "1", "true", "yes", "on"
}
GUARDRAIL_ENABLE_QWEN_CLASSIFIER = os.getenv(
    "GUARDRAIL_ENABLE_QWEN_CLASSIFIER", "false"
).lower() in {"1", "true", "yes", "on"}
GUARDRAIL_QWEN_API_KEY = os.getenv("GUARDRAIL_QWEN_API_KEY", "")
GUARDRAIL_QWEN_BASE_URL = os.getenv(
    "GUARDRAIL_QWEN_BASE_URL", "http://127.0.0.1:18200/v1"
)
GUARDRAIL_QWEN_MODEL = os.getenv(
    "GUARDRAIL_QWEN_MODEL", "qwen3guard-gen-0.6b"
)
GUARDRAIL_QWEN_TIMEOUT_SECONDS = float(
    os.getenv("GUARDRAIL_QWEN_TIMEOUT_SECONDS", "15")
)
GUARDRAIL_ENABLE_SINGGUARD_CLASSIFIER = os.getenv(
    "GUARDRAIL_ENABLE_SINGGUARD_CLASSIFIER", "false"
).lower() in {"1", "true", "yes", "on"}
GUARDRAIL_SINGGUARD_API_KEY = os.getenv("GUARDRAIL_SINGGUARD_API_KEY", "")
GUARDRAIL_SINGGUARD_BASE_URL = os.getenv(
    "GUARDRAIL_SINGGUARD_BASE_URL", "http://127.0.0.1:18210/v1"
)
GUARDRAIL_SINGGUARD_MODEL = os.getenv(
    "GUARDRAIL_SINGGUARD_MODEL", "singguard-nsfa-0.8b"
)
GUARDRAIL_SINGGUARD_TIMEOUT_SECONDS = float(
    os.getenv("GUARDRAIL_SINGGUARD_TIMEOUT_SECONDS", "20")
)
GUARDRAIL_PARALLEL_EXPERTS = os.getenv("GUARDRAIL_PARALLEL_EXPERTS", "true").lower() in {
    "1", "true", "yes", "on",
}
GUARDRAIL_EXPERT_MAX_WORKERS = max(
    1,
    min(int(os.getenv("GUARDRAIL_EXPERT_MAX_WORKERS", "4")), 4),
)
GUARDRAIL_ENABLE_XGBOOST_SHADOW = os.getenv(
    "GUARDRAIL_ENABLE_XGBOOST_SHADOW", "false"
).lower() in {"1", "true", "yes", "on"}
GUARDRAIL_XGBOOST_SHADOW_MODULE_PATH = os.getenv(
    "GUARDRAIL_XGBOOST_SHADOW_MODULE_PATH", ""
)
GUARDRAIL_XGBOOST_SHADOW_MODEL_PATH = os.getenv(
    "GUARDRAIL_XGBOOST_SHADOW_MODEL_PATH", ""
)
GUARDRAIL_XGBOOST_SHADOW_SHA256 = os.getenv(
    "GUARDRAIL_XGBOOST_SHADOW_SHA256", ""
).lower()

# Deepfake detector artifacts and decision policy. Runtime artifacts are pinned
# and verified before they can be loaded by the service.
DEEPFAKE_MODEL_PATH = os.getenv(
    "DEEPFAKE_MODEL_PATH", "../deepfake-detection/weights/model.ckpt"
)
DEEPFAKE_MODEL_REPO = os.getenv(
    "DEEPFAKE_MODEL_REPO", "yermandy/deepfake-detection"
)
DEEPFAKE_MODEL_REVISION = os.getenv(
    "DEEPFAKE_MODEL_REVISION", "9a6857ec642deb57373c5437be803a199468b8c6"
)
DEEPFAKE_MODEL_FILENAME = os.getenv("DEEPFAKE_MODEL_FILENAME", "model.ckpt")
DEEPFAKE_MODEL_SHA256 = os.getenv(
    "DEEPFAKE_MODEL_SHA256",
    "57a0d00f2f5b4046afd2c344ff9877a35e8889e075916cf816796c54816c9955",
).strip().lower()
DEEPFAKE_BACKBONE_REVISION = os.getenv(
    "DEEPFAKE_BACKBONE_REVISION", "32bd64288804d66eefd0ccbe215aa642df71cc41"
)
DEEPFAKE_FACE_MODEL_PATH = os.getenv(
    "DEEPFAKE_FACE_MODEL_PATH",
    "../deepfake-detection/weights/face_detection_yunet_2023mar.onnx",
)
DEEPFAKE_FACE_MODEL_URL = os.getenv(
    "DEEPFAKE_FACE_MODEL_URL",
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/"
    "47534e27c9851bb1128ccc0102f1145e27f23f98/"
    "models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
)
DEEPFAKE_FACE_MODEL_SHA256 = os.getenv(
    "DEEPFAKE_FACE_MODEL_SHA256",
    "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
).strip().lower()
DEEPFAKE_REAL_THRESHOLD = float(os.getenv("DEEPFAKE_REAL_THRESHOLD", "0.20"))
DEEPFAKE_FAKE_THRESHOLD = float(os.getenv("DEEPFAKE_FAKE_THRESHOLD", "0.80"))
DEEPFAKE_FACE_MARGIN = float(os.getenv("DEEPFAKE_FACE_MARGIN", "0.15"))
DEEPFAKE_MAX_FACES = max(1, min(int(os.getenv("DEEPFAKE_MAX_FACES", "8")), 32))
DEEPFAKE_CACHE_SIZE = max(1, min(int(os.getenv("DEEPFAKE_CACHE_SIZE", "128")), 1024))

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
