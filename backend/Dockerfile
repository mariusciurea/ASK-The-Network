FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .

RUN sed '/^pywin32==/d' requirements.txt > /tmp/requirements-linux.txt \
    && pip install --no-cache-dir -r /tmp/requirements-linux.txt

COPY . ./backend

EXPOSE 8082

CMD ["sh", "-c", "uvicorn backend.services:app --host 0.0.0.0 --port ${PORT:-8082}"]
