#!/usr/bin/env bash
# Проверка live demo после деплоя (test.md: AI + health)
set -euo pipefail

BASE_URL="${1:-https://landing-contact.onrender.com}"

echo "=== Health: $BASE_URL/api/health ==="
curl -sf "$BASE_URL/api/health" | python3 -m json.tool | head -20

echo ""
echo "=== Contact (AI check): $BASE_URL/api/contact ==="
curl -sf -X POST "$BASE_URL/api/contact" \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo","email":"demo@example.com","phone":"+79991234567","comment":"Проверка AI-анализа после деплоя"}' \
  | python3 -c "import sys,json; a=json.load(sys.stdin).get('analysis',{}); print(json.dumps({k:a.get(k) for k in ('ai_used','provider','summary')}, ensure_ascii=False, indent=2))"

echo ""
echo "Ожидается: ai_used=true, provider=openai|anthropic, summary — краткое резюме"
