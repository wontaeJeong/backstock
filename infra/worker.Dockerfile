FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps ./apps
COPY packages ./packages
RUN uv sync --frozen --no-dev && useradd --create-home --uid 10001 app && mkdir -p /app/var/data && chown -R app:app /app/var
USER app

CMD ["/app/.venv/bin/python", "-m", "apps.worker.main"]
