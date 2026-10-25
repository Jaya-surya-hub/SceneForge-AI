#!/bin/bash
set -e

# Ensure storage directories exist
mkdir -p /app/storage/sceneforge-uploads /app/storage/sceneforge-artifacts /app/storage/sceneforge-cache 2>/dev/null || true

# Determine service mode (default: api)
SERVICE_MODE="${SERVICE_TYPE:-${1:-api}}"
PORT="${PORT:-8000}"

# Resolve REDIS_URL from individual parts if not provided
if [ -z "$REDIS_URL" ] && [ -n "$REDIS_HOST" ]; then
    REDIS_PORT="${REDIS_PORT:-6379}"
    REDIS_DB="${REDIS_DB:-0}"
    if [ -n "$REDIS_PASSWORD" ]; then
        REDIS_URL="redis://:${REDIS_PASSWORD}@${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}"
    else
        REDIS_URL="redis://${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}"
    fi
fi

case "$SERVICE_MODE" in
    worker)
        echo "[SceneForge] Starting RQ Background Worker..."
        exec rq worker --url "${REDIS_URL:-redis://redis:6379/0}" --name sceneforge-worker default
        ;;
    all)
        echo "[SceneForge] Running database migrations..."
        alembic upgrade head || true
        echo "[SceneForge] Starting RQ Background Worker in background..."
        rq worker --url "${REDIS_URL:-redis://redis:6379/0}" --name sceneforge-worker default &
        echo "[SceneForge] Starting API Server on port $PORT..."
        exec uvicorn sceneforge.api.app:app --host 0.0.0.0 --port "$PORT"
        ;;
    api|*)
        echo "[SceneForge] Running database migrations..."
        alembic upgrade head || true
        echo "[SceneForge] Starting API Server on port $PORT..."
        exec uvicorn sceneforge.api.app:app --host 0.0.0.0 --port "$PORT"
        ;;
esac
