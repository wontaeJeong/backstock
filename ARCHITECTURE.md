# Architecture

## 현재 상태

현재 저장소에는 기준 문서만 있으며 아래 구조와 흐름은 2단계 이후 구축할 목표 아키텍처다. 실행 코드나 배포 구성이 이미 존재한다는 의미가 아니다.

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

## 목표 구조

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
