"""Run category-level image safety evaluation from a lawful local manifest.

The manifest is the authority for labels. This adapter never infers a label
from the model verdict, never downloads a dataset, and writes only hashes and
normalized category scores to evidence.

Manifest rows require ``sample_id``, ``image_path`` (or ``file``), and
``reference_labels``. Optional ``dataset_id``, ``split`` and ``source`` are
preserved as non-sensitive provenance.
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

DEFAULT_CATEGORIES = (
    "adult_content",
    "marketing_violation",
    "political_sensitive",
    "weapon_display",
    "violence",
)


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("samples"), list):
        return payload["samples"]
    raise ValueError("manifest must be JSONL, a JSON list, or an object with samples")


def _sample_path(manifest: Path, value: Any) -> Path:
    candidate = Path(str(value))
    return candidate if candidate.is_absolute() else (manifest.parent / candidate).resolve()


def _reference_labels(row: dict[str, Any]) -> set[str]:
    labels = row.get("reference_labels")
    if not isinstance(labels, list):
        raise ValueError("each row needs a reference_labels list; use [] for an explicit negative")
    return {str(label).strip() for label in labels if str(label).strip()}


def _category_score(result: dict[str, Any], category: str) -> float:
    category_scores = result.get("category_scores")
    if isinstance(category_scores, dict) and category in category_scores:
        return max(0.0, min(1.0, float(category_scores[category])))
    scores = [
        float(item.get("confidence", 0.0))
        for item in result.get("categories", [])
        if item.get("code") == category
    ]
    return max(0.0, min(1.0, max(scores, default=0.0)))


def run(
    manifest: Path,
    output: Path,
    *,
    categories: tuple[str, ...] = DEFAULT_CATEGORIES,
    limit: int | None = None,
    heldout_output: Path | None = None,
    checkpoint: Path | None = None,
) -> dict[str, Any]:
    rows = _read_rows(manifest)
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        raise ValueError("manifest contains no samples")
    if len(set(str(row.get("sample_id") or row.get("id") or "") for row in rows)) != len(rows):
        raise ValueError("sample_id values must be unique")

    cached_rows: dict[str, dict[str, Any]] = {}
    if checkpoint and checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            cached = json.loads(line)
            if cached.get("sample_id"):
                cached_rows[str(cached["sample_id"])] = cached

    evidence_rows: list[dict[str, Any]] = []
    heldout_rows: list[dict[str, Any]] = []
    dataset_id = str(rows[0].get("dataset_id") or "local-content-safety")
    for index, row in enumerate(rows, 1):
        sample_id = str(row.get("sample_id") or row.get("id") or "").strip()
        image = _sample_path(manifest, row.get("image_path") or row.get("file"))
        if not sample_id or not image.is_file():
            raise ValueError(f"missing sample_id or local image: {sample_id or image}")
        labels = _reference_labels(row)
        base = cached_rows.get(sample_id)
        if base is None:
            started = time.perf_counter()
            result = mllm_service.analyze_content_safety(str(image))
            latency_ms = round((time.perf_counter() - started) * 1000)
            normalized_categories = [
                {
                    "code": str(item.get("code")),
                    "confidence": round(float(item.get("confidence", 0.0)), 4),
                }
                for item in (result.get("categories") or [])
                if item.get("code") in categories
            ]
            base = {
                "sample_id": sample_id,
                "dataset": dataset_id,
                "split": row.get("split", "test"),
                "source": row.get("source"),
                "source_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "model_version": result.get("model"),
                "policy_version": result.get("policy_version"),
                "latency_ms": latency_ms,
                "risk_score": round(float(result.get("risk_score", 0.0)), 4),
                "verdict": result.get("verdict"),
                "categories": normalized_categories,
                "category_scores": {
                    code: round(float(score), 4)
                    for code, score in (result.get("category_scores") or {}).items()
                    if code in categories
                },
                "score_coverage": result.get("score_coverage"),
                "missing_category_scores": [
                    code for code in (result.get("missing_category_scores") or [])
                    if code in categories
                ],
                "reference_labels": sorted(labels),
            }
            if checkpoint:
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                with checkpoint.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(json.dumps(base, ensure_ascii=False) + "\n")
        print(f"[{index}/{len(rows)}] {sample_id} {'cached' if sample_id in cached_rows else 'completed'}", flush=True)
        evidence_rows.append(base)
        for category in categories:
            heldout_rows.append({
                "sample_id": f"{sample_id}:{category}",
                "task": f"content_safety:{category}",
                "label": int(category in labels),
                "score": _category_score(base, category),
                "dataset": dataset_id,
                "split": row.get("split", "test"),
                "model_version": base.get("model_version"),
                "source_sha256": base["source_sha256"],
            })

    payload = {
        "schema": "aigc.image-content-safety.category-evidence.v1",
        "dataset": dataset_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(evidence_rows),
        "categories": list(categories),
        "privacy": {
            "original_images_in_output": False,
            "raw_provider_response_in_output": False,
            "reference_labels_retained": True,
        },
        "results": evidence_rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if heldout_output:
        heldout_output.parent.mkdir(parents=True, exist_ok=True)
        heldout_output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in heldout_rows), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run category-level local image safety evaluation")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--heldout-output", type=Path)
    parser.add_argument("--checkpoint", type=Path, help="Append-only per-sample checkpoint for safe resume")
    parser.add_argument("--categories", nargs="+", default=list(DEFAULT_CATEGORIES))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    payload = run(
        args.manifest,
        args.output,
        categories=tuple(args.categories),
        limit=args.limit,
        heldout_output=args.heldout_output,
        checkpoint=args.checkpoint,
    )
    print(json.dumps({"dataset": payload["dataset"], "sample_count": payload["sample_count"], "categories": payload["categories"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
