# ADR-0003: Immutable Market Data Snapshot

- Status: Accepted
- Date: 2026-07-16

## Context
무료 원격 데이터와 라이브러리 동작은 시간이 지나며 바뀔 수 있다.

## Decision
원격 응답을 raw로 보존하고 정규화 결과를 순수 validator로 검사한 뒤 deterministic Parquet와 write-once
manifest를 만든다. 저장 영역은 raw, normalized, snapshots로 분리한다. snapshot은 취득 시점까지 포함한
content identity를 가지며 갱신은 새 id로 게시한다. 가격과 volume은 각각 `RAW`, `SPLIT_ADJUSTED`,
`TOTAL_RETURN_ADJUSTED` 중 하나를 기록하고 모호한 `ADJUSTED` 의미는 허용하지 않는다. storage URI는
배포 경로와 독립적인 logical key다. Prompt 08에서 manifest를 PostgreSQL에 idempotent하게 등록하고
BacktestRun 생성 transaction이 snapshot id와 checksum을 고정한다.

## Consequences
저장 공간이 늘지만 실행 재현성과 감사 가능성이 높아진다. 거래소 calendar가 없는 공급자는 누락 거래일을
추측하지 않고 경고하며, provider 간 교차 검사는 자동 병합하지 않는다.
