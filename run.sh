#!/bin/bash
set -e

cd "$(dirname "$0")"

export APP_SECRET_KEY="Ss1Ktt7G8c5zusQirc6Ah6dgbuIy3WN4c9DEOMnW5L0="
export AGENT_SHARED_TOKEN="ZE61QNWgB7rXqNHcg84u"
export SECRET_KEY="sZJ6naKmXYuLAXZ01s8V79TcEa6fGnR5"
export WATCHER_SERVICE_URL_CN="http://114.66.58.8:5010"
export WATCHER_SHARED_TOKEN="@ColorSail-2020"

echo "[System] Starting CS2ZE Browser Backend..."

# 你的环境变量...（保持不变）

# 优先用项目目录下的 .venv
.venv/bin/gunicorn -w 1 --threads 4 --worker-class gthread --keep-alive 5 --timeout 60 --graceful-timeout 30 -b 0.0.0.0:5000 wsgi_main:application