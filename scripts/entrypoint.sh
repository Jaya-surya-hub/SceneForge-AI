#!/bin/bash
set -e

# Ensure storage directories exist
STORAGE_BASE="/app/storage"
if [ ! -d "$STORAGE_BASE" ]; then
    STORAGE_BASE="/tmp/sceneforge_storage"
fi
mkdir -p "$STORAGE_BASE/sceneforge-uploads" "$STORAGE_BASE/sceneforge-artifacts" "$STORAGE_BASE/sceneforge-cache" 2>/dev/null || true

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

# Generate unique worker name per instance to prevent Redis worker collisions
WORKER_ID="sceneforge-worker-${HOSTNAME:-local}-$$-${RANDOM}"

case "$SERVICE_MODE" in
    worker)
        echo "[SceneForge] Starting RQ Background Worker ($WORKER_ID)..."
        exec rq worker --url "${REDIS_URL:-redis://redis:6379/0}" --name "$WORKER_ID" default
        ;;
    all)
        echo "[SceneForge] Running database migrations..."
        alembic upgrade head || true

        echo "[SceneForge] Starting RQ Background Worker in background ($WORKER_ID)..."
        rq worker --url "${REDIS_URL:-redis://redis:6379/0}" --name "$WORKER_ID" default &
        WORKER_PID=$!

        echo "[SceneForge] Starting API Server on port $PORT..."
        uvicorn sceneforge.api.app:app --host 0.0.0.0 --port "$PORT" &
        API_PID=$!

        cleanup() {
            echo "[SceneForge] Shutting down worker ($WORKER_PID) and API ($API_PID)..."
            kill -TERM "$WORKER_PID" "$API_PID" 2>/dev/null || true
            wait "$WORKER_PID" "$API_PID" 2>/dev/null || true
        }
        trap cleanup SIGTERM SIGINT EXIT

        # Wait for either process to exit, then exit container
        wait -n "$WORKER_PID" "$API_PID"
        EXIT_STATUS=$?
        cleanup
        exit "$EXIT_STATUS"
        ;;
    api|*)
        echo "[SceneForge] Running database migrations..."
        alembic upgrade head || true
        echo "[SceneForge] Starting API Server on port $PORT..."
        exec uvicorn sceneforge.api.app:app --host 0.0.0.0 --port "$PORT"
        ;;
esac
