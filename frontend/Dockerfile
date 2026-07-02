FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . ./frontend

EXPOSE 8501

CMD ["sh", "-c", "streamlit run frontend/main.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true --browser.gatherUsageStats=false"]
