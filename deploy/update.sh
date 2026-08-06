#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/root/CH/aigc-safety-system"

cd "$APP_DIR"
git pull --ff-only
git submodule update --init --recursive
(cd "$APP_DIR/vendor/aigc-local-auditor" && sha256sum -c MODEL_SHA256)
if grep -Eq '^GUARDRAIL_ENABLE_XGBOOST_SHADOW=(1|true|yes|on)$' "$APP_DIR/backend/.env"; then
  test "$(awk -F= '$1 == "GUARDRAIL_XGBOOST_SHADOW_MODULE_PATH" {print substr($0, index($0, "=") + 1)}' "$APP_DIR/backend/.env")" = "../vendor/aigc-local-auditor" || {
    echo "Enabled XGBoost Shadow must use ../vendor/aigc-local-auditor" >&2
    exit 1
  }
  test "$(awk -F= '$1 == "GUARDRAIL_XGBOOST_SHADOW_MODEL_PATH" {print substr($0, index($0, "=") + 1)}' "$APP_DIR/backend/.env")" = "../vendor/aigc-local-auditor/security_audit_system/models/hybrid_safety_model_xgboost_color.json" || {
    echo "Enabled XGBoost Shadow must use the bundled model" >&2
    exit 1
  }
fi

cd "$APP_DIR/frontend"
npm install --package-lock=false --no-audit --no-fund
npm run build

cd "$APP_DIR/backend"
uv sync --frozen --no-dev --index https://download.pytorch.org/whl/cpu --index https://pypi.org/simple
uv run python -c 'from services import xgboost_shadow_service as service; result = service.evaluate("部署自检", "safe"); assert result["status"] in {"ok", "disabled"}, result.get("error_code")'
uv run python -c 'from services import deepfake_service as service; service.ensure_artifacts()'

systemctl restart aigc-safety.service
systemctl --no-pager --full status aigc-safety.service
