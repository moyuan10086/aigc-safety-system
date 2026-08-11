"""Run the image-safety model on a locally obtained UnsafeBench export.

This adapter intentionally does not download from Hugging Face or bypass a
dataset agreement. The input manifest must have been obtained lawfully and
contain only local paths. Output keeps labels and hashes, never image bytes.

Accepted manifest formats:

* JSONL, one row per sample, or
* JSON with a ``samples`` list.

Each row needs ``sample_id``, ``image_path`` (or ``file``), and
``safety_label`` (``Safe``/``Unsafe``). ``category`` and ``source`` are
preserved when present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from services import mllm_service  # noqa: E402


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("samples"), list):
        return payload["samples"]
    raise ValueError("manifest must be JSONL, a JSON list, or an object with samples")


def _label(value: Any) -> int:
    normalized = str(value).strip().lower()
    if normalized == "unsafe":
        return 1
    if normalized == "safe":
        return 0
    raise ValueError("safety_label must be Safe or Unsafe")


def _path(root: Path, value: Any) -> Path:
    candidate = Path(str(value))
    return candidate if candidate.is_absolute() else (root / candidate).resolve()


def run(manifest: Path, output: Path, *, limit: int | None = None, heldout_output: Path | None = None) -> dict[str, Any]:
    rows = _read_rows(manifest)
    if limit is not None:
        rows = rows[:limit]
    results: list[dict[str, Any]] = []
    for row in rows:
        sample_id = str(row.get("sample_id") or row.get("id") or "").strip()
        image = _path(manifest.parent, row.get("image_path") or row.get("file"))
        if not sample_id or not image.is_file():
            raise ValueError(f"missing sample_id or local image: {sample_id or image}")
        started = time.perf_counter()
        result = mllm_service.analyze_content_safety(str(image))
        latency_ms = round((time.perf_counter() - started) * 1000)
        results.append({
            "sample_id": sample_id,
            "task": "content_safety:unsafe",
            "label": _label(row.get("safety_label")),
            "score": float(result.get("risk_score", 0.0)),
            "category": row.get("category"),
            "source": row.get("source"),
            "dataset": "UnsafeBench",
            "split": row.get("split", "test"),
            "model_version": result.get("model"),
            "policy_version": result.get("policy_version"),
            "source_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "latency_ms": latency_ms,
            "result": result,
        })
    payload = {
        "schema": "aigc.image-content-safety.unsafebench.evidence.v1",
        "dataset": "UnsafeBench",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(results),
        "privacy": {"original_images_in_output": False, "raw_provider_response_in_output": False},
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if heldout_output:
        heldout_output.parent.mkdir(parents=True, exist_ok=True)
        heldout_output.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results),
            encoding="utf-8",
        )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local UnsafeBench image-safety evaluation")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--heldout-output", type=Path, help="Optional JSONL consumed by evaluate_detection_scores.py")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    payload = run(args.manifest, args.output, limit=args.limit, heldout_output=args.heldout_output)
    print(json.dumps({"dataset": payload["dataset"], "sample_count": payload["sample_count"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
