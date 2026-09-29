FROM node:22-bookworm-slim AS codex
ARG CODEX_VERSION=0.158.0
RUN npm install --global @openai/codex@${CODEX_VERSION} && codex --version

FROM python:3.12-slim-bookworm

COPY --from=codex /usr/local/bin/node /usr/local/bin/node
COPY --from=codex /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex \
    && apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && codex --version

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
