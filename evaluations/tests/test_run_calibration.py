from __future__ import annotations

import sys
import time
from pathlib import Path

EVALUATIONS_DIR = Path(__file__).resolve().parents[1]
if str(EVALUATIONS_DIR) not in sys.path:
    sys.path.insert(0, str(EVALUATIONS_DIR))

import run_calibration  # noqa: E402


def _case(case_id: str, expected: str) -> dict[str, str | None]:
    return {
        "id": case_id,
        "prompt": f"private-{case_id}",
        "response": "",
        "mode": "prompt",
        "expected": expected,
        "expected_category": None,
    }


def test_run_caps_workers_and_keeps_report_metadata_only(monkeypatch) -> None:
    cases = [_case("safe", "safe"), _case("unsafe", "unsafe")]

    def check(prompt: str, response: str, mode: str) -> dict:
        del response, mode
        return {
            "verdict": "unsafe" if prompt.endswith("unsafe") else "safe",
            "risk_score": 0.9,
            "categories": [],
            "engine": {
                "components": {"rules": "ok"},
                "timings_ms": {"rules": 1.25, "total": 2.5},
            },
        }

    monkeypatch.setitem(run_calibration.CASE_SETS, "test", cases)
    monkeypatch.setattr(run_calibration, "_load_guardrail", lambda offline: check)

    report = run_calibration.run(False, case_set="test", workers=99)

    assert report["run"]["workers"] == 8
    assert report["primary"]["block_only"]["samples"] == 2
    assert report["primary"]["block_only"]["accuracy"] == 100.0
    assert report["run"]["component_latency_ms"]["rules"]["average"] == 1.25
    assert all("prompt" not in item and "response" not in item for item in report["results"])


def test_run_separates_errors_degradation_and_sla(monkeypatch) -> None:
    cases = [_case("safe-error", "safe"), _case("unsafe-ok", "unsafe")]

    def check(prompt: str, response: str, mode: str) -> dict:
        del response, mode
        if prompt.endswith("safe-error"):
            raise TimeoutError("synthetic timeout")
        time.sleep(0.002)
        return {
            "verdict": "unsafe",
            "risk_score": 0.95,
            "categories": [],
            "engine": {"components": {"qwen3guard": "unavailable"}},
        }

    monkeypatch.setitem(run_calibration.CASE_SETS, "test", cases)
    monkeypatch.setattr(run_calibration, "_load_guardrail", lambda offline: check)

    report = run_calibration.run(False, case_set="test", workers=1, sla_seconds=0.001)

    assert report["run"]["error_count"] == 1
    assert report["run"]["errors"] == {"TimeoutError": 1}
    assert report["run"]["degraded_samples"] == 1
    assert report["run"]["sla_exceeded_count"] == 1
    assert report["primary"]["block_only"]["samples"] == 1
    assert report["primary"]["block_only"]["tp"] == 1
