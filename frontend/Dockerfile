# Streamlit frontend.
#
# Railway service settings:
#   Root Directory  = /frontend
#   Dockerfile Path = /frontend/Dockerfile
#
# With a Root Directory set, the build context is that directory itself: the
# context root holds requirements.txt, main.py, ui/ ... and nothing above it.
# So paths here are relative to frontend/, and `COPY frontend/...` would fail
# with "/frontend: not found".
#
# docker compose uses the same context (see docker-compose.yaml).

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    # no browser, no telemetry, no inotify watchers in a container
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    STREAMLIT_LOGGER_LEVEL=info

WORKDIR /app

# Dependencies first: this layer stays cached until requirements.txt changes.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The package must land at /app/frontend so `frontend.main` is importable.
COPY . ./frontend

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

# Railway uses healthcheckPath from railway.json; this one covers local runs.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8501')+'/_stcore/health')" || exit 1

CMD ["sh", "-c", "streamlit run frontend/main.py --server.address=0.0.0.0 --server.port=${PORT:-8501}"]
