FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .

RUN sed '/^pywin32==/d' requirements.txt > /tmp/requirements-linux.txt \
    && (grep -qi '^streamlit' /tmp/requirements-linux.txt || echo 'streamlit' >> /tmp/requirements-linux.txt) \
    && pip install --no-cache-dir -r /tmp/requirements-linux.txt

COPY frontend ./frontend

EXPOSE 8501

CMD ["sh", "-c", "streamlit run frontend/main.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true --browser.gatherUsageStats=false"]
