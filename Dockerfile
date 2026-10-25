# SceneForge AI — multi-stage Dockerfile
#
# Stage 1 (builder): install Python dependencies into a venv
# Stage 2 (runtime): copy venv + source; install FFmpeg static binary; run as non-root user
#
# Network note: apt HTTP repos may be blocked on some networks.
# This Dockerfile downloads a pre-built static FFmpeg binary from GitHub
# (BtbN/FFmpeg-Builds, GPL build) using HTTPS, which is accessible.
#
# FFmpeg licence: GPL-2.0+ (includes libx264).
# Acceptable for assessment submission; review before commercial deployment.

# ─── Stage 1: builder ────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies (try apt; skip if blocked)
RUN apt-get update 2>/dev/null || true
RUN apt-get install -y --no-install-recommends gcc libpq-dev 2>/dev/null || true

# Create a virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ─── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

# Copy the FFmpeg install script and run it inside the build
COPY scripts/install_ffmpeg.py /tmp/install_ffmpeg.py
RUN python3 /tmp/install_ffmpeg.py && rm /tmp/install_ffmpeg.py

# Download Roboto Regular font (Apache 2.0) for FFmpeg drawtext card generation
COPY scripts/install_font.py /tmp/install_font.py
RUN python3 /tmp/install_font.py && rm /tmp/install_font.py

# Install libpq for PostgreSQL (try apt; skip if blocked — psycopg2-binary
# bundles its own libpq)
RUN apt-get update 2>/dev/null || true
RUN apt-get install -y --no-install-recommends libpq5 curl 2>/dev/null || \
    echo "libpq5/curl install skipped (apt blocked); psycopg2-binary includes libpq"

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user and set up directories
RUN useradd --create-home --shell /bin/bash sceneforge && \
    mkdir -p /app/storage && \
    chown -R sceneforge:sceneforge /app/storage
WORKDIR /app

# Copy application source & frontend assets
COPY --chown=sceneforge:sceneforge src/ ./src/
COPY --chown=sceneforge:sceneforge alembic/ ./alembic/
COPY --chown=sceneforge:sceneforge alembic.ini ./
COPY --chown=sceneforge:sceneforge apps/ ./apps/
COPY --chown=sceneforge:sceneforge scripts/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Set Python path so `sceneforge` package is importable
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1

# Verify FFmpeg is available at container start
RUN ffmpeg -version 2>&1 | head -1 && ffprobe -version 2>&1 | head -1

# Switch to non-root user
USER sceneforge

# Default: run the API server (overrideable via CMD or SERVICE_TYPE)
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["api"]
