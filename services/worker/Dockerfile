FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/services/api:/app/services/worker
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.6.16 /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/services/worker

COPY services/worker/pyproject.toml services/worker/uv.lock ./
RUN uv sync --frozen --no-dev

COPY services /app/services

CMD ["uv", "run", "python", "-m", "worker.main"]
