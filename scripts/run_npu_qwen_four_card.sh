#!/usr/bin/env bash
set -euo pipefail

RESULT_DIR=/mnt/model/codex-aigc-safety/results/qwen-four-card-concurrent-20260804
SCRIPT_PATH=/mnt/model/codex-aigc-safety/npu_qwen_inference_benchmark.py
MODEL_PATH=/mnt/model/Qwen3-0.6B
IMAGE=quay.io/ascend/vllm-ascend:v0.18.0-a3

mkdir -p "${RESULT_DIR}"

for card in 2 3 4 5; do
  docker rm -f "codex-qwen-npu${card}" >/dev/null 2>&1 || true
done

started_ns=$(date +%s%N)
for card in 2 3 4 5; do
  prompt_index=$((card - 2))
  docker run -d --name "codex-qwen-npu${card}" \
    --device "/dev/davinci${card}" \
    --device /dev/davinci_manager \
    --device /dev/devmm_svm \
    --device /dev/hisi_hdc \
    -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
    -v /usr/local/dcmi:/usr/local/dcmi:ro \
    -v "${MODEL_PATH}":/model:ro \
    -v /mnt/model/codex-aigc-safety:/work:ro \
    "${IMAGE}" \
    python /work/npu_qwen_inference_benchmark.py \
      --physical-card "${card}" \
      --prompt-index "${prompt_index}" \
      --repetitions 3 \
      --max-new-tokens 64 >/dev/null
done

for card in 2 3 4 5; do
  exit_code=$(docker wait "codex-qwen-npu${card}")
  if [[ "${exit_code}" != "0" ]]; then
    docker logs "codex-qwen-npu${card}" >&2 || true
    exit "${exit_code}"
  fi
done
ended_ns=$(date +%s%N)

for card in 2 3 4 5; do
  docker logs "codex-qwen-npu${card}" \
    >"${RESULT_DIR}/card${card}.json" \
    2>"${RESULT_DIR}/card${card}.stderr"
done

python3 - "${RESULT_DIR}" "${started_ns}" "${ended_ns}" <<'PY'
import hashlib
import json
import pathlib
import sys

result_dir = pathlib.Path(sys.argv[1])
started_ns = int(sys.argv[2])
ended_ns = int(sys.argv[3])
cards = []
artifacts = []
for card in (2, 3, 4, 5):
    path = result_dir / f"card{card}.json"
    raw = path.read_bytes()
    payload = json.loads(raw)
    cards.append(payload)
    artifacts.append(
        {
            "name": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
        }
    )

wall_seconds = (ended_ns - started_ns) / 1_000_000_000
total_tokens = sum(item["total_generated_tokens"] for item in cards)
manifest = {
    "schema_version": "1.0",
    "experiment": "Qwen3-0.6B four-card concurrent generation on Ascend NPU",
    "physical_cards": [2, 3, 4, 5],
    "model": "Qwen3-0.6B",
    "model_source": "/mnt/model/Qwen3-0.6B (pre-existing, read-only mount)",
    "container_image": "quay.io/ascend/vllm-ascend:v0.18.0-a3 (pre-existing)",
    "wall_seconds_including_container_start_load_warmup": round(wall_seconds, 6),
    "total_generated_tokens": total_tokens,
    "end_to_end_aggregate_tokens_per_second": round(total_tokens / wall_seconds, 3),
    "mean_steady_generation_tokens_per_second_per_card": round(
        sum(item["average_tokens_per_second"] for item in cards) / len(cards), 3
    ),
    "cards": cards,
    "artifacts": artifacts,
    "boundaries": [
        "The end-to-end metric includes container startup, model loading, warm-up, and generation.",
        "Per-card generation metrics exclude model loading and warm-up but include three deterministic generation runs.",
        "Qwen3-0.6B is a pretrained generation model, not the Qwen3Guard safety classifier.",
        "No existing workload was stopped or preempted; model weights and image were already present.",
    ],
}
(result_dir / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(manifest, ensure_ascii=False, indent=2))
PY

for card in 2 3 4 5; do
  docker rm "codex-qwen-npu${card}" >/dev/null
done
