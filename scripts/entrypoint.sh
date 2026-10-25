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

        # Start supervised background worker (auto-restarts on unexpected worker exit)
        run_worker_supervisor() {
            while true; do
                CURRENT_WORKER_ID="sceneforge-worker-${HOSTNAME:-local}-$$-${RANDOM}"
                echo "[SceneForge] Starting RQ Background Worker ($CURRENT_WORKER_ID)..."
                rq worker --url "${REDIS_URL:-redis://redis:6379/0}" --name "$CURRENT_WORKER_ID" default || true
                echo "[SceneForge] Worker process exited. Resuming worker in 2s..."
                sleep 2
            done
        }

        run_worker_supervisor &
        WORKER_SUPERVISOR_PID=$!

        echo "[SceneForge] Starting API Server on port $PORT..."
        uvicorn sceneforge.api.app:app --host 0.0.0.0 --port "$PORT" &
        API_PID=$!

        cleanup() {
            echo "[SceneForge] Shutting down worker supervisor ($WORKER_SUPERVISOR_PID) and API ($API_PID)..."
            kill -TERM "$WORKER_SUPERVISOR_PID" "$API_PID" 2>/dev/null || true
            pkill -P "$WORKER_SUPERVISOR_PID" 2>/dev/null || true
            wait "$WORKER_SUPERVISOR_PID" "$API_PID" 2>/dev/null || true
        }
        trap cleanup SIGTERM SIGINT EXIT

        # Wait for API server to exit (primary public web service)
        wait "$API_PID"
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
