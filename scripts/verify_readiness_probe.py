#!/usr/bin/env python3
"""Run the protected readiness probe without exposing operator credentials."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from services import auth_service  # noqa: E402

COOKIE_NAME = "aigc_operator_session"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Call the authenticated production readiness probe safely."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8010",
        help="Base URL reachable from the application host.",
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    token = auth_service.create_session(auth_service.current_user())
    base_url = args.base_url.rstrip("/")
    with httpx.Client(
        cookies={COOKIE_NAME: token},
        timeout=args.timeout,
    ) as client:
        response = client.post(f"{base_url}/api/system/readiness/probe")
        stats_response = client.get(f"{base_url}/api/audit/stats")
        logs_response = client.get(
            f"{base_url}/api/audit/logs",
            params={
                "event_type": "system.readiness_probe",
                "page": 1,
                "page_size": 1,
            },
        )
    try:
        payload = response.json()
    except ValueError:
        payload = {"status": "invalid_json", "http_status": response.status_code}

    try:
        stats = stats_response.json()
    except ValueError:
        stats = {"http_status": stats_response.status_code}
    try:
        logs = logs_response.json()
    except ValueError:
        logs = {"http_status": logs_response.status_code}

    events = logs.get("items") or logs.get("events") or []
    latest = events[0] if events else {}
    metadata = latest.get("metadata") or {}
    print(
        json.dumps(
            {
                "probe": payload,
                "audit": {
                    "chain_valid": stats.get("chain_valid"),
                    "event_count": stats.get("total", stats.get("event_count")),
                    "latest_probe": {
                        "event_id": latest.get("id"),
                        "outcome": latest.get("outcome"),
                        "attempts": metadata.get("attempts"),
                        "max_attempts": metadata.get("max_attempts"),
                        "recovered_after_retry": metadata.get("recovered_after_retry"),
                        "error_code": metadata.get("error_code"),
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if response.is_success and stats_response.is_success and logs_response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
