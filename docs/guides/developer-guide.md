# Developer Guide

## 시작

```bash
uv sync
pnpm install
docker compose up --build
```

`uv run uvicorn apps.api.app:app --reload`로 API만, `pnpm dev`로 Web만 실행할 수 있다. Migration SQL은 `uv run alembic upgrade head --sql`로 확인하고 PostgreSQL 적용은 `uv run alembic upgrade head`로 수행한다.

## 검증

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

## 개발 순서
domain model → pure test → application service → adapter → API → Web → integration/E2E → docs.

## 새 Provider
인터페이스 구현, symbol mapper, normalizer, error mapping, raw fixture, contract test, metadata, DATA_PROVIDERS 갱신.

## 새 Indicator
수학적 정의, lookback, availability timing, 구현, 독립 fixture, DSL metadata, UI schema.

## 새 Broker
fake contract, 조회 기능, 오류 매핑, idempotency, reconciliation, redaction, paper 환경, production checklist.
