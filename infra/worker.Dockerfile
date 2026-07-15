FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev
COPY apps ./apps
COPY packages ./packages

CMD ["uv", "run", "--no-dev", "python", "-m", "apps.worker.main"]
