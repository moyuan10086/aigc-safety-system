#!/usr/bin/env python3
"""Run a small, reproducible Qwen generation benchmark on one mapped Ascend NPU.

The container must expose exactly one physical NPU. The script treats it as
``npu:0`` and records the physical card label supplied by the caller.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone

import torch
import torch_npu  # noqa: F401
from transformers import AutoModelForCausalLM, AutoTokenizer


PROMPTS = (
    "请用两句话说明大模型安全护栏在输入和输出阶段分别起什么作用。",
    "请列出 AIGC 图片审核中需要重点关注的两类安全风险，并简述原因。",
    "为什么安全审核系统需要保留加密审计证据？请用简洁中文回答。",
    "请用一句话说明在国产昇腾 NPU 上部署 AI 安全模型的工程价值。",
)


def _sync() -> None:
    torch.npu.synchronize()


def _chat_input(tokenizer, prompt: str) -> str:
    messages = [{"role": "user", "content": prompt}]
    try:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    except TypeError:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/model")
    parser.add_argument("--physical-card", type=int, required=True)
    parser.add_argument("--prompt-index", type=int, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    args = parser.parse_args()

    if not torch.npu.is_available() or torch.npu.device_count() != 1:
        raise RuntimeError("expected exactly one mapped Ascend NPU")

    prompt = PROMPTS[args.prompt_index % len(PROMPTS)]
    torch.manual_seed(20260804 + args.physical_card)
    device = torch.device("npu:0")
    torch.npu.set_device(device)

    load_started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        local_files_only=True,
        trust_remote_code=False,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        local_files_only=True,
        trust_remote_code=False,
        dtype=torch.bfloat16,
        attn_implementation="eager",
    ).to(device)
    model.eval()
    _sync()
    load_seconds = time.perf_counter() - load_started

    rendered = _chat_input(tokenizer, prompt)
    encoded = tokenizer(rendered, return_tensors="pt")
    input_ids = encoded.input_ids.to(device)
    attention_mask = encoded.attention_mask.to(device)
    input_tokens = int(input_ids.shape[-1])

    # Warm up graph compilation and allocator paths. Warm-up output is discarded.
    with torch.inference_mode():
        model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=8,
            do_sample=False,
            use_cache=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    _sync()

    runs = []
    response = ""
    total_generated_tokens = 0
    total_seconds = 0.0
    for run_index in range(args.repetitions):
        _sync()
        started = time.perf_counter()
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                use_cache=True,
                pad_token_id=tokenizer.eos_token_id,
            )
        _sync()
        elapsed = time.perf_counter() - started
        new_ids = output_ids[0, input_tokens:]
        generated_tokens = int(new_ids.shape[-1])
        decoded = tokenizer.decode(new_ids, skip_special_tokens=True).strip()
        if run_index == 0:
            response = decoded
        total_generated_tokens += generated_tokens
        total_seconds += elapsed
        runs.append(
            {
                "run": run_index + 1,
                "seconds": round(elapsed, 6),
                "generated_tokens": generated_tokens,
                "tokens_per_second": round(generated_tokens / elapsed, 3),
                "response_sha256": hashlib.sha256(decoded.encode("utf-8")).hexdigest(),
            }
        )

    result = {
        "schema_version": "1.0",
        "measured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "physical_card": args.physical_card,
        "visible_device": "npu:0",
        "device_name": torch.npu.get_device_name(0),
        "model": "Qwen3-0.6B",
        "model_path": args.model,
        "dtype": "bfloat16",
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torch_npu": torch_npu.__version__,
        "transformers": __import__("transformers").__version__,
        "load_seconds": round(load_seconds, 6),
        "prompt": prompt,
        "input_tokens": input_tokens,
        "response": response,
        "repetitions": args.repetitions,
        "max_new_tokens": args.max_new_tokens,
        "total_generated_tokens": total_generated_tokens,
        "total_generation_seconds": round(total_seconds, 6),
        "average_tokens_per_second": round(total_generated_tokens / total_seconds, 3),
        "runs": runs,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
