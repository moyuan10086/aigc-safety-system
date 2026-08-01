#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/root/CH/aigc-safety-system"

cd "$APP_DIR"
git pull --ff-only
git submodule update --init --recursive

cd "$APP_DIR/frontend"
npm install --package-lock=false --no-audit --no-fund
npm run build

cd "$APP_DIR/backend"
uv sync --frozen --no-dev --index https://download.pytorch.org/whl/cpu --index https://pypi.org/simple

systemctl restart aigc-safety.service
systemctl --no-pager --full status aigc-safety.service
