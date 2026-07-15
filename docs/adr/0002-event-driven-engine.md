# ADR-0002: 이벤트 기반 엔진

- Status: Accepted
- Date: 2026-07-16

## Context
벡터 수익률 계산은 주문 상태, 미체결, 비용, 현금 부족을 표현하기 어렵다.

## Decision
MarketEvent, Signal, OrderIntent, Risk, Order, Fill, Ledger 순서의 이벤트 엔진을 사용한다. 지표 계산에는 벡터 연산을 사용할 수 있다.

## Consequences
복잡도는 증가하지만 거래 추적과 paper/live 개념 공유가 가능하다.
