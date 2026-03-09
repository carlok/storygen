# ══════════════════════════════════════════════════════════════════════════════
# Stage: backend-base
#   Production backend — used by the `web` (FastAPI) and `app` (CLI) services.
# ══════════════════════════════════════════════════════════════════════════════
FROM python:3.11-slim AS backend-base

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "moviepy==1.0.3" \
    "Pillow>=10.0.0" \
    "numpy>=1.24.0" \
    "fastapi>=0.110.0" \
    "uvicorn[standard]>=0.27.0" \
    "pilmoji>=2.0.2" \
    "authlib>=1.3.0" \
    "httpx>=0.27.0" \
    "itsdangerous>=2.1.0" \
    "python-multipart>=0.0.9" \
    "sqlalchemy[asyncio]>=2.0.0" \
    "asyncpg>=0.29.0" \
    "alembic>=1.13.0"

WORKDIR /app

# Default CMD is for the CLI runner service (generate.py).
# The `web` service overrides this via docker-compose `command:`.
CMD ["python", "generate.py"]


# ══════════════════════════════════════════════════════════════════════════════
# Stage: backend-test
#   Adds pytest + test dependencies on top of backend-base.
#   Used by the `backend-test` service (profiles: [test]).
# ══════════════════════════════════════════════════════════════════════════════
FROM backend-base AS backend-test

RUN pip install --no-cache-dir \
    "pytest>=8.0.0" \
    "pytest-asyncio>=0.23.0" \
    "pytest-cov>=5.0.0"
# httpx is already in backend-base (authlib dependency pulls it in)

# Tests run from the workspace root (mounted volume)
WORKDIR /workspace

CMD ["pytest", "tests/", \
     "--cov=/app", \
     "--cov=web", \
     "--cov-report=term-missing", \
     "--cov-report=html:coverage/backend", \
     "-v"]
