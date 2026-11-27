FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini entrypoint.sh ./
COPY scripts/healthcheck.sh ./scripts/healthcheck.sh
COPY frontend ./frontend

RUN mkdir -p data logs \
    && chmod +x entrypoint.sh scripts/healthcheck.sh \
    && adduser --disabled-password --gecos "" --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD ["./scripts/healthcheck.sh"]

ENTRYPOINT ["./entrypoint.sh"]
