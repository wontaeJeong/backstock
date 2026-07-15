# Developer Guide

## 시작 목표

```bash
uv sync
pnpm install
docker compose up --build
```

구현 후 실제 명령으로 갱신한다.

## 개발 순서
domain model → pure test → application service → adapter → API → Web → integration/E2E → docs.

## 새 Provider
인터페이스 구현, symbol mapper, normalizer, error mapping, raw fixture, contract test, metadata, DATA_PROVIDERS 갱신.

## 새 Indicator
수학적 정의, lookback, availability timing, 구현, 독립 fixture, DSL metadata, UI schema.

## 새 Broker
fake contract, 조회 기능, 오류 매핑, idempotency, reconciliation, redaction, paper 환경, production checklist.
