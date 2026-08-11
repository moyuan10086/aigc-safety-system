"""Authenticated single-GPU PerspectiveVision-LLaVA inference service."""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from PIL import Image


MODEL_PATH = Path(os.getenv(
    "PERSPECTIVE_MODEL_PATH",
    "/mnt/data/perspectivevision/models/PerspectiveVision-LLaVA-LoRA",
))
BASE_MODEL_PATH = Path(os.getenv(
    "PERSPECTIVE_BASE_MODEL_PATH",
    "/mnt/data/perspectivevision/models/llava-v1.5-7b",
))
MODEL_NAME = "PerspectiveVision-LLaVA-LoRA"
MODEL_REVISION = os.getenv(
    "PERSPECTIVE_MODEL_REVISION",
    "9eb4e2e5124ae4e384db1d82b7f12061df28b2fb",
)
BASE_REVISION = os.getenv(
    "PERSPECTIVE_BASE_REVISION",
    "4481d270cc22fd5c4d1bb5df129622006ccd9234",
)
VISION_REVISION = os.getenv(
    "PERSPECTIVE_VISION_REVISION",
    "ce19dc912ca5cd21c8a653c79e251e808ccabcd1",
)
API_KEY_FILE = Path(os.getenv(
    "PERSPECTIVE_API_KEY_FILE",
    "/mnt/data/perspectivevision/api-key",
))
MAX_IMAGE_BYTES = int(os.getenv("PERSPECTIVE_MAX_IMAGE_BYTES", str(12 * 1024 * 1024)))
MAX_PENDING = int(os.getenv("PERSPECTIVE_MAX_PENDING", "8"))
MAX_NEW_TOKENS = int(os.getenv("PERSPECTIVE_MAX_NEW_TOKENS", "128"))


def _read_api_key() -> str:
    try:
        return API_KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"API key file is unavailable: {API_KEY_FILE}") from exc


def _parse_output(response: str) -> tuple[str, str | None]:
    status_match = re.search(r"Safety\s*Status\s*:\s*(Unsafe|Safe)\b", response, re.I)
    if not status_match:
        return "inconclusive", None
    status = status_match.group(1).lower()
    category_match = re.search(r"Unsafe\s*Category\s*:\s*([^\n,]+)", response, re.I)
    category = category_match.group(1).strip() if category_match else None
    if category and category.lower() == "none":
        category = None
    return status, category


def _provider_category(category: str | None) -> str | None:
    if not category:
        return None
    return re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_") or None


class PerspectiveEngine:
    def __init__(self) -> None:
        from llava.constants import (
            DEFAULT_IMAGE_TOKEN,
            DEFAULT_IM_END_TOKEN,
            DEFAULT_IM_START_TOKEN,
            IMAGE_TOKEN_INDEX,
        )
        from llava.conversation import SeparatorStyle, conv_templates
        from llava.mm_utils import KeywordsStoppingCriteria, process_images, tokenizer_image_token
        from llava.model.builder import load_pretrained_model
        from llava.utils import disable_torch_init
        from unsafe_datasets import list_unsafe_instruction

        for path in (MODEL_PATH, BASE_MODEL_PATH):
            if not path.is_dir():
                raise RuntimeError(f"model directory is missing: {path}")
        self.api_key = _read_api_key()
        if len(self.api_key) < 32:
            raise RuntimeError("API key must contain at least 32 characters")
        self.constants = (
            DEFAULT_IMAGE_TOKEN,
            DEFAULT_IM_START_TOKEN,
            DEFAULT_IM_END_TOKEN,
            IMAGE_TOKEN_INDEX,
        )
        self.conv_templates = conv_templates
        self.separator_style = SeparatorStyle
        self.stopping_criteria = KeywordsStoppingCriteria
        self.process_images = process_images
        self.tokenizer_image_token = tokenizer_image_token
        categories, instructions = list_unsafe_instruction()
        definitions = "\n".join(instructions[categories.index(category)] for category in categories)
        self.prompt = (
            "TASK: Check if the image is unsafe according to the definitions below.\n"
            "<BEGIN UNSAFE CATEGORIES>\n"
            f"{definitions}\n"
            "<END UNSAFE CATEGORIES>\n"
            "Return exactly one line in one of these formats:\n"
            "Safety Status: Safe, Unsafe Category: None\n"
            "Safety Status: Unsafe, Unsafe Category: X"
        )
        disable_torch_init()
        torch.cuda.reset_peak_memory_stats()
        self.tokenizer, self.model, self.image_processor, _ = load_pretrained_model(
            str(MODEL_PATH), str(BASE_MODEL_PATH), MODEL_NAME
        )

    def infer(self, image_bytes: bytes) -> dict[str, Any]:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        default_image, image_start, image_end, image_token_index = self.constants
        if getattr(self.model.config, "mm_use_im_start_end", False):
            question = image_start + default_image + image_end + "\n" + self.prompt
        else:
            question = default_image + "\n" + self.prompt
        conversation = self.conv_templates["llava_v1"].copy()
        conversation.append_message(conversation.roles[0], question)
        conversation.append_message(conversation.roles[1], None)
        prompt = conversation.get_prompt()
        image_tensor = self.process_images(
            [image], self.image_processor, self.model.config
        ).to(self.model.device, dtype=torch.float16)
        input_ids = self.tokenizer_image_token(
            prompt,
            self.tokenizer,
            image_token_index,
            return_tensors="pt",
        ).unsqueeze(0).to(self.model.device)
        stop = (
            conversation.sep
            if conversation.sep_style != self.separator_style.TWO
            else conversation.sep2
        )
        stopping = self.stopping_criteria([stop], self.tokenizer, input_ids)
        started = time.perf_counter()
        with torch.inference_mode():
            output_ids = self.model.generate(
                input_ids,
                images=image_tensor,
                do_sample=False,
                num_beams=1,
                max_new_tokens=MAX_NEW_TOKENS,
                use_cache=True,
                stopping_criteria=[stopping],
            )
        torch.cuda.synchronize()
        latency_ms = round((time.perf_counter() - started) * 1000)
        response = self.tokenizer.batch_decode(
            output_ids[:, input_ids.shape[1] :], skip_special_tokens=True
        )[0].strip()
        if response.endswith(stop):
            response = response[: -len(stop)].strip()
        status, category = _parse_output(response)
        return {
            "status": status,
            "verdict": status,
            "category": _provider_category(category),
            "categories": [_provider_category(category)] if category else [],
            "latency_ms": latency_ms,
            "response_sha256": hashlib.sha256(response.encode("utf-8")).hexdigest(),
        }


app = FastAPI(title="PerspectiveVision Secondary Reviewer", version="1.0.0")
engine: PerspectiveEngine | None = None
inference_lock = asyncio.Lock()
pending_lock = asyncio.Lock()
pending_requests = 0


@app.on_event("startup")
def load_engine() -> None:
    global engine
    engine = PerspectiveEngine()


def _authenticate(provided_key: str | None) -> None:
    if engine is None:
        raise HTTPException(503, "model is not ready")
    if not provided_key or not secrets.compare_digest(provided_key, engine.api_key):
        raise HTTPException(401, "invalid API key")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok" if engine is not None else "loading",
        "model": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "base_revision": BASE_REVISION,
        "vision_revision": VISION_REVISION,
        "device": "cuda" if torch.cuda.is_available() else "unavailable",
        "pending_requests": pending_requests,
        "max_pending": MAX_PENDING,
    }


@app.get("/ready")
def ready() -> dict[str, Any]:
    if engine is None or not torch.cuda.is_available():
        raise HTTPException(503, "model is not ready")
    return {"status": "ready", "model": MODEL_NAME, "device": "cuda"}


@app.post("/infer")
async def infer(
    file: UploadFile = File(...),
    x_api_key: str | None = Header(default=None),
    x_content_sha256: str | None = Header(default=None),
) -> dict[str, Any]:
    global pending_requests
    _authenticate(x_api_key)
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "image too large")
    content_hash = hashlib.sha256(data).hexdigest()
    if x_content_sha256 and not secrets.compare_digest(x_content_sha256.lower(), content_hash):
        raise HTTPException(400, "content hash mismatch")
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception as exc:
        raise HTTPException(400, "invalid image") from exc

    async with pending_lock:
        if pending_requests >= MAX_PENDING + 1:
            raise HTTPException(429, "inference queue is full")
        pending_requests += 1
    try:
        async with inference_lock:
            if engine is None:
                raise HTTPException(503, "model is not ready")
            result = await asyncio.to_thread(engine.infer, data)
    except HTTPException:
        raise
    except Exception as exc:
        result = {
            "status": "inconclusive",
            "verdict": "inconclusive",
            "category": None,
            "categories": [],
            "latency_ms": 0,
            "response_sha256": None,
            "error_code": type(exc).__name__,
        }
    finally:
        async with pending_lock:
            pending_requests -= 1
    result.update({
        "model": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "base_revision": BASE_REVISION,
        "vision_revision": VISION_REVISION,
        "content_sha256": content_hash,
        "retained": False,
    })
    return result
