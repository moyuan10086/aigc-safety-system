"""Normalize untrusted model classifier output without exposing raw text.

The model gateway is allowed to return JSON, fenced JSON, or a short JSON
object embedded in explanatory text.  Anything else is an uncertainty signal,
not a safe result.  Raw model output is intentionally never returned.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


_VERDICT_ALIASES = {
    "safe": "safe",
    "allow": "safe",
    "benign": "safe",
    "borderline": "borderline",
    "review": "borderline",
    "controversial": "borderline",
    "unsafe": "unsafe",
    "block": "unsafe",
    "blocked": "unsafe",
}
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def _candidate_objects(raw: str) -> list[tuple[str, Any]]:
    candidates: list[tuple[str, Any]] = []
    fenced = _FENCE_RE.findall(raw)
    for text in [*fenced, raw]:
        text = text.strip()
        if not text:
            continue
        try:
            candidates.append(("json" if text == raw else "fenced_json", json.loads(text)))
            continue
        except json.JSONDecodeError:
            pass
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                value, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            candidates.append(("embedded_json", value))
            break
    return candidates


def normalize_classifier_output(
    raw: str,
    *,
    allowed_categories: set[str],
    max_chars: int = 8_000,
) -> dict[str, Any]:
    """Return a privacy-safe normalized classifier result.

    ``status`` is ``ok`` only when a JSON object with a recognized verdict or
    a usable category score is parsed.  Malformed output is ``inconclusive``.
    """
    text = str(raw or "")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    base = {
        "status": "inconclusive",
        "output_sha256": digest,
        "output_length": len(text),
        "parse_mode": None,
        "verdict": None,
        "categories": [],
        "scores": {},
        "reason": "模型输出未通过结构化校验",
    }
    for parse_mode, parsed in _candidate_objects(text[:max_chars]):
        if not isinstance(parsed, dict):
            continue
        verdict_value = str(parsed.get("verdict", parsed.get("safety", ""))).strip().lower()
        verdict = _VERDICT_ALIASES.get(verdict_value)
        raw_scores = parsed.get("scores") if isinstance(parsed.get("scores"), dict) else {}
        scores: dict[str, float] = {}
        for category, score in raw_scores.items():
            category = str(category)
            if category not in allowed_categories:
                continue
            try:
                scores[category] = round(min(1.0, max(0.0, float(score))), 3)
            except (TypeError, ValueError):
                continue
        raw_categories = parsed.get("categories", [])
        if isinstance(raw_categories, str):
            raw_categories = re.split(r"[,;|]", raw_categories)
        categories = [
            str(category).strip()
            for category in raw_categories
            if str(category).strip() in allowed_categories
        ] if isinstance(raw_categories, list) else []
        categories = list(dict.fromkeys(categories + list(scores)))
        if verdict is None and not scores and not categories:
            continue
        reason = str(parsed.get("reason", parsed.get("analysis", ""))).strip()[:240]
        return {
            **base,
            "status": "ok",
            "parse_mode": parse_mode,
            "verdict": verdict,
            "categories": categories,
            "scores": scores,
            "reason": reason or "结构化模型结果已解析",
        }
    return base
