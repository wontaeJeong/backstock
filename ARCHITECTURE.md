# Architecture

## 현재 상태

Python 3.12 `uv` project, FastAPI adapter, worker entrypoint, Next.js web, Alembic migration, PostgreSQL과 Docker Compose 실행 기반이 구축되어 있다. Domain/application과 기능 package는 framework 독립 Python package로 확장한다.

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

## 저장

PostgreSQL에는 instrument, mapping, manifest, strategy version, run, summary, order/fill, audit를 저장한다. Parquet/object storage에는 bars와 대규모 시계열·이벤트를 저장한다.

## Job 상태

`PENDING -> VALIDATING -> RUNNING -> SUCCEEDED/FAILED`, 취소는 `CANCELLING -> CANCELLED`.

## 재현성

code revision, engine/metric version, strategy hash, snapshot checksum, config, seed, provider metadata를 저장한다.

## 확장 지점

MarketDataProvider, Indicator, FeeModel, TaxModel, SlippageModel, ExecutionModel, RiskPolicy, BrokerAdapter, StorageBackend, JobQueue.

## 보안 경계

paper/production credential과 endpoint를 분리한다. MCP 조회와 주문 scope를 분리한다. Production은 approval, 상한, kill switch, audit, reconciliation이 필요하다.
