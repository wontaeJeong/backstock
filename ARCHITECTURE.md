# Architecture

## 현재 상태

Python 3.12 `uv` project, FastAPI adapter, worker entrypoint, Next.js web, Alembic migration,
PostgreSQL과 Docker Compose 실행 기반이 구축되어 있다. market data provider, 순수 품질 검사,
immutable Parquet snapshot과 bounded `/datasets` API가 구현되어 있다.

## 개요

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

## 재현성

code revision, engine/metric version, strategy hash, snapshot checksum, config, seed, provider metadata를 저장한다.

## 확장 지점

MarketDataProvider, Indicator, FeeModel, TaxModel, SlippageModel, ExecutionModel, RiskPolicy, BrokerAdapter, StorageBackend, JobQueue.

## 보안 경계

paper/production credential과 endpoint를 분리한다. MCP 조회와 주문 scope를 분리한다. Production은 approval, 상한, kill switch, audit, reconciliation이 필요하다.
