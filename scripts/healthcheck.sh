#!/bin/sh
is_worker=false
case "${SERVICE_ROLE:-}" in
  worker) is_worker=true ;;
esac
case "${RAILWAY_SERVICE_NAME:-}" in
  *[Ww]orker*) is_worker=true ;;
esac

if [ "$is_worker" = true ]; then
  exit 0
fi
python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/api/health')" || exit 1
