"""Run a metadata-only calibration benchmark against the real guardrail pipeline."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

from blind_cases import BLIND_CASES
from calibration_cases import CASES

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * percentile) - 1)
    return round(ordered[index], 3)


def _binary_metrics(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    tp = sum(expected == "unsafe" and predicted == "unsafe" for expected, predicted in pairs)
    tn = sum(expected == "safe" and predicted == "safe" for expected, predicted in pairs)
    fp = sum(expected == "safe" and predicted == "unsafe" for expected, predicted in pairs)
    fn = sum(expected == "unsafe" and predicted == "safe" for expected, predicted in pairs)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "samples": len(pairs),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": round((tp + tn) / len(pairs) * 100, 2) if pairs else 0.0,
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "fpr": round(fp / (fp + tn) * 100, 2) if fp + tn else 0.0,
        "fnr": round(fn / (fn + tp) * 100, 2) if fn + tp else 0.0,
        "f1": round(2 * precision * recall / (precision + recall) * 100, 2)
        if precision + recall
        else 0.0,
    }


def _load_guardrail(offline: bool) -> Callable[..., dict[str, Any]]:
    if offline:
        for switch in (
            "GUARDRAIL_ENABLE_RAG",
            "GUARDRAIL_ENABLE_MLLM",
            "GUARDRAIL_ENABLE_QWEN_CLASSIFIER",
            "GUARDRAIL_ENABLE_SINGGUARD_CLASSIFIER",
            "GUARDRAIL_ENABLE_XGBOOST_SHADOW",
        ):
            os.environ[switch] = "false"
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from services import guardrail_service

    return guardrail_service.check


CASE_SETS = {
    "calibration": CASES,
    "blind": BLIND_CASES,
    "all": [*CASES, *BLIND_CASES],
}


def _evaluate_case(
    case: dict[str, Any],
    check: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    sample_started = time.perf_counter()
    try:
        output = check(case["prompt"], case["response"], case["mode"])
        error_code = None
    except Exception as exc:
        output = {}
        error_code = type(exc).__name__
    latency = round((time.perf_counter() - sample_started) * 1000, 3)
    shadow = output.get("shadow_evaluation") or {}
    return {
        "id": case["id"],
        "expected": case["expected"],
        "expected_category": case["expected_category"],
        "predicted": output.get("verdict", "error"),
        "risk_score": output.get("risk_score"),
        "categories": output.get("categories", []),
        "latency_ms": latency,
        "error_code": error_code,
        "components": (output.get("engine") or {}).get("components", {}),
        "shadow": {
            key: shadow.get(key)
            for key in ("status", "decision", "confidence", "agreement", "latency_ms", "risk_type")
        },
    }


def run(
    offline: bool,
    *,
    case_set: str = "calibration",
    workers: int = 1,
    sla_seconds: float = 30.0,
) -> dict[str, Any]:
    check = _load_guardrail(offline)
    selected_cases = CASE_SETS[case_set]
    workers = max(1, min(int(workers), 8))
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="guardrail-eval") as executor:
        results = list(executor.map(lambda case: _evaluate_case(case, check), selected_cases))
    duration_seconds = time.perf_counter() - started
    latencies = [float(item["latency_ms"]) for item in results]

    binary_results = [
        item
        for item in results
        if item["expected"] in {"safe", "unsafe"} and item["error_code"] is None
    ]
    primary_block = _binary_metrics([
        (item["expected"], "unsafe" if item["predicted"] == "unsafe" else "safe")
        for item in binary_results
    ])
    primary_intervention = _binary_metrics([
        (item["expected"], "unsafe" if item["predicted"] != "safe" else "safe")
        for item in binary_results
    ])
    category_cases = [item for item in results if item["expected_category"]]
    category_hits = sum(item["expected_category"] in item["categories"] for item in category_cases)
    shadow_results = [
        item for item in binary_results
        if item["shadow"].get("status") == "ok" and item["shadow"].get("decision") in {"pass", "fail"}
    ]
    shadow_native = _binary_metrics([
        (item["expected"], "unsafe" if item["shadow"]["decision"] == "fail" else "safe")
        for item in shadow_results
    ])
    threshold_curve = []
    for threshold in (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95):
        pairs = []
        for item in shadow_results:
            confidence = float(item["shadow"].get("confidence") or 0.0)
            risk_probability = confidence if item["shadow"]["decision"] == "fail" else 1 - confidence
            pairs.append((item["expected"], "unsafe" if risk_probability >= threshold else "safe"))
        threshold_curve.append({"threshold": threshold, **_binary_metrics(pairs)})

    exact_hits = sum(item["expected"] == item["predicted"] for item in results)
    dataset_canonical = json.dumps(selected_cases, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    component_statuses: dict[str, Counter[str]] = defaultdict(Counter)
    for item in results:
        for component, status in item["components"].items():
            component_statuses[str(component)][str(status)] += 1
    degraded_samples = sum(
        any(status in {"unavailable", "error", "warming"} for status in item["components"].values())
        for item in results
    )
    error_counts = Counter(item["error_code"] for item in results if item["error_code"])
    return {
        "dataset": {
            "name": case_set,
            "version": "2026.08.04-p2.3" if case_set != "calibration" else "2026.08.03-p2.2",
            "sha256": hashlib.sha256(dataset_canonical.encode("utf-8")).hexdigest(),
            "samples": len(selected_cases),
            "labels": {
                label: sum(case["expected"] == label for case in selected_cases)
                for label in ("safe", "borderline", "unsafe")
            },
            "raw_content_in_report": False,
        },
        "run": {
            "offline": offline,
            "workers": workers,
            "duration_ms": round(duration_seconds * 1000, 3),
            "throughput_samples_per_second": round(len(results) / duration_seconds, 3)
            if duration_seconds
            else 0.0,
            "average_latency_ms": round(sum(latencies) / len(latencies), 3),
            "p95_latency_ms": _percentile(latencies, 0.95),
            "sla_seconds": sla_seconds,
            "sla_exceeded_count": sum(latency > sla_seconds * 1000 for latency in latencies),
            "error_count": sum(error_counts.values()),
            "errors": dict(error_counts),
            "degraded_samples": degraded_samples,
            "degraded_rate": round(degraded_samples / len(results) * 100, 2) if results else 0.0,
            "component_statuses": {
                component: dict(statuses)
                for component, statuses in sorted(component_statuses.items())
            },
        },
        "primary": {
            "exact_accuracy": round(exact_hits / len(results) * 100, 2),
            "block_only": primary_block,
            "intervention": primary_intervention,
            "category_recall": round(category_hits / len(category_cases) * 100, 2)
            if category_cases
            else 0.0,
        },
        "shadow": {
            "evaluated_samples": len(shadow_results),
            "native": shadow_native,
            "threshold_curve": threshold_curve,
        },
        "failures": [
            {
                "id": item["id"],
                "expected": item["expected"],
                "predicted": item["predicted"],
                "expected_category": item["expected_category"],
                "categories": item["categories"],
                "shadow_decision": item["shadow"].get("decision"),
            }
            for item in results
            if item["expected"] != item["predicted"]
        ],
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="disable model and RAG enrichments")
    parser.add_argument("--case-set", choices=sorted(CASE_SETS), default="calibration")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--sla-seconds", type=float, default=30.0)
    parser.add_argument("--output", default="results/calibration-latest.json")
    args = parser.parse_args()
    report = run(
        args.offline,
        case_set=args.case_set,
        workers=args.workers,
        sla_seconds=max(1.0, args.sla_seconds),
    )
    output = Path(args.output)
    if not output.is_absolute():
        output = Path(__file__).parent / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "dataset": report["dataset"],
        "run": report["run"],
        "primary": report["primary"],
        "shadow": report["shadow"],
        "report": str(output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
