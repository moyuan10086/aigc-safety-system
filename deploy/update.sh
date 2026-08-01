#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/root/CH/aigc-safety-system"

cd "$APP_DIR"
git pull --ff-only
git submodule update --init --recursive

cd "$APP_DIR/frontend"
npm ci
npm run build

cd "$APP_DIR/backend"
uv sync --frozen --no-dev

systemctl restart aigc-safety.service
systemctl --no-pager --full status aigc-safety.service
