# SkynetClaw — backend image.
#
#   docker build -t skynetclaw .
#   docker run --rm -p 8766:8766 skynetclaw
#
# For the full stack (backend + a local model runtime) use: docker compose up

FROM python:3.12-slim

# curl is used by the container healthcheck and by the model-availability probe.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so a source change does not invalidate the pip layer.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r backend/requirements.txt

COPY . .

# settings.json is git-ignored, so an image built from a clean checkout has none.
# Seed it from the template; a bind-mounted file at runtime overrides this.
RUN test -f backend/settings.json || cp backend/settings.example.json backend/settings.json

# Inside a container, "localhost" is the container itself. Default the model
# runtime to the compose service; override with -e OLLAMA_BASE_URL to point
# anywhere else, including a host-run Ollama.
ENV OLLAMA_BASE_URL=http://ollama:11434 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

EXPOSE 8766

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -sf http://127.0.0.1:8766/api/system/health/quick || exit 1

WORKDIR /app/backend

# Initialise the database on first boot, then serve. Both are idempotent.
CMD ["sh", "-c", "python migrate.py up && python -m uvicorn main:app --host 0.0.0.0 --port 8766"]
