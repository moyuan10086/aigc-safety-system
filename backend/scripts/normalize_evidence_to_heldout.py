"""Convert recorded image-safety evidence into label-backed heldout JSONL.

The source evidence must contain human/reference labels. This script never
infers labels from model verdicts; absent categories become score 0 only after
the reference label says the sample is negative for the selected task.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _has_label(labels: list[str], positive_label: str) -> bool:
    return any(label == positive_label or label.startswith(f"{positive_label}_") for label in labels)


def _score_for_category(result: dict, category: str) -> float:
    scores = [
        float(item.get("confidence", 0))
        for item in result.get("categories", [])
        if item.get("code") == category
    ]
    return max(scores, default=0.0)


def normalize(source: dict, *, task: str, positive_label: str) -> list[dict]:
    records: list[dict] = []
    category = task.split(":", 1)[1] if task.startswith("content_safety:") else None
    for sample in source.get("samples", []):
        labels = [str(value) for value in sample.get("reference_labels", [])]
        result = sample.get("result") or {}
        if category is None:
            raise ValueError("only content_safety:<category> normalization is supported")
        label = int(_has_label(labels, positive_label))
        score = _score_for_category(result, category)
        records.append({
            "sample_id": sample["sample_id"],
            "task": task,
            "label": label,
            "score": score,
            "dataset": source.get("schema", "recorded-evidence"),
            "split": "recorded",
            "model_version": result.get("model") or source.get("model"),
            "source_sha256": sample.get("sha256"),
            "reference_labels": labels,
        })
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize recorded evidence to heldout JSONL")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--task", required=True, help="content_safety:<category>")
    parser.add_argument("--positive-label", required=True)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    records = normalize(source, task=args.task, positive_label=args.positive_label)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    print(json.dumps({"record_count": len(records), "task": args.task, "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
