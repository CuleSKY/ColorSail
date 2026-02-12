#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ -f ".env" ]; then
  set -a
  . ./.env
  set +a
fi

: "${APP_SECRET_KEY:?APP_SECRET_KEY is required}"
: "${AGENT_MASTER_URL:?AGENT_MASTER_URL is required}"
: "${AGENT_SHARED_TOKEN:?AGENT_SHARED_TOKEN is required}"

echo "[System] Starting backend..."

.venv/bin/gunicorn \
  -w 1 \
  --threads 4 \
  --worker-class gthread \
  --keep-alive 5 \
  --timeout 60 \
  --graceful-timeout 30 \
  -b 0.0.0.0:5000 \
  wsgi_main:application
