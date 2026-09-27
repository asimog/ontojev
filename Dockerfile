FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CANCERJEV_DATA_DIR=/data

WORKDIR /app

COPY pyproject.toml README.md ./
COPY cancerjev ./cancerjev
COPY apps ./apps
COPY deploy ./deploy
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

RUN mkdir -p /data
EXPOSE 8080

# Public API over the persistent data directory. With CANCERJEV_RUN_WORKER=1
# (set in production) the same process also starts the canonical durable worker.
CMD ["python", "-m", "deploy.serve"]
