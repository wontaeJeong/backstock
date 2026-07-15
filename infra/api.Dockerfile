FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev
COPY apps ./apps
COPY packages ./packages
COPY alembic.ini ./
COPY migrations ./migrations

CMD ["sh", "-c", "uv run --no-dev alembic upgrade head && exec uv run --no-dev uvicorn apps.api.app:app --host 0.0.0.0 --port 8000"]
