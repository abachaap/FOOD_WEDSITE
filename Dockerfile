FROM python:3.12-slim

ENV HOST=0.0.0.0 \
    PORT=8000 \
    BEP_NHA_DATA_DIR=/data \
    COOKIE_SECURE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app
RUN mkdir -p /data
EXPOSE 8000
CMD ["python", "server.py"]
