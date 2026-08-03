"""Verify production trajectory evidence isolation without printing plaintext."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services import audit_log_service  # noqa: E402
from test_agent_trajectory_production import CASES, _raw_values  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--audit-db", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    event_ids = [item["audit_event_id"] for item in report["results"]]
    events = [audit_log_service.get_event(event_id) for event_id in event_ids]
    evidence = [audit_log_service.get_evidence(event_id) for event_id in event_ids]
    markers = [_raw_values(case) for case in CASES]
    event_text = json.dumps(events, ensure_ascii=False)
    database_bytes = Path(args.audit_db).read_bytes()

    result = {
        "events_found": sum(bool(item) for item in events),
        "evidence_encrypted_at_rest": all(
            item and item.get("encrypted_at_rest") for item in evidence
        ),
        "evidence_preserved": all(
            all(marker in (item or {}).get("prompt", "") for marker in case_markers)
            for case_markers, item in zip(markers, evidence, strict=True)
        ),
        "ordinary_logs_redacted": not any(
            marker in event_text for case_markers in markers for marker in case_markers
        ),
        "sqlite_plaintext_absent": not any(
            marker.encode("utf-8") in database_bytes
            for case_markers in markers
            for marker in case_markers
        ),
    }
    result["passed"] = (
        result["events_found"] == len(event_ids)
        and all(value for key, value in result.items() if key != "events_found")
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
