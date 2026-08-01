#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/root/CH/aigc-safety-system"
SERVICE_NAME="aigc-safety.service"

test -f "$APP_DIR/backend/.env"

cd "$APP_DIR/frontend"
npm install --package-lock=false --no-audit --no-fund
npm run build

cd "$APP_DIR/backend"
uv sync --frozen --no-dev
uv run python -c 'from huggingface_hub import hf_hub_download; hf_hub_download(repo_id="yermandy/deepfake-detection", filename="model.ckpt", local_dir="../deepfake-detection/weights")'
uv run python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", cache_folder="weights/sentence_transformers")'

install -m 0644 "$APP_DIR/deploy/$SERVICE_NAME" "/etc/systemd/system/$SERVICE_NAME"
systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "Deployment complete: http://49.51.248.227:8010"
