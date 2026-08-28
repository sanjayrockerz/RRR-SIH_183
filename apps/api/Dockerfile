FROM python:3.12-slim
WORKDIR /app
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api/app ./app
COPY infrastructure/postgres ./infrastructure/postgres
COPY data ./data
EXPOSE 8000
# Railway injects PORT; fall back to 8000 for local/Docker Compose
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
