"""Local NudeNet adapter for adult-content specialist evidence."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from config import (
    NUDENET_ENABLED,
    NUDENET_MODEL_PATH,
    NUDENET_SHADOW_ONLY,
    NUDENET_THRESHOLD,
)

PROVIDER = "nudenet"
MODEL_VERSION = "3.4.2/320n"
EXPLICIT_CLASSES = {
    "ANUS_EXPOSED": "肛门暴露",
    "BUTTOCKS_EXPOSED": "臀部暴露",
    "FEMALE_BREAST_EXPOSED": "女性胸部暴露",
    "FEMALE_GENITALIA_EXPOSED": "女性生殖器暴露",
    "MALE_GENITALIA_EXPOSED": "男性生殖器暴露",
}

_detector: Any | None = None
_detector_lock = threading.Lock()


def _base(status: str, *, shadow_only: bool, latency_ms: int = 0) -> dict:
    return {
        "provider": PROVIDER,
        "status": status,
        "adult_score": None,
        "regions": [],
        "latency_ms": latency_ms,
        "model_version": MODEL_VERSION,
        "license": "AGPL-3.0",
        "source_url": "https://github.com/notAI-tech/NudeNet",
        "shadow_only": shadow_only,
        "error_code": None,
    }


def _load_detector():
    global _detector
    if _detector is not None:
        return _detector
    with _detector_lock:
        if _detector is None:
            from nudenet import NudeDetector

            kwargs = {"model_path": NUDENET_MODEL_PATH} if NUDENET_MODEL_PATH else {}
            _detector = NudeDetector(**kwargs)
    return _detector


def _score(value: Any) -> float:
    try:
        return round(max(0.0, min(1.0, float(value))), 4)
    except (TypeError, ValueError):
        return 0.0


def _box(value: Any) -> list[int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        return [max(0, int(coordinate)) for coordinate in value]
    except (TypeError, ValueError):
        return None


def analyze(
    image_path: str,
    *,
    enabled: bool = NUDENET_ENABLED,
    shadow_only: bool = NUDENET_SHADOW_ONLY,
    threshold: float = NUDENET_THRESHOLD,
    detector: Any | None = None,
) -> dict:
    """Return normalized local specialist evidence without persisting the image."""
    if not enabled:
        return _base("not_configured", shadow_only=shadow_only)

    started = time.perf_counter()
    try:
        raw_detections = (detector or _load_detector()).detect(Path(image_path).read_bytes())
    except Exception:
        result = _base(
            "inconclusive",
            shadow_only=shadow_only,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        result["error_code"] = "detector_unavailable"
        return result

    explicit_scores: list[float] = []
    regions = []
    for item in raw_detections if isinstance(raw_detections, list) else []:
        if not isinstance(item, dict):
            continue
        class_name = str(item.get("class") or "").strip().upper()
        if class_name not in EXPLICIT_CLASSES:
            continue
        score = _score(item.get("score"))
        explicit_scores.append(score)
        box = _box(item.get("box"))
        if score >= threshold and box is not None:
            regions.append({
                "class": class_name,
                "label": EXPLICIT_CLASSES[class_name],
                "score": score,
                "box": box,
            })

    adult_score = max(explicit_scores, default=0.0)
    result = _base(
        "detected" if regions else "not_detected",
        shadow_only=shadow_only,
        latency_ms=round((time.perf_counter() - started) * 1000),
    )
    result["adult_score"] = adult_score
    result["regions"] = sorted(regions, key=lambda item: item["score"], reverse=True)
    return result
