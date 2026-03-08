FROM python:3.11-slim

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
    "resend>=2.0.0" \
    "authlib>=1.3.0" \
    "httpx>=0.27.0" \
    "itsdangerous>=2.1.0" \
    "python-multipart>=0.0.9" \
    "sqlalchemy[asyncio]>=2.0.0" \
    "asyncpg>=0.29.0" \
    "alembic>=1.13.0"

WORKDIR /app

CMD ["python", "generate.py"]
