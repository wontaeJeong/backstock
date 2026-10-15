# Architecture

## 현재 상태

Python 3.12 `uv` project, FastAPI adapter, worker entrypoint, Next.js web, Alembic migration,
PostgreSQL과 Docker Compose 실행 기반이 구축되어 있다. market data provider, 순수 품질 검사,
immutable Parquet snapshot, bounded `/datasets` API, 순수 이벤트 기반 일봉 backtest engine이 구현되어 있다.
`packages/strategy`가 JSON AST 조건주문 DSL, indicator, `StrategyEvaluator` 구현체, canonical
hash version, `/strategies/validate`·`/strategies/metadata` API, 4개 템플릿을 제공한다.

한국어 웹 편집기 → 같은 출처의 Next.js proxy → `/simulations` → `SimulationService` →
검증된 snapshot reader → 순수 DSL/engine → immutable run JSON 흐름이 연결되어 있다.
원금 대비 순손익·수익률·최대 낙폭을 반환하며, 웹은 금융 지표를 재계산하지 않는다.
동기 실행은 3,000 bar·계산 15초 cooperative 제한이며 DB job queue나 worker 실행을 가장하지 않는다.
실행 config/전략/결과·소스 content hash를 filesystem artifact로 보존하고 checksum 검증으로 조회한다.
Compose는 migration 완료 후 API를 시작하며 snapshot/run volume을 보존한다. readiness는 실제 필요한
filesystem 쓰기를 검사하고 DB 작업 처리 상태를 주장하지 않는다.

분봉 업로드는 `1m`/`5m`, 명시적 UTC offset, bar **종료** timestamp 계약이다. 다음 bar open은
`timestamp - duration`이며 이전 신호 확정 시각과 같을 수 있다(지연 0 근사). 거래소 세션은 뉴욕 시간,
DAY 주문은 다음 세션 전에 만료한다. calendar·조기폐장·호가·부분 체결은 지원하지 않는다.
원격 Yahoo는 일봉과 제한된 최근 1m/5m finalized bar를 수집한다. 로컬 raw tick/quote 파일은
event timestamp와 별도 bid/ask를 보존하며 같은 엔진의 다음 eligible event 정책을 사용한다.
spread/latency/optional all-or-none volume cap은 시나리오이고 실제 queue·부분 체결은 아니다.
합성 데모는 `synthetic_demo` lineage로 실제 시세와 분리한다.

## 개요

연구 워크벤치의 보관함·분석·비교·실험·수동 paper 패널도 같은 Next.js same-origin allowlist proxy를
거친다. 금융 계산은 서버에만 있으며 UI는 통계/이유·원본 근거·차트 좌표만 표시한다. 검증된 bar 미리보기는
manifest row_count≤3000 확인 후 checksum-bound reader를 사용하고 파일 경로를 반환하지 않는다.
portfolio analysis는 immutable 실험의 별도 파생 조회이고, 원본 artifact를 수정하지 않는다.
paper POST의 성공/실패·과거 idempotency 응답과 무관하게 UI는 현재 GET 계좌를 다시 읽는다.
application factory는 동시 요청 전에 공개 `app.openapi()`로 route/dependency schema와 API 계약을 구성한다.
FastAPI/Pydantic lazy schema 생성이 병렬 첫 요청에서 전역 warning filter를 경쟁하지 않게 한다.

```text
Browser -> Web -> API -> Application Services
                         -> Market Data
                         -> Strategy
                         -> Backtest Engine
                         -> Risk Engine
                         -> Broker Interface
                    -> PostgreSQL / Snapshot Storage
Worker <-------------+
MCP -> Application Services
External Providers/Brokers -> Adapters
```

## 구현 구조

```text
apps/api
apps/web
apps/worker
apps/mcp
packages/domain
packages/application
packages/market_data
packages/strategy
packages/backtest
packages/risk
packages/broker
packages/shared
infra
docs
```

Python import 방향은 `apps -> packages/application -> packages/domain`이다. `packages/shared`는 설정·로그처럼 계산 규칙이 아닌 공통 운영 계약만 제공한다. `apps/api`의 SQLAlchemy 모델은 persistence adapter이며 domain 모델이 아니다.

## 경계

- Domain: 프레임워크 독립 모델과 규칙
- Market Data: 수집, 정규화, 검증, snapshot
- Strategy: DSL 평가와 OrderIntent
- Backtest: clock, 주문, 체결, 원장
- Risk: 승인·수정·거절
- Broker: mock, paper, KIS adapter
- Application: use case와 transaction
- API/MCP: 얇은 adapter

## 데이터 흐름

```text
Provider -> Raw -> Normalizer -> Validator -> Snapshot/Manifest
Snapshot + StrategyVersion + Config -> Worker -> Engine -> Result
Signal -> OrderIntent -> Risk -> ProposedOrder -> Approval -> Broker
```

Market data domain 모델은 `packages/domain`에 있고 공급자 protocol과 adapter는
`packages/market_data`에 있다. remote provider adapter는 외부 응답을 immutable raw artifact와 metadata
sidecar로 먼저 보존한 뒤 정규화한다. untrusted local upload는 bounded temporary file에서 schema/resource
검사를 통과한 뒤에만 raw artifact로 승격한다. API와 backtest는 provider SDK를 직접 호출하지 않는다.

정규화는 provider 순서와 naive-timezone 추론 provenance를 보존한다. application의
`DatasetSnapshotService`가 provider 결과를 validator에 전달하고, 오류가 없을 때만 content-addressed
normalized Parquet와 write-once manifest를 게시한다. API는 이 use case만 호출한다. provider 간 비교는
경고 report만 만들고 데이터를 합치지 않는다.

Backtest engine은 immutable snapshot reference와 이미 검증된 bar만 입력으로 받으며 provider, HTTP,
DB를 호출하지 않는다. 매 bar는 canonical 순서로 `Clock -> Market -> 기존 주문 체결 -> Strategy 평가 ->
OrderIntent/Risk -> Order -> Metrics`를 처리한다. 종가 전략 결정은 다음 instrument bar의 open부터 체결
대상이 된다. 원장과 비용은 Decimal이며 result에 order, fill, portfolio snapshot, benchmark, event log,
재현성 metadata를 함께 반환한다. Prompt 07 전까지 risk 단계는 현금·보유 수량을 확인하는 내장
pass-through 정책이고, Prompt 08에서 worker/job persistence와 연결한다.

`DslStrategyEvaluator`는 `packages.backtest.ports.StrategyEvaluator`를 구현하며 엔진의
`EvaluationContext`(현재 bar, 전체 종목이 섞인 누적 history, 포트폴리오 스냅샷)만 사용한다. evaluator는
종목별로 직전 호출과 비교해 포지션 수량 변화를 관찰함으로써 진입가·진입 시점·고점을 자체 상태로
추론하며(별도 DB나 주문 상태 조회 없이), 매 bar 지표 lookback이 부족하면 조건을 명시적으로
false로 평가해 warm-up 기간에는 주문을 생성하지 않는다. 생성되는 `OrderIntent`는 항상 `market`/`limit`
유형 또는 stop/stop_limit이며, 보수적인 gap/trigger/limit 정책을 실행 모델에 둔다.
session controls는 신호 시각의 뉴욕 weekday/clock을 사용하고 flatten도 다음 이벤트로만 체결한다.

## 저장

PostgreSQL에는 instrument와 mapping을 저장한다. Prompt 08에서 manifest, strategy version, run, summary,
order/fill, audit repository를 같은 transaction 경계에 추가한다. Parquet/object storage에는 bars와 대규모
시계열·이벤트를 저장한다.

현재 snapshot의 authoritative metadata는 write-once filesystem manifest다. URI는 storage root와 무관한
`snapshot://` logical key이고 adapter 내부에서만 실제 경로로 해석한다. 파일 저장은 `raw/`, `normalized/`,
`snapshots/` 영역을 분리한다. Prompt 08의 DB 등록은 동일 snapshot id/checksum 충돌을 거부하고
BacktestRun 생성과 함께 immutable reference를 고정해야 한다.

## Job 상태

`PENDING -> VALIDATING -> RUNNING -> SUCCEEDED/FAILED`, 취소는 `CANCELLING -> CANCELLED`.

순수 engine은 callback 기반 cooperative cancellation을 지원하며 `SUCCEEDED`, `FAILED`, `CANCELLED`
result를 반환한다. 영속 job 상태 전이와 transaction은 Prompt 08 application service가 소유한다.

## 재현성

code revision, engine/metric version, strategy hash, snapshot checksum, config, seed, provider metadata를 저장한다.

## 확장 지점

MarketDataProvider, Indicator, FeeModel, TaxModel, SlippageModel, ExecutionModel, RiskPolicy, BrokerAdapter, StorageBackend, JobQueue.

## 보안 경계

paper/production credential과 endpoint를 분리한다. MCP 조회와 주문 scope를 분리한다. Production은 approval, 상한, kill switch, audit, reconciliation이 필요하다.
