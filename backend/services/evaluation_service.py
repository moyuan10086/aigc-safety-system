"""Offline, label-backed evaluation utilities for detection-score calibration.

These functions deliberately operate on a held-out, human-labelled dataset. They
must not be fed live review decisions when producing a published calibration report.
"""

from __future__ import annotations

from collections import defaultdict
from math import sqrt
from pathlib import Path
import json
from typing import Any, Iterable

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


MIN_SAMPLES = 30
MIN_CLASS_SAMPLES = 5
SHOWCASE_MIN_RECALL = 0.80
SHOWCASE_MIN_PRECISION = 0.80
SHOWCASE_MIN_F1 = 0.80
CONTENT_SAFETY_TASKS = (
    "content_safety:adult_content",
    "content_safety:weapon_display",
    "content_safety:violence",
    "content_safety:political_sensitive",
    "content_safety:marketing_violation",
)

PUBLISHED_METRICS = (
    "accuracy", "accuracy_95ci", "precision", "precision_95ci",
    "recall", "recall_95ci", "f1", "f1_95ci", "roc_auc",
    "roc_auc_95ci", "pr_auc", "pr_auc_95ci", "brier_score", "ece",
)


def _metric_evidence(result: dict[str, Any]) -> dict[str, Any]:
    """Select fields that are safe and useful in the administrator UI."""
    evidence = {
        "threshold": result.get("threshold"),
        "confusion_matrix": result.get("confusion_matrix"),
        "metrics": {
            key: result.get(key)
            for key in PUBLISHED_METRICS
            if result.get(key) is not None
        },
    }
    return {key: value for key, value in evidence.items() if value is not None}


def _quality_state(task: dict[str, Any]) -> tuple[str, str]:
    """Separate statistical availability from operational fitness."""
    if task.get("status") != "ready":
        return "evidence_pending", "尚未形成可发布统计结论"

    metrics = task.get("metrics") or {}
    recall = metrics.get("recall")
    precision = metrics.get("precision")
    roc_auc = metrics.get("roc_auc")
    positive_count = int(task.get("positive_count") or 0)

    if recall is not None and float(recall) < 0.5:
        return "unsafe_for_automation", "召回率过低，不可自动放行"
    if any(
        value is not None and float(value) < limit
        for value, limit in ((recall, 0.7), (precision, 0.5), (roc_auc, 0.7))
    ):
        return "limited", "统计完成，但能力仍受限"
    if positive_count <= MIN_CLASS_SAMPLES:
        return "limited_evidence", "阳性样本较少，需继续扩充"
    return "validated", "协议内统计指标可用"


def evaluation_status() -> dict[str, Any]:
    """Return the conservative, read-only status exposed to the review UI.

    The UI must never infer calibration from live decisions or an unlabeled
    benchmark.  This function only inspects versioned evaluation artifacts
    checked into the project and reports the strongest claim they support.
    """
    # ``evaluation_service.py`` lives under ``backend/services`` while the
    # versioned evidence and reports live under the repository-level ``docs``.
    project_root = Path(__file__).resolve().parents[2]
    evidence_dir = project_root / "docs" / "evidence"
    evaluation_dir = project_root / "docs" / "evaluation"
    task_statuses: list[dict[str, Any]] = []
    latest_evidence: str | None = None

    production_retest_path = evidence_dir / "deepfake-platform-epoch6-retest-20260812.json"
    if production_retest_path.exists():
        try:
            production_retest = json.loads(production_retest_path.read_text(encoding="utf-8"))
            model = production_retest.get("model") or {}
            protocol = production_retest.get("protocol") or {}
            latest_evidence = production_retest_path.name
            for split in ("val", "test"):
                result = production_retest.get(split) or {}
                if not result:
                    continue
                task_statuses.append({
                    "task": f"deepfake:platform_{'validation' if split == 'val' else 'test'}",
                    "evidence_artifact": production_retest_path.name,
                    "dataset": protocol.get("dataset", "DF40 curated held-out"),
                    "split": "validation" if split == "val" else "test",
                    "model_version": f"{model.get('name', '平台多数据集微调模型')} · epoch {model.get('best_epoch', 6)}",
                    "model_origin": "platform_finetuned",
                    "weights_sha256": model.get("checkpoint_sha256"),
                    "status": "ready",
                    "sample_count": result.get("count", 0),
                    "positive_count": result.get("tp", 0) + result.get("fn", 0),
                    "negative_count": result.get("tn", 0) + result.get("fp", 0),
                    "threshold": protocol.get("threshold", 0.5),
                    "confusion_matrix": {key: result.get(key, 0) for key in ("tp", "tn", "fp", "fn")},
                    "metrics": {
                        "accuracy": result.get("accuracy"),
                        "precision": result.get("precision"),
                        "recall": result.get("recall_fake"),
                        "f1": result.get("f1"),
                    },
                    "latency_ms": {"total": round(float(result.get("elapsed_s", 0)) * 1000, 1)},
                    "evaluated_at": production_retest.get("generated_at"),
                    "current_deployment": True,
                })
        except (OSError, ValueError, TypeError):
            task_statuses.append({"task": "deepfake:platform", "status": "inconclusive"})

    cascade_artifacts = (
        ("content_safety:multiheaded_q16", evidence_dir / "multiheaded-q16-public75-20260812.json", "MultiHeaded+Q16 主审核"),
        ("content_safety:perspectivevision", evidence_dir / "perspectivevision-public75-20260812.json", "PerspectiveVision-LLaVA 二次复核"),
    )
    for task, artifact_path, model_version in cascade_artifacts:
        if not artifact_path.exists():
            continue
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            metrics = payload.get("metrics") or {}
            cm = {key: metrics.get(key, 0) for key in ("tp", "tn", "fp", "fn")}
            task_statuses.append({
                "task": task,
                "evidence_artifact": artifact_path.name,
                "dataset": "public_content_safety_v1",
                "split": "frozen-75-same-input",
                "model_version": model_version,
                "status": "ready" if not payload.get("inconclusive") else "inconclusive",
                "sample_count": payload.get("sample_count", metrics.get("evaluated", 0)),
                "positive_count": cm["tp"] + cm["fn"],
                "negative_count": cm["tn"] + cm["fp"],
                "threshold": 0.5,
                "confusion_matrix": cm,
                "metrics": {key: metrics.get(key) for key in ("accuracy", "precision", "recall", "f1")},
                "latency_ms": payload.get("latency_ms"),
                "evaluated_at": "2026-08-12",
                "current_deployment": True,
            })
            latest_evidence = artifact_path.name
        except (OSError, ValueError, TypeError):
            task_statuses.append({"task": task, "status": "inconclusive", "evidence_artifact": artifact_path.name})

    singguard_path = evidence_dir / "singguard-benchmark-20260812.json"
    if singguard_path.exists():
        try:
            payload = json.loads(singguard_path.read_text(encoding="utf-8"))
            rows = payload.get("results") or []
            tp = sum(bool(row.get("expected_risk")) and bool(row.get("predicted_risk")) for row in rows)
            tn = sum(not bool(row.get("expected_risk")) and not bool(row.get("predicted_risk")) for row in rows)
            fp = sum(not bool(row.get("expected_risk")) and bool(row.get("predicted_risk")) for row in rows)
            fn = sum(bool(row.get("expected_risk")) and not bool(row.get("predicted_risk")) for row in rows)
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / (tp + fn) if tp + fn else 0.0
            task_statuses.append({
                "task": "guardrail:singguard",
                "evidence_artifact": singguard_path.name,
                "dataset": "platform_guardrail_cases_v1",
                "split": "frozen-10",
                "model_version": "SingGuard-NSFA-0.8B",
                "model_origin": "third_party_deployed",
                "status": "ready",
                "sample_count": len(rows),
                "positive_count": tp + fn,
                "negative_count": tn + fp,
                "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
                "metrics": {
                    "accuracy": payload.get("accuracy"),
                    "precision": precision,
                    "recall": recall,
                    "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
                },
                "latency_ms": payload.get("latency_ms"),
                "evaluated_at": "2026-08-12",
                "current_deployment": True,
            })
        except (OSError, ValueError, TypeError):
            task_statuses.append({"task": "guardrail:singguard", "status": "inconclusive"})

    statistical_path = evidence_dir / "df40-statistical-evaluation-20260809.json"
    if statistical_path.exists():
        try:
            statistical = json.loads(statistical_path.read_text(encoding="utf-8"))
            latest_evidence = statistical_path.name
            for split, result in sorted((statistical.get("metrics") or {}).items()):
                task_statuses.append({
                    "task": f"deepfake:{split}",
                    "evidence_artifact": statistical_path.name,
                    "dataset": statistical.get("dataset"),
                    "split": split,
                    "model_version": statistical.get("model_name") or "模型名称未登记",
                    "weights_sha256": statistical.get("model_sha256"),
                    "status": result.get("status", "inconclusive"),
                    "sample_count": result.get("sample_count", 0),
                    "positive_count": result.get("positive_count", 0),
                    "negative_count": result.get("negative_count", 0),
                    **_metric_evidence(result),
                })
        except (OSError, ValueError, TypeError):
            task_statuses.append({"task": "deepfake:df40", "status": "inconclusive"})

    public_content_path = evidence_dir / "public-content-safety-statistical-evaluation-20260809.json"
    if public_content_path.exists():
        try:
            public_content = json.loads(public_content_path.read_text(encoding="utf-8"))
            latest_evidence = public_content_path.name
            protocol = public_content.get("protocol") or {}
            for task, result in sorted((public_content.get("tasks") or {}).items()):
                if task not in CONTENT_SAFETY_TASKS:
                    continue
                task_statuses.append({
                    "task": task,
                    "evidence_artifact": public_content_path.name,
                    "dataset": ", ".join(protocol.get("datasets") or []),
                    "split": ", ".join(protocol.get("splits") or []),
                    "model_version": ", ".join(protocol.get("model_versions") or []),
                    "status": result.get("status", "inconclusive"),
                    "sample_count": result.get("sample_count", 0),
                    "positive_count": result.get("positive_count", 0),
                    "negative_count": result.get("negative_count", 0),
                    **_metric_evidence(result),
                })
        except (OSError, ValueError, TypeError):
            task_statuses.append({"task": "content_safety:public_benchmark", "status": "inconclusive"})

    smoke_path = evidence_dir / "detection-score-smoke-20260809.json"
    if smoke_path.exists():
        try:
            payload = json.loads(smoke_path.read_text(encoding="utf-8"))
            if not latest_evidence:
                latest_evidence = smoke_path.name
            for task, result in sorted((payload.get("tasks") or {}).items()):
                if any(item.get("task") == task for item in task_statuses):
                    continue
                task_statuses.append({
                    "task": task,
                    "evidence_artifact": smoke_path.name,
                    "status": result.get("status", "unknown"),
                    "sample_count": result.get("sample_count", 0),
                    "positive_count": result.get("positive_count", 0),
                    "negative_count": result.get("negative_count", 0),
                })
            known_tasks = {item["task"] for item in task_statuses}
            for task in CONTENT_SAFETY_TASKS:
                if task not in known_tasks:
                    task_statuses.append({
                        "task": task,
                        "status": "insufficient_samples",
                        "sample_count": 0,
                        "positive_count": 0,
                        "negative_count": 0,
                        "reason": "no frozen labelled evidence registered",
                    })
        except (OSError, ValueError, TypeError):
            task_statuses.append({"task": "content_safety", "status": "inconclusive"})

    # Once a local, label-backed statistical report exists, expose its metrics
    # instead of leaving the task stuck at the access-gated placeholder.
    unsafebench_ready = False
    unsafebench_statistical_path = evidence_dir / "unsafebench-statistical-evaluation.json"
    if unsafebench_statistical_path.exists():
        try:
            statistical = json.loads(unsafebench_statistical_path.read_text(encoding="utf-8"))
            latest_evidence = latest_evidence or unsafebench_statistical_path.name
            for task, result in sorted((statistical.get("tasks") or {}).items()):
                if not str(task).startswith("content_safety:"):
                    continue
                unsafebench_ready = unsafebench_ready or result.get("status") == "ready"
                task_statuses.append({
                    "task": task,
                    "evidence_artifact": unsafebench_statistical_path.name,
                    "status": result.get("status", "inconclusive"),
                    "sample_count": result.get("sample_count", 0),
                    "positive_count": result.get("positive_count", 0),
                    "negative_count": result.get("negative_count", 0),
                    **_metric_evidence(result),
                })
        except (OSError, ValueError, TypeError):
            task_statuses.append({"task": "content_safety:unsafebench", "status": "inconclusive"})

    # Optional extension benchmarks are reported independently. They must not
    # be folded into the five core image-safety categories or into UnsafeBench.
    extension_paths = (
        # Prefer the full 30-sample held-out extension. The older five-positive
        # smoke artifact remains in the repository as a chain-validation record,
        # but must not override the label-backed statistical result.
        evidence_dir / "content-safety-personal-data-statistical-evaluation-30-20260809.json",
    )
    for extension_path in extension_paths:
        if not extension_path.exists():
            continue
        try:
            extension = json.loads(extension_path.read_text(encoding="utf-8"))
            latest_evidence = latest_evidence or extension_path.name
            protocol = extension.get("protocol") or {}
            for task, result in sorted((extension.get("tasks") or {}).items()):
                if not str(task).startswith("content_safety:"):
                    continue
                task_statuses.append({
                    "task": task,
                    "evidence_artifact": extension_path.name,
                    "dataset": (protocol.get("datasets") or [None])[0],
                    "split": (protocol.get("splits") or [None])[0],
                    "model_version": (protocol.get("model_versions") or [None])[0],
                    "status": result.get("status", "inconclusive"),
                    "sample_count": result.get("sample_count", 0),
                    "positive_count": result.get("positive_count", 0),
                    "negative_count": result.get("negative_count", 0),
                    **_metric_evidence(result),
                })
        except (OSError, ValueError, TypeError):
            task_statuses.append({"task": "content_safety:personal_data", "status": "inconclusive"})

    # A gated public benchmark is visible as a pending task, never as a
    # successful evaluation. This makes the remaining access action explicit.
    audit_path = evaluation_dir / "dataset-access-audit-20260809.json"
    if audit_path.exists():
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            unsafebench = next(
                (item for item in audit.get("datasets", []) if item.get("dataset_id") == "unsafebench"),
                None,
            )
            if unsafebench and not unsafebench_ready:
                task_statuses.append({
                    "task": "content_safety:unsafebench",
                    "status": "pending_access",
                    "sample_count": unsafebench.get("dataset_scale", 0),
                })
        except (OSError, ValueError, TypeError):
            task_statuses.append({"task": "content_safety:unsafebench", "status": "inconclusive"})

    blind_path = evidence_dir / "faceforensics-blind-predictions-20260809.json"
    blind_labeled = False
    if blind_path.exists():
        try:
            blind = json.loads(blind_path.read_text(encoding="utf-8"))
            blind_labeled = bool(blind.get("labels_available") or blind.get("ground_truth"))
            if not latest_evidence:
                latest_evidence = blind_path.name
            task_statuses.append({
                "task": "deepfake:faceforensics_blind",
                "evidence_artifact": blind_path.name,
                "status": "ready" if blind_labeled else "unlabeled",
                "sample_count": len(blind.get("predictions") or blind.get("results") or []),
            })
        except (OSError, ValueError, TypeError):
            task_statuses.append({"task": "deepfake:faceforensics_blind", "status": "inconclusive"})

    for item in task_statuses:
        quality_state, quality_summary = _quality_state(item)
        item["quality_state"] = quality_state
        item["quality_summary"] = quality_summary

        metrics = item.get("metrics") or {}
        current = bool(item.get("current_deployment"))
        meets_showcase_threshold = all(
            metrics.get(metric) is not None and float(metrics[metric]) >= threshold
            for metric, threshold in (
                ("recall", SHOWCASE_MIN_RECALL),
                ("precision", SHOWCASE_MIN_PRECISION),
                ("f1", SHOWCASE_MIN_F1),
            )
        )
        item["publication"] = "showcase" if (
            current
            and item.get("status") == "ready"
            and int(item.get("sample_count") or 0) >= MIN_SAMPLES
            and meets_showcase_threshold
        ) else "archive"
        item["showcase"] = item["publication"] == "showcase"

    if production_retest_path.exists():
        latest_evidence = production_retest_path.name

    has_ready = any(item.get("status") == "ready" for item in task_statuses)
    has_evidence = bool(task_statuses)
    has_incomplete = any(item.get("status") != "ready" for item in task_statuses)
    status = (
        "partially_calibrated" if has_ready and has_incomplete
        else "calibrated" if has_ready
        else "smoke_only" if has_evidence
        else "not_calibrated"
    )
    claim_level = {
        "calibrated": "所有已登记评测任务均有足量独立标签，可发布协议内统计指标",
        "partially_calibrated": "仅部分模块有足量独立标签；其余模块仍不能发布准确率或 SOTA 结论",
        "smoke_only": "仅验证接口字段与链路，不支持准确率或 SOTA 结论",
        "not_calibrated": "暂无带标签的独立评测证据",
    }[status]
    result = {
        "status": status,
        "claim_level": claim_level,
        "tasks": task_statuses,
        "latest_evidence": latest_evidence,
        "minimum_samples": {"total": MIN_SAMPLES, "per_class": MIN_CLASS_SAMPLES},
        "showcase_thresholds": {
            "recall": SHOWCASE_MIN_RECALL,
            "precision": SHOWCASE_MIN_PRECISION,
            "f1": SHOWCASE_MIN_F1,
        },
        "summary": {
            "evaluated": sum(item.get("status") == "ready" for item in task_statuses),
            "validated": sum(item.get("quality_state") == "validated" for item in task_statuses),
            "limited": sum(item.get("quality_state") in {"limited", "limited_evidence"} for item in task_statuses),
            "blocked": sum(item.get("quality_state") == "unsafe_for_automation" for item in task_statuses),
            "pending": sum(item.get("quality_state") == "evidence_pending" for item in task_statuses),
            "showcase": sum(bool(item.get("showcase")) for item in task_statuses),
            "archived": sum(not bool(item.get("showcase")) for item in task_statuses),
        },
        "boundary": "只有独立、人工标注且冻结版本的留出集才能支持统计校准；无标签盲测只能报告模型分数分布。",
        "report": str((evaluation_dir / "master-evaluation-report-20260809.md").relative_to(project_root))
        if (evaluation_dir / "master-evaluation-report-20260809.md").exists() else None,
    }
    result["claim_level"] = claim_level
    result["boundary"] = "只有独立、人工标注且冻结版本的留出集才能支持统计校准；无标签盲测只能报告模型分数分布。"
    return result


def _bootstrap_interval(labels: np.ndarray, scores: np.ndarray, metric: str, *, threshold: float = 0.5, reps: int = 500, seed: int = 20260809) -> list[float] | None:
    """Deterministic percentile bootstrap interval for a binary metric."""
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(reps):
        indices = rng.integers(0, len(labels), len(labels))
        sample_labels = labels[indices]
        if len(np.unique(sample_labels)) < 2:
            continue
        sample_scores = scores[indices]
        if metric == "roc_auc":
            values.append(float(roc_auc_score(sample_labels, sample_scores)))
        elif metric == "pr_auc":
            values.append(float(average_precision_score(sample_labels, sample_scores)))
        else:
            predicted = sample_scores >= threshold
            tp = int(((predicted == 1) & (sample_labels == 1)).sum())
            tn = int(((predicted == 0) & (sample_labels == 0)).sum())
            fp = int(((predicted == 1) & (sample_labels == 0)).sum())
            fn = int(((predicted == 0) & (sample_labels == 1)).sum())
            if metric == "precision":
                values.append(tp / (tp + fp) if tp + fp else 0.0)
            elif metric == "recall":
                values.append(tp / (tp + fn) if tp + fn else 0.0)
            elif metric == "f1":
                precision = tp / (tp + fp) if tp + fp else 0.0
                recall = tp / (tp + fn) if tp + fn else 0.0
                values.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    if not values:
        return None
    return [round(float(np.percentile(values, 2.5)), 4), round(float(np.percentile(values, 97.5)), 4)]


def _bounded_score(value: Any) -> float:
    score = float(value)
    if not 0.0 <= score <= 1.0:
        raise ValueError("score must be within [0, 1]")
    return score


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    if total <= 0:
        return None
    rate = successes / total
    denominator = 1 + z * z / total
    centre = (rate + z * z / (2 * total)) / denominator
    margin = z * sqrt((rate * (1 - rate) + z * z / (4 * total)) / total) / denominator
    return [round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4)]


def _expected_calibration_error(labels: np.ndarray, scores: np.ndarray, bins: int = 10) -> tuple[float, list[dict[str, Any]]]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, Any]] = []
    ece = 0.0
    for index in range(bins):
        low, high = edges[index], edges[index + 1]
        mask = (scores >= low) & ((scores < high) if index < bins - 1 else (scores <= high))
        count = int(mask.sum())
        if not count:
            continue
        confidence = float(scores[mask].mean())
        accuracy = float(labels[mask].mean())
        ece += count / len(labels) * abs(accuracy - confidence)
        rows.append({
            "range": [round(float(low), 2), round(float(high), 2)],
            "count": count,
            "mean_score": round(confidence, 4),
            "empirical_rate": round(accuracy, 4),
        })
    return round(float(ece), 4), rows


def evaluate_binary(records: Iterable[dict[str, Any]], *, threshold: float = 0.5) -> dict[str, Any]:
    """Evaluate a binary score against independent labels.

    Each record requires ``label`` (0/1 or false/true) and ``score`` in [0, 1].
    ``score`` must mean the probability/risk of the positive class for that task.
    """
    if not 0.0 < threshold < 1.0:
        raise ValueError("threshold must be within (0, 1)")
    rows = list(records)
    labels = np.asarray([int(bool(row["label"])) for row in rows], dtype=int)
    scores = np.asarray([_bounded_score(row["score"]) for row in rows], dtype=float)
    total = len(rows)
    positives = int(labels.sum())
    negatives = total - positives
    base = {
        "sample_count": total,
        "positive_count": positives,
        "negative_count": negatives,
        "threshold": threshold,
        "status": "ready",
    }
    if total < MIN_SAMPLES or min(positives, negatives) < MIN_CLASS_SAMPLES:
        base.update({
            "status": "insufficient_samples",
            "reason": f"requires at least {MIN_SAMPLES} samples and {MIN_CLASS_SAMPLES} samples per class",
        })
        return base

    predicted = scores >= threshold
    tp = int(((predicted == 1) & (labels == 1)).sum())
    tn = int(((predicted == 0) & (labels == 0)).sum())
    fp = int(((predicted == 1) & (labels == 0)).sum())
    fn = int(((predicted == 0) & (labels == 1)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    accuracy = (tp + tn) / total
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    ece, calibration_bins = _expected_calibration_error(labels, scores)
    base.update({
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "accuracy": round(accuracy, 4),
        "accuracy_95ci": _wilson_interval(tp + tn, total),
        "precision": round(precision, 4),
        "precision_95ci": _bootstrap_interval(labels, scores, "precision", threshold=threshold),
        "recall": round(recall, 4),
        "recall_95ci": _bootstrap_interval(labels, scores, "recall", threshold=threshold),
        "f1": round(f1, 4),
        "f1_95ci": _bootstrap_interval(labels, scores, "f1", threshold=threshold),
        "roc_auc": round(float(roc_auc_score(labels, scores)), 4),
        "roc_auc_95ci": _bootstrap_interval(labels, scores, "roc_auc"),
        "pr_auc": round(float(average_precision_score(labels, scores)), 4),
        "pr_auc_95ci": _bootstrap_interval(labels, scores, "pr_auc"),
        "brier_score": round(float(np.mean((scores - labels) ** 2)), 4),
        "ece": ece,
        "calibration_bins": calibration_bins,
    })
    return base


def evaluate_by_task(records: Iterable[dict[str, Any]], *, threshold: float = 0.5) -> dict[str, Any]:
    """Group a JSONL-style evaluation set by task and score each task independently."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        task = str(record.get("task") or "").strip()
        if not task:
            raise ValueError("each evaluation record requires a task")
        groups[task].append(record)
    return {task: evaluate_binary(items, threshold=threshold) for task, items in sorted(groups.items())}
