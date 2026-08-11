"""Convert deepfake benchmark inference output to heldout JSONL.

The input is produced by scripts/deepfake_multidataset_benchmark.py. Labels
and scores are copied verbatim; this script does not calculate or rewrite
metrics.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def normalize(source: dict, *, task: str = "deepfake") -> list[dict]:
    records: list[dict] = []
    for index, row in enumerate(source.get("results", [])):
        if "label" not in row or "p_fake" not in row:
            raise ValueError(f"result {index} requires label and p_fake")
        records.append({
            "sample_id": row.get("sample_id") or row.get("path") or f"row-{index}",
            "task": task,
            "label": int(row["label"]),
            "score": float(row["p_fake"]),
            "dataset": row.get("dataset") or source.get("dataset") or "unknown",
            "split": source.get("split") or "test",
            "model_version": source.get("model_source"),
            "source_sha256": source.get("model_sha256"),
        })
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize deepfake benchmark results")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    records = normalize(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    print(json.dumps({"record_count": len(records), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
