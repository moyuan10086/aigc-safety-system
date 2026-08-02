#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${SINGGUARD_ROOT:-/mnt/data/singguard}"
PYTHON_BIN="${SINGGUARD_PYTHON:-${ROOT_DIR}/env/bin/python}"
SERVICE_SCRIPT="${SINGGUARD_SERVICE_SCRIPT:-${ROOT_DIR}/singguard_service.py}"
MODEL_DIR="${SINGGUARD_MODEL_DIR:-${ROOT_DIR}/models/SingGuard-NSFA-0.8B}"
PORT="${SINGGUARD_PORT:-18210}"
PID_FILE="${ROOT_DIR}/singguard.pid"
LOG_FILE="${ROOT_DIR}/singguard.log"

test -x "${PYTHON_BIN}"
test -f "${SERVICE_SCRIPT}"
test -d "${MODEL_DIR}"
test -s "${ROOT_DIR}/api-key"

if [[ -s "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "SingGuard is already running with PID $(cat "${PID_FILE}")"
  exit 0
fi

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
nohup "${PYTHON_BIN}" "${SERVICE_SCRIPT}" \
  --model-dir "${MODEL_DIR}" \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --api-key-file "${ROOT_DIR}/api-key" \
  >"${LOG_FILE}" 2>&1 &

echo $! >"${PID_FILE}"
echo "Started SingGuard PID $(cat "${PID_FILE}") on port ${PORT}"
