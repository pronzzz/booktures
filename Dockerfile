# syntax=docker/dockerfile:1

# --- 1. Build the web app ---------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# vite writes to ../booktures/web
RUN npm run build

# --- 2. Python app ------------------------------------------------------------
FROM python:3.12-slim
# Extras to install: "" (default, cloud and offline providers), "anthropic", or "local"
# for the bundled SD-Turbo model (adds about 2 GB of PyTorch, CPU only in Docker).
ARG EXTRAS=""
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BOOKTURES_HOME=/data \
    HF_HOME=/data/hf-cache

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY booktures/ booktures/
COPY --from=web /src/booktures/web booktures/web
RUN if [ "$EXTRAS" = "local" ]; then \
      pip install torch --index-url https://download.pytorch.org/whl/cpu; \
    fi \
 && pip install ".${EXTRAS:+[$EXTRAS]}"

RUN useradd --create-home --uid 1000 booktures && mkdir -p /data && chown booktures /data
USER booktures
VOLUME /data
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health')"

CMD ["booktures", "serve", "--host", "0.0.0.0", "--port", "8765", "--no-browser"]
