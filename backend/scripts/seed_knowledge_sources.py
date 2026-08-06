"""One-time/idempotent importer for curated red-line knowledge sources."""
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.kb_service import seed_official_sources  # noqa: E402


if __name__ == "__main__":
    print(json.dumps(seed_official_sources(), ensure_ascii=False, indent=2))
