# Current State

진단일: 2026-08-01

## 현재 구현

- Python 3.12 `uv` project와 Next.js `pnpm` workspace가 있다.
- FastAPI live/ready health, 공통 error contract, request id, JSON request log가 동작한다.
- Worker entrypoint, PostgreSQL 17 Compose service, 초기 Alembic migration이 있다.
- Web bootstrap과 디자인 시스템 primitive showcase가 있다.
- GitHub Actions가 backend lint/type/test/migration SQL과 frontend lint/type/test/build를 검증한다.
- YFinance/LocalFile/FinanceDataReader provider, immutable raw sidecar/checksum, effective-dated symbol mapping이 있다.
- normalized bar의 순수 품질 검사와 provider 교차 비교 report가 있다. 거래소 calendar가 없으면 추측하지 않고 경고한다.
- lossless deterministic normalized Parquet, checksum 검증, portable `snapshot://` URI와 write-once manifest가 있다.
- `/datasets` CSV/Parquet upload와 `/dataset-snapshots/{id}` 조회가 streaming byte limit, Parquet row/column
  bound, file type/signature/path 제한 및 `DATASET_INVALID` 계약으로 동작한다.
- immutable snapshot reference를 입력으로 받는 순수 이벤트 기반 일봉 backtest engine이 있다.
- MARKET/LIMIT와 DAY/GTC, next-open 체결, commission/세금/slippage, Decimal 원장, 다중 종목,
  benchmark, 종료 정책, cooperative cancellation/failure partial result를 지원한다.
- order/fill/portfolio/benchmark/event log와 snapshot checksum·engine version·seed를 포함한 재현성
  metadata를 immutable result로 반환한다.

## 재사용 가능 요소

- `PRD.md`의 기능·비기능 요구사항과 성공 기준
- `ARCHITECTURE.md`의 의존 방향과 adapter 경계
- 정확성, provider, DSL, broker, MCP, security 문서의 계약
- `docs/adr/`의 제품 범위, 이벤트 엔진, immutable snapshot, JSON DSL, 주문 안전 결정
- `docs/reference/`의 데이터 모델, 지표, API, 테스트 계획

## 누락 기능

- strategy DSL, backtest job/application service, risk, broker application service
- Web의 typed API client와 제품 화면
- snapshot/strategy/backtest/order 등 후속 리소스의 PostgreSQL schema와 repository
- strategy DSL, indicator, 고급 risk/execution, broker engine
- analytics, paper approval, KIS adapter, MCP server
- 전체 제품 흐름의 browser E2E와 운영 관측성

## 기술 부채

- stop/partial fill/volume participation/tick-lot/exchange calendar 실행 정책은 Prompt 07 범위다.
- object storage와 job queue 제품은 선택하지 않았고 snapshot storage는 filesystem adapter다.
- snapshot DB 등록과 BacktestRun의 snapshot id/checksum FK transaction은 Prompt 08 범위다.

## 정확성·보안 위험

- 일봉 엔진은 no-future, 비용, Decimal 원장을 검증하지만 split/dividend 실행과 point-in-time universe는
  아직 지원하지 않는다.
- 거래소 calendar가 구현된 provider가 없어 fixture 외 실제 누락 거래일 검사는 `VALID_WITH_WARNINGS`다.
- approval, idempotency, kill switch, secret redaction 경계가 문서에만 존재한다.
- identity model이 없어 authz/rate limit은 아직 application에 없으며 공개 배포 전 ingress 또는 Prompt 08
  security slice에서 강제해야 한다.
- 실제 credential은 없으며 `.env.example` 값은 비밀이 아닌 빈 placeholder다.

## 다음 단계 진입 조건

- Prompt 06 strategy DSL은 `StrategyEvaluator` port 뒤에 구현하고 engine이나 broker를 직접 호출하지 않는다.
- Prompt 07 risk/execution은 현재 pass-through 경계를 대체하되 no-future와 Decimal 원장 불변식을 유지한다.
- Prompt 08은 immutable result를 job/repository에 저장하고 snapshot id/checksum reference를 transaction으로
  고정한다.
