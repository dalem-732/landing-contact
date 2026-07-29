#!/bin/sh
# Worker: SERVICE_ROLE=worker или имя сервиса Railway содержит "worker"
# (например landing-worker → RAILWAY_SERVICE_NAME=landing-worker).

is_worker=false
case "${SERVICE_ROLE:-}" in
  worker) is_worker=true ;;
esac
case "${RAILWAY_SERVICE_NAME:-}" in
  *[Ww]orker*) is_worker=true ;;
esac

if [ "$is_worker" = true ]; then
  exec python -m app.workers.run_worker
fi

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
