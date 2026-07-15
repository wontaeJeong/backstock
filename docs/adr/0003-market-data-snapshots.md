# ADR-0003: Immutable Market Data Snapshot

- Status: Accepted
- Date: 2026-07-16

## Context
무료 원격 데이터와 라이브러리 동작은 시간이 지나며 바뀔 수 있다.

## Decision
원격 응답을 raw로 보존하고 검증·정규화한 Parquet snapshot과 manifest를 만든다. BacktestRun은 snapshot id와 checksum을 참조한다.

## Consequences
저장 공간이 늘지만 실행 재현성과 감사 가능성이 높아진다.
