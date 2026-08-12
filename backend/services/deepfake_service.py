"""Pinned, face-aligned inference for a configured DFDet checkpoint."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import sys
import tempfile
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import httpx
import numpy as np
import torch
from huggingface_hub import hf_hub_download, snapshot_download
from PIL import Image

import config

BACKEND_DIR = Path(__file__).parents[1]
DFDET_ROOT = Path(__file__).parents[2] / "deepfake-detection"
if str(DFDET_ROOT) not in sys.path:
    sys.path.insert(0, str(DFDET_ROOT))

from src.config import Config  # noqa: E402
from src.model.dfdet import DeepfakeDetectionModel  # noqa: E402

PREPROCESSING_VERSION = "deepfakebench-5point-align-v1"
_device = "cuda" if torch.cuda.is_available() else "cpu"
_model: Any | None = None
_preprocess: Any | None = None
_load_lock = threading.Lock()
_cache_lock = threading.Lock()
_digest_lock = threading.Lock()
_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
_digest_cache: OrderedDict[tuple[str, int, int], str] = OrderedDict()
_runtime: dict[str, Any] = {
    "state": "not_loaded",
    "model_loaded": False,
    "last_inference_at": None,
    "last_latency_ms": None,
    "last_error_code": None,
}
_logger = logging.getLogger(__name__)


class DeepfakeServiceError(RuntimeError):
    """Controlled local model or preprocessing failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _runtime_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


def model_path() -> Path:
    return _runtime_path(config.DEEPFAKE_MODEL_PATH)


def face_model_path() -> Path:
    return _runtime_path(config.DEEPFAKE_FACE_MODEL_PATH)


def _sha256(path: Path) -> str:
    stat = path.stat()
    key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    with _digest_lock:
        cached = _digest_cache.get(key)
        if cached:
            _digest_cache.move_to_end(key)
            return cached
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    with _digest_lock:
        _digest_cache[key] = value
        _digest_cache.move_to_end(key)
        while len(_digest_cache) > 64:
            _digest_cache.popitem(last=False)
    return value


def _valid_digest(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _verify(path: Path, expected_digest: str, code: str) -> str:
    expected = str(expected_digest or "").strip().lower()
    if not path.is_file():
        raise DeepfakeServiceError(f"{code}_missing", "required artifact is missing")
    if not _valid_digest(expected):
        raise DeepfakeServiceError(f"{code}_digest_unconfigured", "artifact digest is not configured")
    actual = _sha256(path)
    if actual != expected:
        raise DeepfakeServiceError(f"{code}_digest_mismatch", "artifact digest verification failed")
    return actual


def artifact_status() -> dict[str, Any]:
    """Return metadata-safe artifact integrity and runtime inference state."""
    artifacts: dict[str, dict[str, Any]] = {}
    for name, path, digest in (
        ("checkpoint", model_path(), config.DEEPFAKE_MODEL_SHA256),
        ("face_detector", face_model_path(), config.DEEPFAKE_FACE_MODEL_SHA256),
    ):
        try:
            actual = _verify(path, digest, name)
            artifacts[name] = {"status": "verified", "sha256": actual}
        except DeepfakeServiceError as exc:
            artifacts[name] = {"status": "unavailable", "error_code": exc.code}
        except OSError:
            artifacts[name] = {"status": "unavailable", "error_code": f"{name}_unreadable"}
    return {"artifacts": artifacts, "runtime": runtime_status()}


def _ensure_checkpoint() -> Path:
    path = model_path()
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        downloaded = hf_hub_download(
            repo_id=config.DEEPFAKE_MODEL_REPO,
            filename=config.DEEPFAKE_MODEL_FILENAME,
            revision=config.DEEPFAKE_MODEL_REVISION,
            local_dir=str(path.parent),
        )
        downloaded_path = Path(downloaded)
        if downloaded_path.resolve() != path.resolve():
            path = downloaded_path
    _verify(path, config.DEEPFAKE_MODEL_SHA256, "checkpoint")
    return path


def _ensure_face_model() -> Path:
    path = face_model_path()
    if path.is_file():
        _verify(path, config.DEEPFAKE_FACE_MODEL_SHA256, "face_detector")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary_name = temporary.name
            with httpx.stream("GET", config.DEEPFAKE_FACE_MODEL_URL, timeout=30.0) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes(1024 * 1024):
                    temporary.write(chunk)
        temporary_path = Path(temporary_name)
        _verify(temporary_path, config.DEEPFAKE_FACE_MODEL_SHA256, "face_detector")
        os.replace(temporary_path, path)
        temporary_name = None
    except DeepfakeServiceError:
        raise
    except Exception as exc:
        raise DeepfakeServiceError("face_detector_download_failed", "face detector download failed") from exc
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
    return path


def ensure_artifacts() -> dict[str, str]:
    """Download pinned runtime artifacts if needed and verify both digests."""
    checkpoint = _ensure_checkpoint()
    detector = _ensure_face_model()
    return {
        "checkpoint_sha256": _verify(
            checkpoint, config.DEEPFAKE_MODEL_SHA256, "checkpoint"
        ),
        "face_detector_sha256": _verify(
            detector, config.DEEPFAKE_FACE_MODEL_SHA256, "face_detector"
        ),
    }


def _backbone_snapshot(repo_id: str) -> str:
    snapshot = Path(
        snapshot_download(
            repo_id=repo_id,
            revision=config.DEEPFAKE_BACKBONE_REVISION,
            allow_patterns=[
                "config.json",
                "merges.txt",
                "model.safetensors",
                "preprocessor_config.json",
                "special_tokens_map.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.json",
            ],
        )
    ).resolve()
    # The upstream DFDet lowercases its backbone identifier. A stable lowercase
    # alias keeps local paths valid even when the Hugging Face cache path does
    # not use lowercase directory names.
    alias = Path(tempfile.gettempdir()) / "aigc-safety-deepfake" / "clip-vit-large-patch14"
    alias.parent.mkdir(parents=True, exist_ok=True)
    if alias.is_symlink():
        if alias.resolve() != snapshot:
            raise DeepfakeServiceError("backbone_alias_conflict", "backbone alias is stale")
    elif alias.exists():
        raise DeepfakeServiceError("backbone_alias_conflict", "backbone alias is not a symlink")
    else:
        alias.symlink_to(snapshot, target_is_directory=True)
    return str(alias)


def _load() -> None:
    global _model, _preprocess
    if _model is not None:
        return
    with _load_lock:
        if _model is not None:
            return
        _runtime.update({"state": "loading", "last_error_code": None})
        try:
            checkpoint_path = _ensure_checkpoint()
            checkpoint = torch.load(str(checkpoint_path), map_location="cpu", weights_only=True)
            hyper_parameters = copy.deepcopy(checkpoint["hyper_parameters"])
            backbone = str(hyper_parameters.get("backbone") or "")
            if "/" in backbone and not Path(backbone).exists():
                hyper_parameters["backbone"] = _backbone_snapshot(backbone)
            model = DeepfakeDetectionModel(Config(**hyper_parameters))
            model.load_state_dict(checkpoint["state_dict"])
            model.eval()
            preprocess = model.get_preprocessing()
            if not torch.cuda.is_available():
                model = model.float()
            _model = model.to(_device)
            _preprocess = preprocess
            _runtime.update({"state": "loaded_unprobed", "model_loaded": True})
        except DeepfakeServiceError as exc:
            _runtime.update({"state": "failed", "model_loaded": False, "last_error_code": exc.code})
            raise
        except Exception as exc:
            _logger.exception("Deepfake model load failed")
            _runtime.update(
                {"state": "failed", "model_loaded": False, "last_error_code": "model_load_failed"}
            )
            raise DeepfakeServiceError("model_load_failed", "deepfake model could not be loaded") from exc


def runtime_status() -> dict[str, Any]:
    return copy.deepcopy(_runtime)


def _target_landmarks(size: int = 256, margin: float = 0.15) -> np.ndarray:
    destination = np.array(
        [
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041],
        ],
        dtype=np.float32,
    )
    destination *= size / 112.0
    margin_pixels = size * max(0.0, margin)
    destination += margin_pixels
    destination *= size / (size + 2 * margin_pixels)
    return destination


def _align_face(image: np.ndarray, landmarks: np.ndarray, size: int = 256) -> Image.Image:
    matrix, _ = cv2.estimateAffinePartial2D(
        landmarks.astype(np.float32),
        _target_landmarks(size, config.DEEPFAKE_FACE_MARGIN),
        method=cv2.LMEDS,
    )
    if matrix is None:
        raise DeepfakeServiceError("face_alignment_failed", "face landmarks could not be aligned")
    aligned = cv2.warpAffine(
        image,
        matrix,
        (size, size),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
    )
    return Image.fromarray(cv2.cvtColor(aligned, cv2.COLOR_BGR2RGB))


def _yunet_faces(image: np.ndarray) -> list[tuple[Image.Image, dict[str, Any]]]:
    path = _ensure_face_model()
    height, width = image.shape[:2]
    detector = cv2.FaceDetectorYN_create(str(path), "", (width, height), 0.75, 0.3, 5000)
    _, rows = detector.detect(image)
    if rows is None:
        return []
    faces: list[tuple[Image.Image, dict[str, Any]]] = []
    for row in sorted(rows.tolist(), key=lambda item: item[-1], reverse=True)[: config.DEEPFAKE_MAX_FACES]:
        x, y, box_width, box_height = row[:4]
        points = np.asarray(row[4:14], dtype=np.float32).reshape(5, 2)
        eyes = sorted(points[:2], key=lambda point: point[0])
        mouth = sorted(points[3:5], key=lambda point: point[0])
        ordered = np.asarray([eyes[0], eyes[1], points[2], mouth[0], mouth[1]])
        try:
            aligned = _align_face(image, ordered)
        except DeepfakeServiceError:
            continue
        faces.append(
            (
                aligned,
                {
                    "box": {
                        "x": max(0, int(round(x))),
                        "y": max(0, int(round(y))),
                        "width": max(1, int(round(box_width))),
                        "height": max(1, int(round(box_height))),
                    },
                    "detector_score": round(float(row[-1]), 4),
                    "alignment_applied": True,
                    "preprocessing": PREPROCESSING_VERSION,
                },
            )
        )
    return faces


def _square_crop(image: Image.Image, box: dict[str, Any]) -> Image.Image | None:
    try:
        x = float(box["x"])
        y = float(box["y"])
        width = float(box["width"])
        height = float(box["height"])
    except (KeyError, TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    side = max(width, height) * (1 + 2 * max(0.0, config.DEEPFAKE_FACE_MARGIN))
    center_x, center_y = x + width / 2, y + height / 2
    return image.crop(
        (center_x - side / 2, center_y - side / 2, center_x + side / 2, center_y + side / 2)
    ).resize((256, 256), Image.Resampling.LANCZOS)


def _fallback_faces(image_path: str, face_result: dict[str, Any] | None) -> list[tuple[Image.Image, dict[str, Any]]]:
    if face_result is None:
        from services import face_service

        face_result = face_service.inspect(image_path)
    boxes = (face_result or {}).get("boxes") or []
    source = Image.open(image_path).convert("RGB")
    faces: list[tuple[Image.Image, dict[str, Any]]] = []
    for box in boxes[: config.DEEPFAKE_MAX_FACES]:
        crop = _square_crop(source, box)
        if crop is not None:
            faces.append(
                (
                    crop,
                    {
                        "box": box,
                        "detector_score": None,
                        "alignment_applied": False,
                        "preprocessing": "padded-square-crop-fallback-v1",
                    },
                )
            )
    return faces


def _extract_faces(
    image_path: str, face_result: dict[str, Any] | None
) -> tuple[list[tuple[Image.Image, dict[str, Any]]], str | None]:
    image = cv2.imread(image_path)
    if image is None:
        raise DeepfakeServiceError("image_decode_failed", "image could not be decoded")
    preprocessing_error = None
    try:
        aligned = _yunet_faces(image)
    except DeepfakeServiceError as exc:
        preprocessing_error = exc.code
        aligned = []
    except Exception:
        preprocessing_error = "face_alignment_failed"
        aligned = []
    if aligned:
        return aligned, None
    fallback = _fallback_faces(image_path, face_result)
    if fallback:
        return fallback, preprocessing_error or "landmark_alignment_unavailable"
    return [], preprocessing_error or "no_face_detected"


def _decision(score: float, *, aligned: bool = True) -> str:
    if score >= config.DEEPFAKE_FAKE_THRESHOLD:
        return "fake"
    if aligned and score <= config.DEEPFAKE_REAL_THRESHOLD:
        return "real"
    return "review"


def _cache_key(image_path: str, face_result: dict[str, Any] | None) -> str:
    digest = _sha256(Path(image_path))
    boxes = json.dumps((face_result or {}).get("boxes") or [], sort_keys=True, separators=(",", ":"))
    policy = (
        f"{config.DEEPFAKE_MODEL_SHA256}:{config.DEEPFAKE_FACE_MODEL_SHA256}:"
        f"{config.DEEPFAKE_REAL_THRESHOLD}:{config.DEEPFAKE_FAKE_THRESHOLD}:"
        f"{config.DEEPFAKE_FACE_MARGIN}:{boxes}"
    )
    return hashlib.sha256(f"{digest}:{policy}".encode()).hexdigest()


def _inconclusive(reason: str, *, latency_ms: float, error_code: str | None = None) -> dict[str, Any]:
    return {
        "score": 0.0,
        "label": "inconclusive",
        "confidence": 0.0,
        "status": "degraded" if error_code else "completed",
        "requires_human_review": True,
        "reason": reason,
        "error_code": error_code,
        "face_count": 0,
        "faces": [],
        "model": config.DEEPFAKE_MODEL_NAME,
        "model_origin": config.DEEPFAKE_MODEL_ORIGIN,
        "model_revision": config.DEEPFAKE_MODEL_REVISION,
        "preprocessing": PREPROCESSING_VERSION,
        "policy_version": "deepfake-triage-v1",
        "calibration_status": "production_benchmark_pending",
        "latency_ms": round(latency_ms, 1),
    }


def detect(image_path: str, face_result: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run aligned, per-face inference and aggregate using the maximum fake score."""
    started = time.perf_counter()
    try:
        if not 0 <= config.DEEPFAKE_REAL_THRESHOLD < config.DEEPFAKE_FAKE_THRESHOLD <= 1:
            raise DeepfakeServiceError("invalid_threshold_config", "deepfake thresholds are invalid")
        key = _cache_key(image_path, face_result)
        with _cache_lock:
            cached = _cache.get(key)
            if cached is not None:
                _cache.move_to_end(key)
                result = copy.deepcopy(cached)
                result["cached"] = True
                return result

        crops, preprocessing_warning = _extract_faces(image_path, face_result)
        if not crops:
            result = _inconclusive(
                "未检测到可执行局部伪造分析的人脸",
                latency_ms=(time.perf_counter() - started) * 1000,
                error_code=(
                    preprocessing_warning
                    if preprocessing_warning != "no_face_detected"
                    else None
                ),
            )
        else:
            _load()
            tensors = torch.stack([_preprocess(crop) for crop, _ in crops]).to(_device)
            if not torch.cuda.is_available():
                tensors = tensors.float()
            with torch.inference_mode():
                output = _model(tensors)
                probabilities = output.logits_labels.softmax(dim=1).float().cpu().numpy()

            face_results: list[dict[str, Any]] = []
            for index, ((_, metadata), probability) in enumerate(zip(crops, probabilities)):
                p_real, p_fake = float(probability[0]), float(probability[1])
                face_results.append(
                    {
                        "index": index,
                        **metadata,
                        "score": round(p_fake, 4),
                        "p_real": round(p_real, 4),
                        "label": _decision(p_fake, aligned=bool(metadata["alignment_applied"])),
                    }
                )
            score = max(item["score"] for item in face_results)
            all_aligned = all(item["alignment_applied"] for item in face_results)
            label = _decision(score, aligned=all_aligned)
            result = {
                "score": round(score, 4),
                "label": label,
                "confidence": round(max(score, 1 - score), 4),
                "status": "degraded" if preprocessing_warning else "completed",
                "requires_human_review": label == "review",
                "reason": (
                    "关键点对齐不可用，裁剪结果仅作为辅助证据"
                    if preprocessing_warning
                    else None
                ),
                "error_code": preprocessing_warning,
                "face_count": len(face_results),
                "faces": face_results,
                "aggregation": "max_fake_probability",
                "thresholds": {
                    "real_max": config.DEEPFAKE_REAL_THRESHOLD,
                    "fake_min": config.DEEPFAKE_FAKE_THRESHOLD,
                },
                "threshold_source": "conservative_operational_default",
                "policy_version": "deepfake-triage-v1",
                "calibration_status": "production_benchmark_pending",
                "model": config.DEEPFAKE_MODEL_NAME,
                "model_origin": config.DEEPFAKE_MODEL_ORIGIN,
                "model_revision": config.DEEPFAKE_MODEL_REVISION,
                "preprocessing": PREPROCESSING_VERSION if all_aligned else "mixed_with_bbox_fallback",
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "cached": False,
            }
            _runtime.update(
                {
                    "state": "ready",
                    "model_loaded": True,
                    "last_inference_at": _utc_now(),
                    "last_latency_ms": result["latency_ms"],
                    "last_error_code": preprocessing_warning,
                }
            )
        with _cache_lock:
            _cache[key] = copy.deepcopy(result)
            _cache.move_to_end(key)
            while len(_cache) > config.DEEPFAKE_CACHE_SIZE:
                _cache.popitem(last=False)
        return result
    except DeepfakeServiceError as exc:
        _runtime.update({"state": "failed", "last_error_code": exc.code})
        return _inconclusive(
            "Deepfake 模型暂不可用，已转人工复核",
            latency_ms=(time.perf_counter() - started) * 1000,
            error_code=exc.code,
        )
    except Exception:
        _runtime.update({"state": "failed", "last_error_code": "inference_failed"})
        return _inconclusive(
            "Deepfake 推理失败，已转人工复核",
            latency_ms=(time.perf_counter() - started) * 1000,
            error_code="inference_failed",
        )


def reset_runtime_state() -> None:
    """Clear process-local model and caches; intended for tests and controlled reloads."""
    global _model, _preprocess
    with _load_lock:
        _model = None
        _preprocess = None
        _runtime.update(
            {
                "state": "not_loaded",
                "model_loaded": False,
                "last_inference_at": None,
                "last_latency_ms": None,
                "last_error_code": None,
            }
        )
    with _cache_lock:
        _cache.clear()
