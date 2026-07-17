#!/usr/bin/env bash
set -euo pipefail

REDIRECTS="frontend/_redirects"

{
  echo "/static/*  /:splat  200"
  if [[ -n "${API_URL:-}" ]]; then
    base="${API_URL%/}"
    echo "/api/*  ${base}/api/:splat  200!"
  fi
} > "$REDIRECTS"

echo "Generated ${REDIRECTS}:"
cat "$REDIRECTS"
