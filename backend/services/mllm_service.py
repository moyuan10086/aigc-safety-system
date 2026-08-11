"""
MLLM 可解释性检测服务 — 复用 mllm-defake，图片自动压缩
"""
import base64
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path

import httpx
from PIL import Image
from openai import OpenAI
import config
from services import nudenet_service, unsafe_bench_service

MLLM_ROOT = Path(__file__).parents[2] / "mllm-defake"
sys.path.insert(0, str(MLLM_ROOT))

CONTENT_SAFETY_CATEGORIES = {
    "adult_content": "疑似成人内容",
    "weapon_display": "疑似武器展示",
    "violence": "疑似暴力血腥",
    "political_sensitive": "疑似政治敏感",
    "marketing_violation": "疑似营销违规",
    "illegal_activity": "疑似违法活动",
    "self_harm": "疑似自伤风险",
    "child_safety": "疑似未成年人风险",
    "personal_data": "疑似个人敏感信息",
}

# Keep one public category vocabulary across the API, evaluation manifests and
# UI. Older prompts/checkpoints may still emit ``graphic_violence``.
CONTENT_SAFETY_ALIASES = {
    "graphic_violence": "violence",
}


def _make_client() -> OpenAI:
    if config.PROXY_URL:
        return OpenAI(api_key=config.MLLM_API_KEY, base_url=config.MLLM_BASE_URL,
                      timeout=config.MLLM_TIMEOUT_SECONDS, max_retries=1,
                      http_client=httpx.Client(proxy=config.PROXY_URL, timeout=config.MLLM_TIMEOUT_SECONDS))
    return OpenAI(api_key=config.MLLM_API_KEY, base_url=config.MLLM_BASE_URL,
                  timeout=config.MLLM_TIMEOUT_SECONDS, max_retries=1)


def _encode_compressed(path: str, max_bytes: int = 4 * 1024 * 1024) -> str:
    img = Image.open(path).convert("RGB")
    if max(img.size) > 1920:
        img.thumbnail((1920, 1920), Image.LANCZOS)
    for quality in [85, 70, 50, 30]:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        data = buf.getvalue()
        if len(data) <= max_bytes:
            return f"data:image/jpeg;base64,{base64.b64encode(data).decode()}"
    img.thumbnail((800, 800), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=40)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"


def _request_authenticity(image_path: str) -> str:
    client = _make_client()
    image_url = _encode_compressed(image_path)

    resp = client.chat.completions.create(
        model=config.MLLM_MODEL,
        messages=[
            {"role": "system", "content": "You are an expert in detecting AI-generated and deepfake images."},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": (
                    "Analyze this image for signs of AI generation or deepfake manipulation. "
                    'Respond in JSON with keys: "verdict" (real/fake/uncertain), '
                    '"confidence" (0.0-1.0), "evidence" (list of artifacts), '
                    '"regions" (list of suspicious regions), "explanation" (one paragraph in Chinese).'
                )},
            ]},
        ],
        max_tokens=1024,
    )
    return resp.choices[0].message.content or ""


def _json_object(raw: str) -> dict:
    decoder = json.JSONDecoder()
    text = raw or ""
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def _score(value, default: float = 0.0) -> float:
    try:
        return round(max(0.0, min(1.0, float(value))), 4)
    except (TypeError, ValueError):
        return default


def _short_list(value, *, limit: int = 16) -> list:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value[:limit]:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip()[:240])
        elif isinstance(item, dict):
            normalized.append({str(key)[:40]: str(raw)[:160] for key, raw in list(item.items())[:8]})
    return normalized


def normalize_authenticity(payload: dict, *, model: str | None = None) -> dict:
    """Normalize untrusted multimodal output into the authenticity contract."""
    verdict = str(payload.get("verdict") or "").strip().lower()
    if verdict not in {"real", "fake", "uncertain"}:
        verdict = "uncertain"
    confidence = _score(payload.get("confidence"), default=0.5)
    evidence = _short_list(payload.get("evidence"))
    explanation = str(payload.get("explanation") or "").strip()[:1200]
    if verdict in {"real", "fake"} and (confidence < 0.55 or not evidence):
        verdict = "uncertain"
    return {
        "verdict": verdict,
        "confidence": confidence,
        "evidence": evidence,
        "regions": _short_list(payload.get("regions")),
        "explanation": explanation or "模型未提供足够的可解释证据，已转人工复核",
        "model": model or config.MLLM_MODEL,
        "requires_human_review": verdict == "uncertain",
    }


def analyze(image_path: str) -> dict:
    """Run MLLM authenticity analysis and fail closed to an uncertain result."""
    started = time.perf_counter()
    content_hash = hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
    model = config.MLLM_MODEL
    try:
        raw = _request_authenticity(image_path)
    except Exception:
        return {
            "verdict": "uncertain",
            "confidence": 0.0,
            "evidence": [],
            "regions": [],
            "explanation": "多模态真实性模型暂时不可用，已转人工复核",
            "model": model,
            "model_called": False,
            "model_attempted": True,
            "requires_human_review": True,
            "status": "degraded",
            "error_code": "model_unavailable",
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "content_hash": content_hash,
        }
    payload = _json_object(raw)
    result = normalize_authenticity(payload, model=model)
    valid_output = bool(payload)
    if not valid_output:
        result.update({
            "verdict": "uncertain",
            "requires_human_review": True,
            "explanation": "模型输出无法结构化解析，已转人工复核",
        })
    result.update({
        "model_called": True,
        "model_attempted": True,
        "status": "completed" if valid_output else "degraded",
        "error_code": None if valid_output else "invalid_model_output",
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "content_hash": content_hash,
    })
    return result


def normalize_content_safety(payload: dict, *, model: str | None = None) -> dict:
    """Normalize untrusted model JSON into the public content-safety contract."""
    categories = []
    seen = set()
    category_scores: dict[str, float] = {}
    raw_scores = payload.get("category_scores")
    if isinstance(raw_scores, dict):
        for raw_code, value in raw_scores.items():
            code = CONTENT_SAFETY_ALIASES.get(str(raw_code).strip().lower(), str(raw_code).strip().lower())
            if code in CONTENT_SAFETY_CATEGORIES:
                category_scores[code] = _score(value)
    raw_categories = payload.get("categories")
    if not isinstance(raw_categories, list):
        raw_categories = []
    for item in raw_categories:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().lower()
        code = CONTENT_SAFETY_ALIASES.get(code, code)
        if code not in CONTENT_SAFETY_CATEGORIES or code in seen:
            continue
        confidence = _score(item.get("confidence"))
        category_scores[code] = max(category_scores.get(code, 0.0), confidence)
        if confidence < 0.25:
            continue
        seen.add(code)
        severity = str(item.get("severity") or "medium").strip().lower()
        if severity not in {"low", "medium", "high", "critical"}:
            severity = "medium"
        categories.append({
            "code": code,
            "label": CONTENT_SAFETY_CATEGORIES[code],
            "confidence": confidence,
            "severity": severity,
            "evidence": str(item.get("evidence") or "").strip()[:240],
        })

    missing_category_scores = sorted(set(CONTENT_SAFETY_CATEGORIES) - set(category_scores))
    risk_score = max(
        [_score(payload.get("risk_score"))]
        + list(category_scores.values())
        + [item["confidence"] for item in categories]
    )
    requested = str(payload.get("verdict") or "").strip().lower()
    if requested not in {"safe", "review", "unsafe"}:
        requested = "unsafe" if risk_score >= 0.8 else "review" if risk_score >= 0.35 else "safe"
    if categories and requested == "safe":
        requested = "review"
    if not categories and requested == "unsafe":
        requested = "review"
    return {
        "verdict": requested,
        "safe": requested == "safe",
        "risk_score": risk_score,
        "categories": categories,
        "category_scores": category_scores,
        "missing_category_scores": missing_category_scores,
        "score_coverage": round(len(category_scores) / len(CONTENT_SAFETY_CATEGORIES), 4),
        "summary": str(payload.get("summary") or "模型未提供摘要").strip()[:500],
        "model": model or config.MLLM_MODEL,
        "requires_human_review": requested == "review",
        "policy_version": "image-safety-v1",
    }


def _request_content_safety(image_path: str) -> str:
    client = _make_client()
    image_url = _encode_compressed(image_path)
    category_list = ", ".join(CONTENT_SAFETY_CATEGORIES)
    response = client.chat.completions.create(
        model=config.MLLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a conservative image content-safety reviewer. Classify visible content only. "
                    "Do not identify real people and do not infer protected attributes."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": (
                        "审核图片中的内容安全风险。仅使用以下类别代码："
                        f"{category_list}。返回单个 JSON 对象："
                        '{"verdict":"safe|review|unsafe","risk_score":0.0,'
                        '"category_scores":{"adult_content":0.0,"weapon_display":0.0,'
                        '"violence":0.0,"political_sensitive":0.0,"marketing_violation":0.0,'
                        '"illegal_activity":0.0,"self_harm":0.0,"child_safety":0.0,'
                        '"personal_data":0.0},'
                        '"categories":[{"code":"category_code","confidence":0.0,'
                        '"severity":"low|medium|high|critical","evidence":"中文可见证据"}],'
                        '"summary":"中文审核摘要"}。category_scores 必须逐项返回上述全部类别，'
                        '即使未发现风险也要给出分数；categories 只列出有可见证据的类别。'
                        '不确定时 verdict=review；不要把 AI 生成痕迹本身当作内容风险；'
                        "字符串值中不得出现未转义的双引号，引用画面文字时使用中文方括号。"
                    )},
                ],
            },
        ],
        max_tokens=1200,
    )
    return response.choices[0].message.content or ""


def analyze_content_safety(image_path: str) -> dict:
    """Run an actual multimodal content-safety classification call."""
    content_hash = hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
    # Specialist models remain auxiliary evidence: a provider outage must not
    # replace the primary MLLM decision or turn into a false "safe" result.
    specialist_evidence = {
        "nudenet": nudenet_service.analyze(image_path),
        "unsafe_bench": unsafe_bench_service.analyze(image_path),
    }
    try:
        raw = _request_content_safety(image_path)
    except Exception:
        return {
            "verdict": "review",
            "safe": False,
            "risk_score": 0.0,
            "categories": [],
            "category_scores": {},
            "missing_category_scores": sorted(CONTENT_SAFETY_CATEGORIES),
            "score_coverage": 0.0,
            "summary": "视觉内容安全模型暂时不可用，已转人工复核",
            "model": config.MLLM_MODEL,
            "requires_human_review": True,
            "policy_version": "image-safety-v1",
            "status": "degraded",
            "error_code": "model_unavailable",
            "content_hash": content_hash,
            "specialist_evidence": specialist_evidence,
        }
    payload = _json_object(raw)
    normalized = normalize_content_safety(payload)
    if not payload:
        normalized.update({
            "verdict": "review",
            "safe": False,
            "requires_human_review": True,
            "summary": "模型输出无法结构化解析，已转人工复核",
        })
    normalized["status"] = "completed" if payload else "degraded"
    normalized["error_code"] = None if payload else "invalid_model_output"
    if payload and normalized["missing_category_scores"]:
        normalized.update({
            "verdict": "review",
            "safe": False,
            "requires_human_review": True,
            "status": "degraded",
            "error_code": "incomplete_category_scores",
            "summary": "模型未返回完整的逐类别分数，已转人工复核。" + normalized["summary"],
        })
    normalized["content_hash"] = content_hash
    normalized["specialist_evidence"] = specialist_evidence
    return normalized
