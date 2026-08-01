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
