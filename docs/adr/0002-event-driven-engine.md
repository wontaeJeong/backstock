# ADR-0002: 이벤트 기반 엔진

- Status: Accepted
- Date: 2026-07-16

## Context
벡터 수익률 계산은 주문 상태, 미체결, 비용, 현금 부족을 표현하기 어렵다.

## Decision
MarketEvent, Signal, OrderIntent, Risk, Order, Fill, Ledger 순서의 이벤트 엔진을 사용한다. 지표 계산에는 벡터 연산을 사용할 수 있다.

일봉 구현은 canonical `(timestamp, instrument_id)` 순서로 `Clock -> Market -> 이전 주문 체결 -> Strategy
평가 -> OrderIntent/Risk -> Order -> Metrics`를 기록한다. 종가 전략은 현재 bar까지의 history만 받고,
생성한 주문은 다음 종목 bar의 open부터 실행한다. 엔진은 immutable input과 result를 사용하는 순수
library이며, 실행 중 상태는 run마다 격리한다.

현재 risk 단계는 현금·보유 수량을 검증하는 pass-through 정책이다. Prompt 07에서 별도 risk/execution
policy를 연결하고 Prompt 08에서 job persistence를 추가하되 event engine은 HTTP, DB, broker SDK에
의존하지 않는다.

## Consequences
복잡도는 증가하지만 거래 추적과 paper/live 개념 공유가 가능하다. 모든 state transition과 비용을
순서가 있는 event log로 설명할 수 있고 cancellation/failure도 partial result로 보존한다. 대신 일봉
OHLC만으로 intrabar 순서를 추정하지 않으며, 현재 전량 체결 모델의 제한을 결과 소비자에게 공개해야 한다.
