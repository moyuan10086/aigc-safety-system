from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import threading
import time
from pathlib import Path

EVALUATIONS_DIR = Path(__file__).resolve().parents[1]
if str(EVALUATIONS_DIR) not in sys.path:
    sys.path.insert(0, str(EVALUATIONS_DIR))

import run_review_campaign  # noqa: E402


def _case(case_id: str, text: str | None = None) -> dict[str, str | None]:
    return {
        "id": case_id,
        "prompt": text or f"private-{case_id}",
        "response": "",
        "mode": "prompt",
        "expected": "must-not-appear",
        "expected_category": "must-not-appear",
    }


def _create_db(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE audit_events (
                id TEXT PRIMARY KEY, event_type TEXT NOT NULL, outcome TEXT NOT NULL,
                content_hash TEXT
            );
            CREATE TABLE audit_evidence (event_id TEXT PRIMARY KEY);
            CREATE TABLE guardrail_shadow_reviews (event_id TEXT PRIMARY KEY);
            """
        )


def _persist(path: Path, content_hash: str, event_id: str) -> None:
    with sqlite3.connect(path, timeout=10) as connection:
        connection.execute(
            "INSERT INTO audit_events VALUES (?, 'guardrail.check', 'allowed', ?)",
            (event_id, content_hash),
        )
        connection.execute("INSERT INTO audit_evidence VALUES (?)", (event_id,))


def _sender(path: Path, *, fail_first: bool = False, concurrency: dict | None = None):
    attempts: dict[str, int] = {}
    lock = threading.Lock()

    def send(_endpoint: str, payload: dict[str, str], _timeout: float) -> dict:
        content_hash = hashlib.sha256(
            f"{payload['prompt']}\n{payload['response']}".encode("utf-8")
        ).hexdigest()
        with lock:
            attempts[content_hash] = attempts.get(content_hash, 0) + 1
            if concurrency is not None:
                concurrency["active"] += 1
                concurrency["maximum"] = max(concurrency["maximum"], concurrency["active"])
        try:
            if fail_first and attempts[content_hash] == 1:
                raise run_review_campaign.CampaignRequestError("http_503", status_code=503, retryable=True)
            if concurrency is not None:
                time.sleep(0.01)
            _persist(path, content_hash, f"event-{content_hash[:16]}")
            return {
                "verdict": "safe",
                "risk_code": "SAFE",
                "categories": [],
                "engine": {
                    "components": {
                        "rag": "ok", "qwen3guard": "ok", "singguard": "ok", "xgboost_shadow": "ok"
                    },
                    "timings_ms": {"rag": 1.0, "qwen3guard": 2.0},
                },
                "shadow_evaluation": {"status": "ok", "decision": "pass"},
            }
        finally:
            if concurrency is not None:
                with lock:
                    concurrency["active"] -= 1

    send.attempts = attempts
    return send


def test_deduplicates_existing_hash_and_stops_at_target(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _create_db(db)
    duplicate = _case("duplicate")
    duplicate_hash = hashlib.sha256(b"private-duplicate\n").hexdigest()
    _persist(db, duplicate_hash, "existing")
    sender = _sender(db)

    report = run_review_campaign.run_campaign(
        endpoint="http://local/check",
        audit_db=db,
        target=2,
        cases=[duplicate, _case("new"), _case("unused")],
        sender=sender,
        retry_delay=0,
    )

    assert report["campaign"]["completed"] is True
    assert report["campaign"]["persisted_this_run"] == 1
    assert report["review_pool"]["final_unique_hashes"] == 2
    assert duplicate_hash not in sender.attempts


def test_resume_adds_only_missing_samples_and_never_writes_labels(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _create_db(db)
    sender = _sender(db)
    cases = [_case("one"), _case("two"), _case("three")]

    first = run_review_campaign.run_campaign(
        endpoint="http://local/check", audit_db=db, target=2, cases=cases,
        sender=sender, retry_delay=0,
    )
    second = run_review_campaign.run_campaign(
        endpoint="http://local/check", audit_db=db, target=3, cases=cases,
        sender=sender, retry_delay=0,
    )

    assert first["campaign"]["persisted_this_run"] == 2
    assert second["campaign"]["persisted_this_run"] == 1
    assert second["review_pool"]["human_labels_before"] == 0
    assert second["review_pool"]["human_labels_after"] == 0
    assert second["review_pool"]["campaign_writes_human_labels"] is False


def test_caps_concurrency_at_two(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _create_db(db)
    concurrency = {"active": 0, "maximum": 0}
    report = run_review_campaign.run_campaign(
        endpoint="http://local/check",
        audit_db=db,
        target=5,
        workers=99,
        cases=[_case(str(index)) for index in range(6)],
        sender=_sender(db, concurrency=concurrency),
        retry_delay=0,
    )

    assert report["campaign"]["workers"] == 2
    assert concurrency["maximum"] == 2
    assert report["review_pool"]["final_unique_hashes"] == 5


def test_retries_transient_failure_and_accounts_for_attempts(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _create_db(db)
    report = run_review_campaign.run_campaign(
        endpoint="http://local/check",
        audit_db=db,
        target=1,
        cases=[_case("retry")],
        sender=_sender(db, fail_first=True),
        max_retries=2,
        retry_delay=0,
    )

    assert report["campaign"]["completed"] is True
    assert report["campaign"]["retry_count"] == 1
    assert report["results"][0]["attempts"] == 2
    assert report["results"][0]["status"] == "persisted"


def test_report_is_metadata_only_and_preflight_blocks_degradation(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _create_db(db)
    secret = "raw-secret-prompt-that-must-not-leak"

    def degraded_sender(_endpoint: str, payload: dict[str, str], _timeout: float) -> dict:
        content_hash = hashlib.sha256(
            f"{payload['prompt']}\n{payload['response']}".encode("utf-8")
        ).hexdigest()
        _persist(db, content_hash, "degraded-event")
        return {
            "verdict": "safe",
            "risk_code": "SAFE",
            "categories": [],
            "evidence": [{"excerpt": secret}],
            "redline_answer": secret,
            "engine": {"components": {
                "rag": "ok", "qwen3guard": "ok", "singguard": "unavailable", "xgboost_shadow": "ok"
            }},
        }

    report = run_review_campaign.run_campaign(
        endpoint="http://local/check", audit_db=db, target=3,
        cases=[_case("secret", secret), _case("unused")], sender=degraded_sender,
        retry_delay=0,
    )
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["campaign"]["preflight"]["passed"] is False
    assert report["campaign"]["requests_completed"] == 1
    assert report["campaign"]["completed"] is False
    assert secret not in serialized
    assert "must-not-appear" not in serialized
    assert all("prompt" not in item and "response" not in item and "expected" not in item for item in report["results"])
