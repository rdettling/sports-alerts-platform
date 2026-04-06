FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/services/api:/app/services/worker

COPY --from=ghcr.io/astral-sh/uv:0.6.16 /uv /uvx /bin/

WORKDIR /app/services/worker

COPY services/worker/pyproject.toml services/worker/uv.lock ./
RUN uv sync --frozen --no-dev

COPY services /app/services

CMD ["uv", "run", "python", "-m", "worker.main"]
