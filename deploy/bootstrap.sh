#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/root/CH/aigc-safety-system"
SERVICE_NAME="aigc-safety.service"

test -f "$APP_DIR/backend/.env"

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
uv run python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", cache_folder="weights/sentence_transformers")'

install -m 0644 "$APP_DIR/deploy/$SERVICE_NAME" "/etc/systemd/system/$SERVICE_NAME"
systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "Deployment complete: http://49.51.248.227:8010"
