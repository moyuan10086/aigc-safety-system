"""
MLLM 可解释性检测服务 — 复用 mllm-defake，图片自动压缩
"""
import base64
import io
import json
import re
import sys
from pathlib import Path

import httpx
from PIL import Image
from openai import OpenAI
from config import MLLM_API_KEY, MLLM_BASE_URL, MLLM_MODEL, PROXY_URL

MLLM_ROOT = Path(__file__).parents[2] / "mllm-defake"
sys.path.insert(0, str(MLLM_ROOT))

CONTENT_SAFETY_CATEGORIES = {
    "adult_content": "疑似成人内容",
    "weapon_display": "疑似武器展示",
    "graphic_violence": "疑似暴力血腥",
    "political_sensitive": "疑似政治敏感",
    "marketing_violation": "疑似营销违规",
    "illegal_activity": "疑似违法活动",
    "self_harm": "疑似自伤风险",
    "child_safety": "疑似未成年人风险",
    "personal_data": "疑似个人敏感信息",
}


def _make_client() -> OpenAI:
    if PROXY_URL:
        return OpenAI(api_key=MLLM_API_KEY, base_url=MLLM_BASE_URL,
                      http_client=httpx.Client(proxy=PROXY_URL, timeout=60))
    return OpenAI(api_key=MLLM_API_KEY, base_url=MLLM_BASE_URL)


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


def analyze(image_path: str) -> dict:
    client = _make_client()
    image_url = _encode_compressed(image_path)

    resp = client.chat.completions.create(
        model=MLLM_MODEL,
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
    raw = resp.choices[0].message.content
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {"verdict": "uncertain", "confidence": 0.5, "evidence": [],
            "regions": [], "explanation": raw}


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


def normalize_content_safety(payload: dict, *, model: str = MLLM_MODEL) -> dict:
    """Normalize untrusted model JSON into the public content-safety contract."""
    categories = []
    seen = set()
    raw_categories = payload.get("categories")
    if not isinstance(raw_categories, list):
        raw_categories = []
    for item in raw_categories:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().lower()
        if code not in CONTENT_SAFETY_CATEGORIES or code in seen:
            continue
        confidence = _score(item.get("confidence"))
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

    risk_score = max([_score(payload.get("risk_score"))] + [item["confidence"] for item in categories])
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
        "summary": str(payload.get("summary") or "模型未提供摘要").strip()[:500],
        "model": model,
        "requires_human_review": requested == "review",
        "policy_version": "image-safety-v1",
    }


def _request_content_safety(image_path: str) -> str:
    client = _make_client()
    image_url = _encode_compressed(image_path)
    category_list = ", ".join(CONTENT_SAFETY_CATEGORIES)
    response = client.chat.completions.create(
        model=MLLM_MODEL,
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
                        '"categories":[{"code":"category_code","confidence":0.0,'
                        '"severity":"low|medium|high|critical","evidence":"中文可见证据"}],'
                        '"summary":"中文审核摘要"}。不确定时 verdict=review；不要把 AI 生成痕迹本身当作内容风险；'
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
    raw = _request_content_safety(image_path)
    payload = _json_object(raw)
    normalized = normalize_content_safety(payload)
    if not payload:
        normalized.update({
            "verdict": "review",
            "safe": False,
            "requires_human_review": True,
            "summary": "模型输出无法结构化解析，已转人工复核",
        })
    return normalized
