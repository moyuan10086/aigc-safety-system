import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import run_content_safety_benchmark as runner


def test_category_runner_uses_reference_labels_and_emits_separate_tasks(tmp_path, monkeypatch):
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"fixture-image")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "sample_id": "s-1",
        "image_path": image.name,
        "dataset_id": "fixture-public-export",
        "reference_labels": ["weapon_display"],
    }) + "\n", encoding="utf-8")
    monkeypatch.setattr(runner.mllm_service, "analyze_content_safety", lambda _: {
        "model": "fixture-model",
        "policy_version": "fixture-policy",
        "risk_score": 0.8,
        "verdict": "unsafe",
        "categories": [{"code": "weapon_display", "confidence": 0.83}],
    })

    output = tmp_path / "evidence.json"
    heldout = tmp_path / "heldout.jsonl"
    payload = runner.run(manifest, output, categories=("weapon_display", "violence"), heldout_output=heldout)

    assert payload["sample_count"] == 1
    assert payload["privacy"]["original_images_in_output"] is False
    assert payload["privacy"]["raw_provider_response_in_output"] is False
    records = [json.loads(line) for line in heldout.read_text(encoding="utf-8").splitlines()]
    assert {record["task"] for record in records} == {"content_safety:weapon_display", "content_safety:violence"}
    assert next(record for record in records if record["task"].endswith("weapon_display"))["label"] == 1
    assert next(record for record in records if record["task"].endswith("violence"))["label"] == 0


def test_category_runner_rejects_missing_reference_labels(tmp_path):
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"fixture-image")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"sample_id": "s-1", "image_path": image.name}) + "\n", encoding="utf-8")

    try:
        runner.run(manifest, tmp_path / "evidence.json")
    except ValueError as exc:
        assert "reference_labels" in str(exc)
    else:
        raise AssertionError("runner accepted a manifest without reference labels")
