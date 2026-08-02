"""Minimal authenticated OpenAI-compatible service for SingGuard-NSFA."""

from __future__ import annotations

import argparse
import asyncio
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import torch
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=12_000)


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(min_length=1, max_length=8)
    max_tokens: int = Field(default=512, ge=16, le=1024)
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18210)
    parser.add_argument("--api-key-file", required=True)
    return parser.parse_args()


ARGS = parse_args()
MODEL_NAME = "singguard-nsfa-0.8b"
API_KEY = Path(ARGS.api_key_file).read_text(encoding="utf-8").strip()
INFERENCE_LOCK = asyncio.Lock()
TOKENIZER: Any = None
MODEL: Any = None


def _load_model() -> None:
    global TOKENIZER, MODEL
    TOKENIZER = AutoTokenizer.from_pretrained(ARGS.model_dir, trust_remote_code=True)
    MODEL = AutoModelForCausalLM.from_pretrained(
        ARGS.model_dir,
        dtype=torch.bfloat16,
        device_map={"": 0},
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    ).eval()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(_load_model)
    yield


app = FastAPI(title="SingGuard NSFA Service", lifespan=lifespan)


def authorize(value: str | None) -> None:
    prefix = "Bearer "
    supplied = value[len(prefix) :] if value and value.startswith(prefix) else ""
    if not supplied or not secrets.compare_digest(supplied, API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME, "loaded": MODEL is not None}


@app.get("/v1/models")
async def models(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "inclusionAI"}]}


def _generate(body: ChatRequest) -> dict[str, Any]:
    messages = [message.model_dump() for message in body.messages]
    encoded = TOKENIZER.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    )
    encoded = {key: value.to(MODEL.device) for key, value in encoded.items()}
    input_tokens = int(encoded["input_ids"].shape[-1])
    started = time.perf_counter()
    with torch.inference_mode():
        output = MODEL.generate(
            **encoded,
            max_new_tokens=body.max_tokens,
            do_sample=body.temperature > 0,
            temperature=max(body.temperature, 1e-5) if body.temperature > 0 else None,
            pad_token_id=TOKENIZER.eos_token_id,
        )
    generated = output[0, input_tokens:]
    content = TOKENIZER.decode(generated, skip_special_tokens=True).strip()
    completion_tokens = int(generated.shape[-1])
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_NAME,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": input_tokens + completion_tokens,
        },
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }


@app.post("/v1/chat/completions")
async def chat(body: ChatRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    if body.model != MODEL_NAME:
        raise HTTPException(status_code=404, detail="Model not found")
    async with INFERENCE_LOCK:
        return await asyncio.to_thread(_generate, body)


if __name__ == "__main__":
    uvicorn.run(app, host=ARGS.host, port=ARGS.port, log_level="info")
