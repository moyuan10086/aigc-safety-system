"""Run an isolated four-card Ascend compute and MLP inference benchmark."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import time
from typing import Any

import torch
import torch_npu  # noqa: F401 - registers the NPU backend with PyTorch


def _synchronize() -> None:
    torch.npu.synchronize()


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def _worker(
    rank: int,
    world_size: int,
    matrix_size: int,
    matrix_iterations: int,
    mlp_batch_size: int,
    mlp_iterations: int,
    barrier: Any,
    output: Any,
) -> None:
    device = torch.device(f"npu:{rank}")
    torch.npu.set_device(device)
    torch.manual_seed(20260804 + rank)

    left = torch.randn((matrix_size, matrix_size), dtype=torch.float16, device=device)
    right = torch.randn((matrix_size, matrix_size), dtype=torch.float16, device=device)
    for _ in range(2):
        matrix_result = left @ right
    _synchronize()
    barrier.wait()
    matrix_started = time.perf_counter()
    for _ in range(matrix_iterations):
        matrix_result = left @ right
    _synchronize()
    matrix_seconds = time.perf_counter() - matrix_started
    matrix_tflops = (
        2 * matrix_size**3 * matrix_iterations / matrix_seconds / 1_000_000_000_000
    )

    model = torch.nn.Sequential(
        torch.nn.Linear(matrix_size, matrix_size, bias=False),
        torch.nn.GELU(),
        torch.nn.Linear(matrix_size, matrix_size, bias=False),
    ).to(device=device, dtype=torch.float16)
    inputs = torch.randn(
        (mlp_batch_size, matrix_size), dtype=torch.float16, device=device
    )
    with torch.inference_mode():
        for _ in range(3):
            inference_result = model(inputs)
        _synchronize()
        barrier.wait()
        inference_latencies = []
        for _ in range(mlp_iterations):
            started = time.perf_counter()
            inference_result = model(inputs)
            _synchronize()
            inference_latencies.append((time.perf_counter() - started) * 1000)

    output.put(
        {
            "rank": rank,
            "logical_device": str(device),
            "matrix": {
                "dtype": "float16",
                "shape": [matrix_size, matrix_size],
                "iterations": matrix_iterations,
                "elapsed_ms": round(matrix_seconds * 1000, 3),
                "tflops": round(matrix_tflops, 3),
                "checksum": round(matrix_result.float().mean().item(), 6),
            },
            "mlp_inference": {
                "architecture": f"Linear({matrix_size},{matrix_size})-GELU-Linear({matrix_size},{matrix_size})",
                "dtype": "float16",
                "batch_size": mlp_batch_size,
                "iterations": mlp_iterations,
                "mean_latency_ms": round(
                    sum(inference_latencies) / len(inference_latencies), 3
                ),
                "p95_latency_ms": round(_percentile(inference_latencies, 0.95), 3),
                "samples_per_second": round(
                    mlp_batch_size * 1000
                    / (sum(inference_latencies) / len(inference_latencies)),
                    2,
                ),
                "checksum": round(inference_result.float().mean().item(), 6),
            },
            "memory_allocated_mb": round(torch.npu.memory_allocated() / 1024 / 1024, 2),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world-size", type=int, default=4)
    parser.add_argument("--matrix-size", type=int, default=4096)
    parser.add_argument("--matrix-iterations", type=int, default=5)
    parser.add_argument("--mlp-batch-size", type=int, default=32)
    parser.add_argument("--mlp-iterations", type=int, default=20)
    args = parser.parse_args()

    available = torch.npu.device_count()
    if available != args.world_size:
        raise RuntimeError(
            f"Expected exactly {args.world_size} visible NPU devices, found {available}"
        )

    context = mp.get_context("spawn")
    barrier = context.Barrier(args.world_size)
    output = context.Queue()
    processes = [
        context.Process(
            target=_worker,
            args=(
                rank,
                args.world_size,
                args.matrix_size,
                args.matrix_iterations,
                args.mlp_batch_size,
                args.mlp_iterations,
                barrier,
                output,
            ),
        )
        for rank in range(args.world_size)
    ]
    started = time.perf_counter()
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    failed = [process.exitcode for process in processes if process.exitcode != 0]
    if failed:
        raise RuntimeError(f"NPU worker failures: {failed}")

    results = sorted((output.get() for _ in processes), key=lambda item: item["rank"])
    wall_seconds = time.perf_counter() - started
    payload = {
        "schema_version": "1.0",
        "status": "ok",
        "backend": "Ascend PyTorch NPU",
        "torch_version": torch.__version__,
        "torch_npu_version": torch_npu.__version__,
        "visible_devices": os.getenv("ASCEND_RT_VISIBLE_DEVICES", ""),
        "world_size": args.world_size,
        "wall_time_ms": round(wall_seconds * 1000, 3),
        "aggregate_matrix_tflops": round(
            sum(item["matrix"]["tflops"] for item in results), 3
        ),
        "aggregate_mlp_samples_per_second": round(
            sum(item["mlp_inference"]["samples_per_second"] for item in results),
            2,
        ),
        "devices": results,
    }
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
