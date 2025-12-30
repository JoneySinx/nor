# ==========================================
# ⚡ PRODUCTION-READY DOCKERFILE (STABLE)
# Python 3.10 | Debian Bookworm | Multi-stage
# ==========================================

# ==========================================
# Stage 1: Builder
# ==========================================
FROM python:3.10-slim-bookworm as builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libc-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade \
    pip \
    setuptools \
    wheel

COPY requirements.txt /tmp/

RUN pip install --no-cache-dir --user \
    -r /tmp/requirements.txt

RUN python -m compileall /root/.local 2>/dev/null || true


# ==========================================
# Stage 2: Runtime
# ==========================================
FROM python:3.10-slim-bookworm

LABEL org.opencontainers.image.title="Auto Filter Bot"
LABEL org.opencontainers.image.description="Telegram Auto Filter Bot"
LABEL org.opencontainers.image.version="4.0-stable"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONOPTIMIZE=2 \
    MALLOC_TRIM_THRESHOLD_=100000

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r -g 1000 botuser && \
    useradd -r -u 1000 -g botuser -m -s /sbin/nologin botuser && \
    mkdir -p /app && \
    chown -R botuser:botuser /app

WORKDIR /app

COPY --from=builder --chown=botuser:botuser /root/.local /home/botuser/.local
COPY --chown=botuser:botuser . .

ENV PATH=/home/botuser/.local/bin:$PATH

USER botuser

# Optional import warm-up
RUN python -c "import hydrogram, pymongo, aiohttp" || true

HEALTHCHECK --interval=60s --timeout=10s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

EXPOSE 8000

STOPSIGNAL SIGTERM

CMD ["python", "-O", "-u", "bot.py"]
