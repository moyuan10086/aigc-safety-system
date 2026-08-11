"""Run label-backed calibration and discrimination metrics on a JSONL dataset.

Example:
  uv run python scripts/evaluate_detection_scores.py --input ../docs/evaluation/heldout.example.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow both `cd backend && python scripts/...` and project-root execution.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.evaluation_service import evaluate_by_task


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate held-out detection scores")
    parser.add_argument("--input", required=True, type=Path, help="JSONL with task, label, score and sample_id")
    parser.add_argument("--output", type=Path, help="Optional JSON evidence report path")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    records = []
    for line_number, line in enumerate(args.input.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSON at line {line_number}: {exc.msg}") from exc
        for key in ("sample_id", "task", "label", "score"):
            if key not in record:
                raise SystemExit(f"missing {key!r} at line {line_number}")
        records.append(record)

    input_bytes = args.input.read_bytes()
    protocol = {
        "datasets": sorted({str(record.get("dataset")) for record in records if record.get("dataset")}),
        "splits": sorted({str(record.get("split")) for record in records if record.get("split")}),
        "model_versions": sorted({str(record.get("model_version")) for record in records if record.get("model_version")}),
        "label_authority": "held-out manifest labels; never inferred from model verdicts",
    }
    report = {
        "report_type": "heldout_detection_score_evaluation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": args.input.name,
        "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "record_count": len(records),
        "protocol": protocol,
        "tasks": evaluate_by_task(records, threshold=args.threshold),
        "boundary": "Only independent, human-labelled held-out samples can support a calibration claim.",
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
