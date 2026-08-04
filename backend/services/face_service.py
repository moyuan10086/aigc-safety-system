"""Non-identifying face detection and explainable image-quality evidence."""

from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable


MIN_IMAGE_SIDE = 480
MIN_FACE_AREA_RATIO = 0.025
MIN_EDGE_MARGIN_RATIO = 0.02
MIN_SHARPNESS = 80.0
MIN_BRIGHTNESS = 45.0
MAX_BRIGHTNESS = 215.0

REVIEW_REASON_LABELS = {
    "image_decode_failed": "图像无法解码，请检查文件格式或重新上传",
    "face_detector_missing": "人脸检测器不可用，请转人工复核",
    "face_analysis_unavailable": "人脸质量分析暂不可用，请转人工复核",
    "low_resolution": f"图像短边低于 {MIN_IMAGE_SIDE} 像素",
    "blurred": "整幅图像清晰度不足",
    "underexposed": "整幅图像曝光不足",
    "overexposed": "整幅图像曝光过度",
    "no_face": "未检测到可审核的正面人脸",
    "multiple_faces": "检测到多张人脸，需要确认主要审核对象",
    "face_too_small": "人脸面积占比过小，局部证据可能不可靠",
    "face_near_edge": "人脸贴近图像边缘或存在截断",
    "face_blurred": "人脸区域清晰度不足",
    "face_underexposed": "人脸区域曝光不足",
    "face_overexposed": "人脸区域曝光过度",
}


def _append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _quality_flags(sharpness: float, brightness: float, *, prefix: str = "") -> list[str]:
    flags: list[str] = []
    if sharpness < MIN_SHARPNESS:
        flags.append(f"{prefix}blurred")
    if brightness < MIN_BRIGHTNESS:
        flags.append(f"{prefix}underexposed")
    elif brightness > MAX_BRIGHTNESS:
        flags.append(f"{prefix}overexposed")
    return flags


def _review_reasons(flags: Iterable[str]) -> list[str]:
    return [REVIEW_REASON_LABELS[flag] for flag in flags if flag in REVIEW_REASON_LABELS]


def _unavailable(reason: str, *, width: int | None = None, height: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "unavailable",
        "face_detected": False if reason == "image_decode_failed" else None,
        "face_count": 0 if reason == "image_decode_failed" else None,
        "reason": reason,
        "quality": "review",
        "quality_flags": [reason],
        "review_recommended": True,
        "review_reasons": _review_reasons([reason]),
        "faces": [],
        "primary_face_index": None,
        "capability": "face_detection_and_quality_only",
        "identity_analysis": False,
        "evidence_version": "2.0",
    }
    if width is not None:
        result["image_width"] = width
    if height is not None:
        result["image_height"] = height
    return result


def _load_detector(cv2: Any) -> Any | None:
    source = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    if not source.exists():
        return None

    candidates = [source]
    if not str(source).isascii():
        cache_dir = Path(tempfile.gettempdir()) / "aigc-safety-face"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = cache_dir / source.name
        if not cached.exists() or cached.stat().st_size != source.stat().st_size:
            shutil.copyfile(source, cached)
        candidates.insert(0, cached)

    for candidate in candidates:
        detector = cv2.CascadeClassifier(str(candidate))
        if not detector.empty():
            return detector
    return None


def analyze_detected_faces(image: Any, boxes: Iterable[Iterable[int]]) -> dict[str, Any]:
    """Build deterministic quality evidence from an image and detector boxes."""
    import cv2

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image_sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    image_brightness = float(gray.mean())

    normalized_boxes: list[tuple[int, int, int, int]] = []
    for raw_box in boxes:
        x, y, box_width, box_height = (int(value) for value in raw_box)
        if box_width <= 0 or box_height <= 0:
            continue
        left = max(0, min(x, width))
        top = max(0, min(y, height))
        right = max(left, min(x + box_width, width))
        bottom = max(top, min(y + box_height, height))
        if right > left and bottom > top:
            normalized_boxes.append((left, top, right - left, bottom - top))

    face_evidence: list[dict[str, Any]] = []
    image_area = max(1, width * height)
    image_diagonal_half = math.hypot(0.5, 0.5)
    for index, (x, y, box_width, box_height) in enumerate(normalized_boxes):
        roi = gray[y : y + box_height, x : x + box_width]
        face_sharpness = float(cv2.Laplacian(roi, cv2.CV_64F).var())
        face_brightness = float(roi.mean())
        area_ratio = (box_width * box_height) / image_area
        center_x = (x + box_width / 2) / max(1, width)
        center_y = (y + box_height / 2) / max(1, height)
        center_offset = math.hypot(center_x - 0.5, center_y - 0.5) / image_diagonal_half
        edge_margin = min(x, y, width - (x + box_width), height - (y + box_height))
        edge_margin_ratio = max(0.0, edge_margin / max(1, min(width, height)))

        flags: list[str] = []
        if area_ratio < MIN_FACE_AREA_RATIO:
            flags.append("face_too_small")
        if edge_margin_ratio < MIN_EDGE_MARGIN_RATIO:
            flags.append("face_near_edge")
        flags.extend(_quality_flags(face_sharpness, face_brightness, prefix="face_"))
        face_evidence.append(
            {
                "index": index,
                "box": {"x": x, "y": y, "width": box_width, "height": box_height},
                "area_ratio": round(area_ratio, 4),
                "center_offset": round(center_offset, 4),
                "edge_margin_ratio": round(edge_margin_ratio, 4),
                "sharpness": round(face_sharpness, 1),
                "brightness": round(face_brightness, 1),
                "quality": "good" if not flags else "review",
                "quality_flags": flags,
                "review_reasons": _review_reasons(flags),
            }
        )

    primary_face_index = (
        max(range(len(face_evidence)), key=lambda item: face_evidence[item]["area_ratio"])
        if face_evidence
        else None
    )
    quality_flags: list[str] = []
    if min(width, height) < MIN_IMAGE_SIDE:
        quality_flags.append("low_resolution")
    quality_flags.extend(_quality_flags(image_sharpness, image_brightness))
    if not face_evidence:
        quality_flags.append("no_face")
    elif len(face_evidence) > 1:
        quality_flags.append("multiple_faces")
    for face in face_evidence:
        for flag in face["quality_flags"]:
            _append_once(quality_flags, flag)

    largest_ratio = (
        face_evidence[primary_face_index]["area_ratio"] if primary_face_index is not None else 0.0
    )
    return {
        "status": "detected" if face_evidence else "not_detected",
        "face_detected": bool(face_evidence),
        "face_count": len(face_evidence),
        "boxes": [face["box"] for face in face_evidence],
        "faces": face_evidence,
        "primary_face_index": primary_face_index,
        "image_width": width,
        "image_height": height,
        "largest_face_ratio": round(largest_ratio, 4),
        "sharpness": round(image_sharpness, 1),
        "brightness": round(image_brightness, 1),
        "quality": "good" if not quality_flags else "review",
        "quality_flags": quality_flags,
        "review_recommended": bool(quality_flags),
        "review_reasons": _review_reasons(quality_flags),
        "detector": "OpenCV Haar Cascade",
        "capability": "face_detection_and_quality_only",
        "identity_analysis": False,
        "evidence_version": "2.0",
    }


def inspect(path: str) -> dict[str, Any]:
    try:
        import cv2

        image = cv2.imread(path)
        if image is None:
            return _unavailable("image_decode_failed")
        height, width = image.shape[:2]
        cascade = _load_detector(cv2)
        if cascade is None:
            return _unavailable("face_detector_missing", width=width, height=height)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        min_size = max(24, min(width, height) // 12)
        boxes = cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(min_size, min_size),
        )
        return analyze_detected_faces(image, boxes)
    except Exception as exc:
        result = _unavailable("face_analysis_unavailable")
        result["error_type"] = type(exc).__name__
        return result
