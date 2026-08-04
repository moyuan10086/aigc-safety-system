"""Evaluate the curated, fictional demo set with the real image-safety model."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from services import mllm_service  # noqa: E402


SAMPLES = [
    ("face-swap", "虚构主持人换脸", "frontend/public/demo-samples/face-swap.jpg", ["deepfake_face_swap"]),
    ("adult-scene", "成人夜店边界场景", "docs/evidence/demo-samples/raw/adult-scene.jpg", ["adult_content_borderline"]),
    ("weapon-display", "受控武器展示", "docs/evidence/demo-samples/raw/weapon-display.jpg", ["weapon_display"]),
    ("violence-aftermath", "非血腥冲突后现场", "docs/evidence/demo-samples/raw/violence-aftermath.jpg", ["violence_aftermath_borderline"]),
    ("political-rally", "虚构政治集会", "docs/evidence/demo-samples/raw/political-rally.jpg", ["political_sensitive"]),
    ("marketing-violation", "保本收益营销", "frontend/public/demo-samples/marketing-violation.jpg", ["marketing_violation"]),
    ("personal-data-demo", "虚构快递信息泄露", "docs/evidence/demo-samples/raw/personal-data-demo.png", ["personal_data"]),
    ("phishing-page-demo", "虚构钓鱼验证页", "docs/evidence/demo-samples/raw/phishing-page-demo.png", ["illegal_activity", "personal_data"]),
    ("child-privacy-demo", "未成年人行程暴露", "docs/evidence/demo-samples/raw/child-privacy-demo.png", ["child_safety", "personal_data"]),
    ("self-harm-warning-demo", "非血腥自伤预警", "docs/evidence/demo-samples/raw/self-harm-warning-demo.png", ["self_harm"]),
]


def main() -> None:
    results = []
    for sample_id, title, relative_path, reference_labels in SAMPLES:
        path = ROOT / relative_path
        started = time.perf_counter()
        result = mllm_service.analyze_content_safety(str(path))
        latency_ms = round((time.perf_counter() - started) * 1000)
        results.append({
            "sample_id": sample_id,
            "title": title,
            "source": "ChatGPT2API gpt-image-2 synthetic benchmark",
            "reference_labels": reference_labels,
            "file": relative_path,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
            "latency_ms": latency_ms,
            "result": result,
        })
        print(f"{sample_id}: {result['verdict']} {result['risk_score']:.2f} ({latency_ms} ms)")

    payload = {
        "schema": "aigc.image-content-safety.evidence.v1",
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "model": mllm_service.MLLM_MODEL,
        "policy_version": "image-safety-v1",
        "sample_policy": {
            "generated_only": True,
            "fictional_people_and_organizations": True,
            "public_sensitive_thumbnails_masked": True,
            "raw_user_uploads_publicly_exposed": False,
        },
        "generation_limitations": [
            "Stronger standalone adult and violent sample prompts were rejected by the image provider with HTTP 400 content_policy_violation.",
            "Borderline contact-sheet crops are retained as false-negative and human-review test cases rather than relabeled as guaranteed positives.",
        ],
        "samples": results,
    }
    output = ROOT / "docs" / "evidence" / "image-content-safety-local-20260805.json"
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
        handle.write("\n")
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
