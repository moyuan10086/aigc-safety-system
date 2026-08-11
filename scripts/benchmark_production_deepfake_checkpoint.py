#!/usr/bin/env python3
"""Compare a DFDet checkpoint using the production face-alignment pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from services import deepfake_service  # noqa: E402


def images(root: Path, limit: int) -> list[Path]:
    candidates = sorted(
        path
        for path in root.rglob("*")
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )
    selected: list[Path] = []
    seen_parents: set[Path] = set()
    for path in candidates:
        if path.parent in seen_parents:
            continue
        selected.append(path)
        seen_parents.add(path.parent)
        if len(selected) == limit:
            break
    if len(selected) < limit:
        selected_set = set(selected)
        selected.extend(path for path in candidates if path not in selected_set)
    return selected[:limit]


def auc(labels: np.ndarray, scores: np.ndarray) -> float:
    positives = scores[labels == 1]
    negatives = scores[labels == 0]
    comparisons = (positives[:, None] > negatives[None, :]).sum()
    ties = (positives[:, None] == negatives[None, :]).sum()
    return float((comparisons + ties * 0.5) / (len(positives) * len(negatives)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-dir", type=Path, required=True)
    parser.add_argument("--fake-dir", type=Path, required=True)
    parser.add_argument("--limit-per-class", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    samples = [(path, 0) for path in images(args.real_dir, args.limit_per_class)]
    samples += [(path, 1) for path in images(args.fake_dir, args.limit_per_class)]
    rows = []
    for path, label in samples:
        result = deepfake_service.detect(str(path))
        rows.append(
            {
                "path": str(path),
                "label": label,
                "score": result["score"],
                "decision": result["label"],
                "status": result["status"],
            }
        )

    labels = np.asarray([row["label"] for row in rows])
    scores = np.asarray([row["score"] for row in rows])
    predictions = (scores >= 0.5).astype(int)
    output = {
        "count": len(rows),
        "count_per_class": len(rows) // 2,
        "accuracy_at_0_50": float((predictions == labels).mean()),
        "auc": auc(labels, scores),
        "real_score_mean": float(scores[labels == 0].mean()),
        "fake_score_mean": float(scores[labels == 1].mean()),
        "operational_decisions": {
            name: sum(row["decision"] == name for row in rows)
            for name in ("real", "review", "fake", "inconclusive")
        },
        "rows": rows,
    }
    serialized = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
