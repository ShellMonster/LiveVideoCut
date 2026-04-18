# ===== Stage 1: Builder — install dependencies =====
ARG DOCKER_REGISTRY=
ARG APT_MIRROR=
ARG PYPI_INDEX_URL=
FROM ${DOCKER_REGISTRY:-}python:3.11-slim AS builder
ARG APT_MIRROR=
ARG PYPI_INDEX_URL=

RUN if [ -n "$APT_MIRROR" ]; then \
        sed -i "s@deb.debian.org@$APT_MIRROR@g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN set -eux; \
    if [ -n "$PYPI_INDEX_URL" ]; then \
        HOST=$(python -c "from urllib.parse import urlparse; import os; print(urlparse(os.environ['PYPI_INDEX_URL']).hostname or '')"); \
        python -m pip install --no-cache-dir --disable-pip-version-check --upgrade pip setuptools wheel -i "$PYPI_INDEX_URL" --trusted-host "$HOST"; \
        pip install --no-cache-dir --disable-pip-version-check --prefix=/install -r requirements.txt -i "$PYPI_INDEX_URL" --trusted-host "$HOST"; \
    else \
        python -m pip install --no-cache-dir --disable-pip-version-check --upgrade pip setuptools wheel; \
        pip install --no-cache-dir --disable-pip-version-check --prefix=/install -r requirements.txt; \
    fi

# ===== Stage 2: Runtime — minimal image =====
ARG DOCKER_REGISTRY=
ARG APT_MIRROR=
FROM ${DOCKER_REGISTRY:-}python:3.11-slim

# Only ffmpeg runtime needed (no build tools)
RUN if [ -n "$APT_MIRROR" ]; then \
        sed -i "s@deb.debian.org@$APT_MIRROR@g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ ./app/
COPY assets/ ./assets/

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
