#!/usr/bin/env python3
"""Read production human-review progress without claiming or labeling samples."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from services import audit_log_service, auth_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print a privacy-safe, read-only review-campaign snapshot."
    )
    parser.add_argument("--reviewer", default="")
    args = parser.parse_args()

    reviewer = args.reviewer.strip() or auth_service.current_user()["username"]
    result = audit_log_service.shadow_review_statistics(
        hours=168,
        reviewer=reviewer,
        queue_limit=1,
    )
    public = {
        "schema_version": "1.0",
        "read_only": True,
        "reviewer": reviewer,
        "target_labels": result["target_labels"],
        "pilot_target_labels": result["pilot_target_labels"],
        "eligible_samples": result["eligible_samples"],
        "pending_reviews": result["pending_reviews"],
        "submitted_labels": result["reviewed_count"],
        "verified_labels": result["verified_review_count"],
        "unverified_labels": result["unverified_review_count"],
        "review_integrity_complete": result["review_integrity_complete"],
        "pilot_remaining_count": result["pilot_remaining_count"],
        "pilot_completed": result["pilot_completed"],
        "remaining_count": result["remaining_count"],
        "target_completed": result["target_completed"],
        "active_claims": result["active_claims"],
        "claimed_by_reviewer": result["claimed_by_me_count"],
        "reviewer_submitted_count": result["reviewer_reviewed_count"],
        "review_labels": result["review_labels"],
        "reviewer_counts": result["reviewer_counts"],
        "privacy": {
            "event_ids_included": False,
            "content_hashes_included": False,
            "raw_content_included": False,
            "claim_or_label_written": False,
        },
    }
    print(json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
