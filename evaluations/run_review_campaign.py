"""Populate the production human-review pool through the real guardrail API.

The campaign never writes human labels. Raw prompts and responses are sent to
the normal guardrail endpoint, which stores them only in encrypted evidence.
The generated report is metadata-only by construction.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable, Iterable
from urllib import error, request

from blind_cases import BLIND_CASES
from calibration_cases import CASES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_DB = ROOT / "backend" / "audit_logs" / "audit.db"
DEFAULT_REQUIRED_COMPONENTS = ("rag", "qwen3guard", "singguard", "xgboost_shadow")
ELIGIBLE_OUTCOMES = ("allowed", "review", "blocked", "denied")
MAX_WORKERS = 2


class CampaignRequestError(RuntimeError):
    """A sanitized transport failure that is safe to include in reports."""

    def __init__(self, code: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True)
class Candidate:
    case_id: str
    variant: int
    prompt: str
    response: str
    mode: str
    content_hash: str


Sender = Callable[[str, dict[str, str], float], dict[str, Any]]


def _content_hash(prompt: str, response: str) -> str:
    return hashlib.sha256(f"{prompt}\n{response}".encode("utf-8")).hexdigest()


def _neutral_variant(text: str, case_id: str, variant: int) -> str:
    marker = f"[授权安全审核样本 {case_id} / 变体 {variant:02d}]"
    return f"{text}\n\n{marker}"


def candidate_stream(
    cases: Iterable[dict[str, Any]],
    *,
    max_variants: int = 20,
) -> Iterable[Candidate]:
    """Yield the base corpus first, then deterministic traceable variants."""
    selected = list(cases)
    for variant in range(0, max(0, int(max_variants)) + 1):
        for case in selected:
            prompt = str(case.get("prompt") or "")
            response = str(case.get("response") or "")
            if variant:
                if prompt:
                    prompt = _neutral_variant(prompt, str(case["id"]), variant)
                else:
                    response = _neutral_variant(response, str(case["id"]), variant)
            yield Candidate(
                case_id=str(case["id"]),
                variant=variant,
                prompt=prompt,
                response=response,
                mode=str(case.get("mode") or "both"),
                content_hash=_content_hash(prompt, response),
            )


def _connect_read_only(path: Path) -> sqlite3.Connection:
    resolved = path.expanduser().resolve()
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def review_pool_state(path: Path) -> dict[str, Any]:
    placeholders = ",".join("?" for _ in ELIGIBLE_OUTCOMES)
    with _connect_read_only(path) as connection:
        rows = connection.execute(
            f"""
            SELECT audit_events.content_hash
            FROM audit_events
            INNER JOIN audit_evidence ON audit_evidence.event_id = audit_events.id
            WHERE audit_events.event_type = 'guardrail.check'
              AND audit_events.outcome IN ({placeholders})
            """,
            ELIGIBLE_OUTCOMES,
        ).fetchall()
        human_labels = int(
            connection.execute("SELECT COUNT(*) FROM guardrail_shadow_reviews").fetchone()[0]
        )
    hashes = {str(row["content_hash"]) for row in rows if row["content_hash"]}
    return {
        "eligible_events": len(rows),
        "eligible_unique_hashes": len(hashes),
        "content_hashes": hashes,
        "human_labels": human_labels,
    }


def _http_sender(endpoint: str, payload: dict[str, str], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    call = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "aigc-review-campaign/1.0"},
        method="POST",
    )
    try:
        with request.urlopen(call, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise CampaignRequestError(
            f"http_{exc.code}", status_code=exc.code, retryable=exc.code == 429 or exc.code >= 500
        ) from exc
    except error.URLError as exc:
        raise CampaignRequestError("transport_error", retryable=True) from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        code = "timeout" if isinstance(exc, TimeoutError) else "invalid_json"
        raise CampaignRequestError(code, retryable=isinstance(exc, TimeoutError)) from exc
    if not isinstance(value, dict):
        raise CampaignRequestError("invalid_response")
    return value


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * percentile) - 1)
    return round(ordered[index], 3)


def _request_candidate(
    candidate: Candidate,
    *,
    endpoint: str,
    sender: Sender,
    timeout: float,
    max_retries: int,
    retry_delay: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    attempts = 0
    last_error: CampaignRequestError | None = None
    while attempts <= max_retries:
        attempts += 1
        try:
            output = sender(
                endpoint,
                {"prompt": candidate.prompt, "response": candidate.response, "mode": candidate.mode},
                timeout,
            )
            engine = output.get("engine") if isinstance(output.get("engine"), dict) else {}
            shadow = (
                output.get("shadow_evaluation")
                if isinstance(output.get("shadow_evaluation"), dict)
                else {}
            )
            return {
                "case_id": candidate.case_id,
                "variant": candidate.variant,
                "content_hash": candidate.content_hash,
                "status": "api_success",
                "attempts": attempts,
                "retry_count": attempts - 1,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "verdict": str(output.get("verdict") or "unknown")[:32],
                "risk_code": str(output.get("risk_code") or "")[:64] or None,
                "categories": [str(item)[:64] for item in output.get("categories", [])[:20]],
                "components": {
                    str(key)[:64]: str(value)[:32]
                    for key, value in (engine.get("components") or {}).items()
                },
                "component_timings_ms": {
                    str(key)[:64]: round(float(value), 3)
                    for key, value in (engine.get("timings_ms") or {}).items()
                    if isinstance(value, (int, float)) and value >= 0
                },
                "shadow": {
                    key: shadow.get(key)
                    for key in (
                        "status", "decision", "confidence", "agreement", "latency_ms", "risk_type"
                    )
                },
                "error_code": None,
                "http_status": 200,
            }
        except CampaignRequestError as exc:
            last_error = exc
            if not exc.retryable or attempts > max_retries:
                break
            if retry_delay > 0:
                time.sleep(retry_delay * attempts)
        except Exception as exc:
            last_error = CampaignRequestError(type(exc).__name__, retryable=False)
            break
    return {
        "case_id": candidate.case_id,
        "variant": candidate.variant,
        "content_hash": candidate.content_hash,
        "status": "request_failed",
        "attempts": attempts,
        "retry_count": max(0, attempts - 1),
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "verdict": None,
        "risk_code": None,
        "categories": [],
        "components": {},
        "component_timings_ms": {},
        "shadow": {},
        "error_code": last_error.code if last_error else "unknown_error",
        "http_status": last_error.status_code if last_error else None,
    }


def _component_summary(results: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    statuses: dict[str, Counter[str]] = defaultdict(Counter)
    timings: dict[str, list[float]] = defaultdict(list)
    for item in results:
        if item["status"] != "persisted":
            continue
        for component, status in item["components"].items():
            statuses[component][status] += 1
        for component, value in item["component_timings_ms"].items():
            timings[component].append(float(value))
    return (
        {component: dict(values) for component, values in sorted(statuses.items())},
        {
            component: {
                "samples": len(values),
                "average": round(sum(values) / len(values), 3),
                "p95": _percentile(values, 0.95),
            }
            for component, values in sorted(timings.items())
        },
    )


def run_campaign(
    *,
    endpoint: str,
    audit_db: Path,
    target: int = 200,
    workers: int = 2,
    timeout: float = 90.0,
    max_retries: int = 2,
    retry_delay: float = 1.0,
    max_variants: int = 20,
    required_components: Iterable[str] = DEFAULT_REQUIRED_COMPONENTS,
    allow_degraded: bool = False,
    cases: Iterable[dict[str, Any]] | None = None,
    sender: Sender | None = None,
) -> dict[str, Any]:
    """Run a resumable campaign and return a metadata-only report."""
    selected_cases = list(cases if cases is not None else [*CASES, *BLIND_CASES])
    target = max(1, int(target))
    workers = max(1, min(int(workers), MAX_WORKERS))
    max_retries = max(0, min(int(max_retries), 5))
    required = tuple(dict.fromkeys(str(item).strip() for item in required_components if str(item).strip()))
    sender = sender or _http_sender
    initial = review_pool_state(audit_db)
    known_hashes = set(initial["content_hashes"])
    seen_hashes = set(known_hashes)
    candidates = iter(candidate_stream(selected_cases, max_variants=max_variants))
    results: list[dict[str, Any]] = []
    preflight: dict[str, Any] = {"passed": None, "required_components": list(required), "statuses": {}}
    started = time.perf_counter()

    def next_candidates(limit: int) -> list[Candidate]:
        batch: list[Candidate] = []
        while len(batch) < limit:
            try:
                candidate = next(candidates)
            except StopIteration:
                break
            if candidate.content_hash in seen_hashes:
                continue
            seen_hashes.add(candidate.content_hash)
            batch.append(candidate)
        return batch

    while len(known_hashes) < target:
        remaining = target - len(known_hashes)
        batch_limit = 1 if preflight["passed"] is None else min(workers, remaining)
        batch = next_candidates(batch_limit)
        if not batch:
            break
        with ThreadPoolExecutor(max_workers=batch_limit, thread_name_prefix="review-campaign") as pool:
            batch_results = list(pool.map(
                lambda candidate: _request_candidate(
                    candidate,
                    endpoint=endpoint,
                    sender=sender,
                    timeout=max(1.0, float(timeout)),
                    max_retries=max_retries,
                    retry_delay=max(0.0, float(retry_delay)),
                ),
                batch,
            ))
        refreshed = review_pool_state(audit_db)
        persisted_hashes = set(refreshed["content_hashes"])
        for item in batch_results:
            if item["status"] == "api_success":
                if item["content_hash"] in persisted_hashes:
                    item["status"] = "persisted"
                else:
                    item["status"] = "evidence_not_persisted"
                    item["error_code"] = "evidence_not_persisted"
            results.append(item)
        known_hashes = persisted_hashes

        if preflight["passed"] is None:
            persisted = next((item for item in batch_results if item["status"] == "persisted"), None)
            if persisted is None:
                preflight["passed"] = False
                preflight["failure"] = "request_or_persistence_failed"
                break
            statuses = persisted["components"]
            preflight["statuses"] = {component: statuses.get(component, "missing") for component in required}
            degraded = {
                component: status
                for component, status in preflight["statuses"].items()
                if status != "ok"
            }
            preflight["passed"] = not degraded
            if degraded:
                preflight["degraded_components"] = degraded
                if not allow_degraded:
                    break

    final = review_pool_state(audit_db)
    component_statuses, component_timings = _component_summary(results)
    verdicts = Counter(
        str(item["verdict"]) for item in results if item["status"] == "persisted" and item["verdict"]
    )
    errors = Counter(
        str(item["error_code"]) for item in results if item.get("error_code")
    )
    dataset_fingerprint = hashlib.sha256(json.dumps(
        [
            {"id": str(case["id"]), "mode": str(case.get("mode") or "both"),
             "content_hash": _content_hash(str(case.get("prompt") or ""), str(case.get("response") or ""))}
            for case in selected_cases
        ],
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        "schema_version": "1.0",
        "dataset": {
            "name": "calibration+blind",
            "base_samples": len(selected_cases),
            "sha256": dataset_fingerprint,
            "raw_content_in_report": False,
            "synthetic_expected_labels_in_report": False,
        },
        "campaign": {
            "endpoint": endpoint,
            "target_unique_review_samples": target,
            "workers": workers,
            "worker_cap": MAX_WORKERS,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "requests_completed": len(results),
            "persisted_this_run": sum(item["status"] == "persisted" for item in results),
            "retry_count": sum(int(item["retry_count"]) for item in results),
            "completed": final["eligible_unique_hashes"] >= target,
            "preflight": preflight,
        },
        "review_pool": {
            "initial_eligible_events": initial["eligible_events"],
            "initial_unique_hashes": initial["eligible_unique_hashes"],
            "final_eligible_events": final["eligible_events"],
            "final_unique_hashes": final["eligible_unique_hashes"],
            "human_labels_before": initial["human_labels"],
            "human_labels_after": final["human_labels"],
            "campaign_writes_human_labels": False,
        },
        "model_evidence": {
            "verdicts": dict(verdicts),
            "component_statuses": component_statuses,
            "component_latency_ms": component_timings,
        },
        "errors": dict(errors),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate the encrypted guardrail review pool")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8010/api/guardrail/check")
    parser.add_argument("--audit-db", type=Path, default=DEFAULT_AUDIT_DB)
    parser.add_argument("--target", type=int, default=200)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-delay", type=float, default=1.0)
    parser.add_argument("--max-variants", type=int, default=20)
    parser.add_argument("--required-components", default=",".join(DEFAULT_REQUIRED_COMPONENTS))
    parser.add_argument("--allow-degraded", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("results/review-campaign-latest.json"))
    args = parser.parse_args()
    report = run_campaign(
        endpoint=args.endpoint,
        audit_db=args.audit_db,
        target=args.target,
        workers=args.workers,
        timeout=args.timeout,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        max_variants=args.max_variants,
        required_components=args.required_components.split(","),
        allow_degraded=args.allow_degraded,
    )
    output = args.output if args.output.is_absolute() else Path(__file__).parent / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "campaign": report["campaign"],
        "review_pool": report["review_pool"],
        "model_evidence": report["model_evidence"],
        "errors": report["errors"],
        "report": str(output),
    }, ensure_ascii=False, indent=2))
    return 0 if report["campaign"]["completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
