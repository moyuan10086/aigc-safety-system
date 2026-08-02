#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${QWEN_GUARD_ROOT:-/mnt/data/qwen-guard}"
VLLM_BIN="${VLLM_BIN:-/mnt/data/qwen-image/envs/vllm-omni-q4/bin/vllm}"
MODEL_DIR="${QWEN_GUARD_MODEL_DIR:-${ROOT_DIR}/models/Qwen3Guard-Gen-0.6B}"
PORT="${QWEN_GUARD_PORT:-18200}"
GPU_UTIL="${QWEN_GUARD_GPU_UTIL:-0.34}"
PID_FILE="${ROOT_DIR}/qwen3guard.pid"
LOG_FILE="${ROOT_DIR}/qwen3guard.log"

mkdir -p "${ROOT_DIR}"
test -x "${VLLM_BIN}"
test -d "${MODEL_DIR}"
test -s "${ROOT_DIR}/api-key"

if [[ -s "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "Qwen3Guard is already running with PID $(cat "${PID_FILE}")"
  exit 0
fi

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export VLLM_API_KEY="$(cat "${ROOT_DIR}/api-key")"
nohup "${VLLM_BIN}" serve "${MODEL_DIR}" \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --served-model-name qwen3guard-gen-0.6b \
  --max-model-len 8192 \
  --gpu-memory-utilization "${GPU_UTIL}" \
  --dtype auto \
  >"${LOG_FILE}" 2>&1 &

echo $! >"${PID_FILE}"
echo "Started Qwen3Guard PID $(cat "${PID_FILE}") on port ${PORT}"
