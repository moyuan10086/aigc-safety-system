"""Minimal Ascend NPU compute validation for an isolated test container."""

import json
import time

import torch
import torch_npu  # noqa: F401 - registers the NPU backend with PyTorch


def main() -> None:
    device = torch.device("npu:0")
    torch.npu.set_device(device)

    left = torch.randn((2048, 2048), device=device)
    right = torch.randn((2048, 2048), device=device)
    torch.npu.synchronize()

    started = time.perf_counter()
    result = left @ right
    torch.npu.synchronize()
    elapsed_ms = (time.perf_counter() - started) * 1000

    print(
        json.dumps(
            {
                "status": "ok",
                "backend": "Ascend PyTorch NPU",
                "torch_version": torch.__version__,
                "torch_npu_version": torch_npu.__version__,
                "logical_device": str(device),
                "operation": "matmul_fp32_2048x2048",
                "elapsed_ms": round(elapsed_ms, 2),
                "checksum": round(result.float().sum().item(), 4),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
