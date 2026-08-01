#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/root/CH/aigc-safety-system"
SERVICE_NAME="aigc-safety.service"

test -f "$APP_DIR/backend/.env"
test -f "$APP_DIR/deepfake-detection/weights/model.ckpt"
test -d "$APP_DIR/backend/weights/sentence_transformers"

cd "$APP_DIR/frontend"
npm ci
npm run build

cd "$APP_DIR/backend"
uv sync --frozen --no-dev

install -m 0644 "$APP_DIR/deploy/$SERVICE_NAME" "/etc/systemd/system/$SERVICE_NAME"
systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "Deployment complete: http://49.51.248.227:8010"
