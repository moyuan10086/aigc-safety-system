import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from services.evaluation_service import evaluate_binary, evaluate_by_task, evaluation_status
from normalize_evidence_to_heldout import normalize
from normalize_deepfake_benchmark import normalize as normalize_deepfake


def test_evaluation_refuses_unpublishable_small_sample() -> None:
    result = evaluate_binary([
        {"label": 1, "score": 0.9},
        {"label": 0, "score": 0.1},
    ])
    assert result["status"] == "insufficient_samples"
    assert result["sample_count"] == 2


def test_evaluation_reports_discrimination_and_calibration_metrics() -> None:
    records = ([{"label": 1, "score": 0.9} for _ in range(20)] +
               [{"label": 0, "score": 0.1} for _ in range(20)])
    result = evaluate_binary(records)
    assert result["status"] == "ready"
    assert result["accuracy"] == 1.0
    assert result["roc_auc"] == 1.0
    assert result["brier_score"] == 0.01
    assert result["accuracy_95ci"] is not None
    assert result["roc_auc_95ci"] is not None
    assert result["pr_auc_95ci"] is not None
    assert result["f1_95ci"] is not None


def test_evaluation_keeps_tasks_separate() -> None:
    records = []
    for index in range(20):
        records.append({"task": "deepfake", "label": 1, "score": 0.8, "sample_id": f"d{index}"})
        records.append({"task": "content_safety:weapon_display", "label": 0, "score": 0.1, "sample_id": f"c{index}"})
    result = evaluate_by_task(records)
    assert set(result) == {"deepfake", "content_safety:weapon_display"}
    assert result["deepfake"]["status"] == "insufficient_samples"
    assert result["content_safety:weapon_display"]["status"] == "insufficient_samples"


def test_evidence_normalization_uses_reference_labels_not_model_verdict() -> None:
    records = normalize({
        "schema": "controlled",
        "samples": [{
            "sample_id": "s1",
            "reference_labels": ["weapon_display"],
            "result": {
                "verdict": "safe",
                "categories": [{"code": "weapon_display", "confidence": 0.91}],
            },
        }],
    }, task="content_safety:weapon_display", positive_label="weapon_display")
    assert records[0]["label"] == 1
    assert records[0]["score"] == 0.91


def test_deepfake_benchmark_normalization_preserves_labels_and_scores() -> None:
    records = normalize_deepfake({
        "model_source": "checkpoint-x",
        "model_sha256": "weights-hash",
        "split": "test",
        "results": [{"dataset": "demo", "path": "a.jpg", "label": 1, "p_fake": 0.83}],
    })
    assert records == [{
        "sample_id": "a.jpg",
        "task": "deepfake",
        "label": 1,
        "score": 0.83,
        "dataset": "demo",
        "split": "test",
        "model_version": "checkpoint-x",
        "source_sha256": "weights-hash",
    }]


def test_evaluation_status_promotes_only_label_backed_evidence() -> None:
    status = evaluation_status()
    assert status["status"] == "partially_calibrated"
    assert status["claim_level"].startswith("仅部分模块有足量独立标签")
    assert "无标签盲测只能报告模型分数分布" in status["boundary"]
    assert status["minimum_samples"] == {"total": 30, "per_class": 5}
    assert {item["task"] for item in status["tasks"]} >= {"deepfake:validation", "deepfake:test"}
    deepfake_test = next(item for item in status["tasks"] if item["task"] == "deepfake:test")
    assert deepfake_test["evidence_artifact"] == "df40-statistical-evaluation-20260809.json"
    assert deepfake_test["model_version"] == "CLIP-ViT-L/14 deepfake checkpoint"
    assert len(deepfake_test["weights_sha256"]) == 64
    assert next(item for item in status["tasks"] if item["task"] == "content_safety:unsafebench")["status"] == "pending_access"
    personal_data = next(item for item in status["tasks"] if item["task"] == "content_safety:personal_data")
    assert personal_data["status"] == "ready"
    assert personal_data["sample_count"] == 30
    assert personal_data["positive_count"] == 5
    assert personal_data["negative_count"] == 25
    assert personal_data["dataset"] == "mm_safetybench_pii_ocr"
    assert personal_data["split"] == "test"
    assert personal_data["model_version"] == "claude-sonnet-4-6"
    assert personal_data["evidence_artifact"] == "content-safety-personal-data-statistical-evaluation-30-20260809.json"
    assert personal_data["metrics"]["accuracy"] == 0.9333
    assert personal_data["metrics"]["roc_auc"] == 0.984
    adult = next(item for item in status["tasks"] if item["task"] == "content_safety:adult_content")
    assert adult["status"] == "ready"
    assert adult["sample_count"] == 75
    assert adult["positive_count"] == 15
    assert adult["negative_count"] == 60
    assert adult["metrics"]["accuracy"] == 0.8
    assert adult["metrics"]["recall"] == 0.0
    assert adult["quality_state"] == "unsafe_for_automation"
    assert adult["quality_summary"] == "召回率过低，不可自动放行"
    assert adult["threshold"] == 0.5
    assert adult["confusion_matrix"] == {"tp": 0, "tn": 60, "fp": 0, "fn": 15}
    weapon = next(item for item in status["tasks"] if item["task"] == "content_safety:weapon_display")
    assert weapon["metrics"]["recall"] == 1.0
    assert weapon["metrics"]["f1"] == 0.7317
    assert weapon["metrics"]["pr_auc"] == 0.7149
    assert status["summary"]["blocked"] >= 1
    assert status["summary"]["pending"] >= 1
    assert all(item["status"] == "ready" for item in status["tasks"] if item["task"] in {"deepfake:validation", "deepfake:test"})
    assert next(item for item in status["tasks"] if item["task"] == "deepfake:faceforensics_blind")["status"] == "unlabeled"
