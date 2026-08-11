#!/usr/bin/env python3
"""Generate publication-style figures for the PerspectiveVision experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


COLORS = {
    "baseline": "#2563EB",
    "perspective": "#10B981",
    "cascade": "#F59E0B",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--perspective", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def metric_tuple(records: list[dict], selector) -> dict[str, float | int]:
    labels = [record["expected_binary"] for record in records]
    predictions = [selector(record) for record in records]
    tp = sum(y == 1 and p == 1 for y, p in zip(labels, predictions))
    tn = sum(y == 0 and p == 0 for y, p in zip(labels, predictions))
    fp = sum(y == 0 and p == 1 for y, p in zip(labels, predictions))
    fn = sum(y == 1 and p == 0 for y, p in zip(labels, predictions))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": (tp + tn) / len(records),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
    }


def save_figure(fig: plt.Figure, output_dir: Path, stem: str) -> None:
    fig.savefig(output_dir / f"{stem}.png", dpi=220, bbox_inches="tight", facecolor="white")
    fig.savefig(output_dir / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    perspective = json.loads(args.perspective.read_text(encoding="utf-8"))
    perspective_by_id = {record["sample_id"]: record for record in perspective["records"]}
    paired = []
    for record in baseline["records"]:
        paired.append({**record, "perspective_status": perspective_by_id[record["sample_id"]]["status"]})
    cascade = metric_tuple(
        paired,
        lambda record: int(record["status"] == "unsafe" or record["perspective_status"] == "unsafe"),
    )

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titleweight": "semibold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 130,
        }
    )
    names = ["MultiHeaded+Q16", "PerspectiveVision", "Risk cascade"]
    metric_sets = [baseline["metrics"], perspective["metrics"], cascade]
    colors = [COLORS["baseline"], COLORS["perspective"], COLORS["cascade"]]

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2), constrained_layout=True)
    labels = ["Accuracy", "Precision", "Recall", "F1"]
    x = np.arange(len(labels))
    width = 0.24
    for index, (name, values, color) in enumerate(zip(names, metric_sets, colors)):
        heights = [values[label.lower()] * 100 for label in labels]
        bars = axes[0].bar(x + (index - 1) * width, heights, width, label=name, color=color)
        axes[0].bar_label(bars, fmt="%.1f", fontsize=8, padding=2)
    axes[0].set_title("Overall binary safety performance (n=75)")
    axes[0].set_ylabel("Score (%)")
    axes[0].set_xticks(x, labels)
    axes[0].set_ylim(0, 108)
    axes[0].grid(axis="y", alpha=0.22)
    axes[0].legend(frameon=False, loc="lower right")

    groups = ["adult_content", "violence", "weapon_display"]
    group_labels = ["Adult", "Violence", "Weapon"]
    bx = np.arange(len(groups))
    for index, (name, data, color) in enumerate(
        zip(names[:2], [baseline["per_group"], perspective["per_group"]], colors[:2])
    ):
        heights = [data[group]["metrics"]["recall"] * 100 for group in groups]
        bars = axes[1].bar(bx + (index - 0.5) * 0.34, heights, 0.34, label=name, color=color)
        axes[1].bar_label(bars, fmt="%.1f", fontsize=8, padding=2)
    axes[1].set_title("Recall by risk category")
    axes[1].set_ylabel("Recall (%)")
    axes[1].set_xticks(bx, group_labels)
    axes[1].set_ylim(0, 108)
    axes[1].grid(axis="y", alpha=0.22)
    axes[1].legend(frameon=False, loc="lower right")
    fig.suptitle("PerspectiveVision-LLaVA independent evaluation", fontsize=14, fontweight="bold")
    save_figure(fig, args.output_dir, "performance-comparison")

    fig, axes = plt.subplots(1, 3, figsize=(10.6, 3.6), constrained_layout=True)
    for ax, name, values, color in zip(axes, names, metric_sets, colors):
        matrix = np.array([[values["tn"], values["fp"]], [values["fn"], values["tp"]]])
        ax.imshow(matrix, cmap="Blues", vmin=0, vmax=max(matrix.max(), 1))
        for row in range(2):
            for column in range(2):
                ax.text(column, row, str(matrix[row, column]), ha="center", va="center", fontsize=15)
        ax.set_title(name, color=color)
        ax.set_xticks([0, 1], ["Pred safe", "Pred unsafe"])
        ax.set_yticks([0, 1], ["True safe", "True unsafe"])
    fig.suptitle("Confusion matrices on the frozen public set", fontsize=14, fontweight="bold")
    save_figure(fig, args.output_dir, "confusion-matrices")

    comparison = {
        "schema": "perspectivevision-comparison-v1",
        "dataset": "public_content_safety_v1",
        "sample_count": len(paired),
        "baseline": baseline["metrics"],
        "perspective": perspective["metrics"],
        "cascade": cascade,
        "disagreements": sum(
            record["status"] != record["perspective_status"] for record in paired
        ),
        "perspective_recovers_baseline_false_negatives": sum(
            record["expected_binary"] == 1
            and record["status"] == "safe"
            and record["perspective_status"] == "unsafe"
            for record in paired
        ),
        "perspective_misses_baseline_true_positives": sum(
            record["expected_binary"] == 1
            and record["status"] == "unsafe"
            and record["perspective_status"] == "safe"
            for record in paired
        ),
    }
    (args.output_dir / "comparison-summary.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
