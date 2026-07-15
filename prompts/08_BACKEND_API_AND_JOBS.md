# 8단계 — Backend API와 Job

`00_GLOBAL_RULES.md`와 이전 구현을 적용한다.

## 리소스

instruments, datasets, dataset-snapshots, strategies, strategy-versions, backtest-runs, results, orders, fills, paper-accounts, broker-connections

## 요구사항

- OpenAPI
- typed request/response
- pagination/filter/sort
- request id
- idempotency
- optimistic version check
- job status와 cancellation
- audit와 sensitive redaction

BacktestRun 상태: `PENDING`, `VALIDATING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLING`, `CANCELLED`.

## 작업

1. application service를 도메인과 HTTP 사이에 둔다.
2. DB schema와 migration을 만든다.
3. dataset/strategy/backtest API를 구현한다.
4. 실행 생성 시 strategy version과 snapshot을 고정한다.
5. DB 기반 job queue와 worker를 구현한다.
6. 중복 실행 방지와 진행률을 구현한다.
7. polling과 가능하면 SSE를 제공한다.
8. 대용량 이벤트와 거래 목록은 pagination한다.
9. worker 재시작 후 상태를 보존한다.
10. API integration test를 작성한다.

## 완료 조건

- API만으로 전체 흐름을 수행한다.
- 결과 재현성 metadata를 조회한다.
