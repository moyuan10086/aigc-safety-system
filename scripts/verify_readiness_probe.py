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
    response = httpx.post(
        f"{args.base_url.rstrip('/')}/api/system/readiness/probe",
        cookies={COOKIE_NAME: token},
        timeout=args.timeout,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {"status": "invalid_json", "http_status": response.status_code}

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
