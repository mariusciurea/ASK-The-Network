# FastAPI / ADK backend.
#
# Railway service settings:
#   Root Directory  = /backend
#   Dockerfile Path = /backend/Dockerfile
#
# With a Root Directory set, the build context is that directory itself: the
# context root holds requirements.txt, services.py, network_agent/ ... and
# nothing above it. So paths here are relative to backend/, and
# `COPY backend/...` would fail with "/backend: not found".
#
# docker compose uses the same context (see docker-compose.yaml).

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLBACKEND=Agg

WORKDIR /app

# Dependencies first: this layer stays cached until requirements.txt changes.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The package must land at /app/backend so `backend.services` is importable.
COPY . ./backend

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8082')+'/health')" || exit 1

# One worker by default: the agent is I/O bound, and the ADK session/artifact
# stores are local unless you point them at a shared database. Raise
# WEB_CONCURRENCY only after SESSION_SERVICE_URI points at MySQL.
CMD ["sh", "-c", "uvicorn backend.services:app --host 0.0.0.0 --port ${PORT:-8082} --workers ${WEB_CONCURRENCY:-1} --proxy-headers --forwarded-allow-ips='*'"]
