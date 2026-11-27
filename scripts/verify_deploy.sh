#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-}"
if [[ -z "$BASE_URL" ]]; then
  echo "Usage: $0 https://your-backend.example.com" >&2
  exit 1
fi

echo "=== Public health: $BASE_URL/api/health ==="
curl -sf "$BASE_URL/api/health" | python3 -m json.tool

if [[ -n "${METRICS_TOKEN:-}" ]]; then
  echo ""
  echo "=== Health details ==="
  curl -sf -H "Authorization: Bearer ${METRICS_TOKEN}" "$BASE_URL/api/health/details" | python3 -m json.tool | head -40
fi
