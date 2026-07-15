# ADR-0005: 주문 생성과 실행 분리

- Status: Accepted
- Date: 2026-07-16

## Context
전략이 broker API를 직접 호출하면 잘못된 신호나 재시도가 실제 주문으로 이어질 수 있다.

## Decision
전략은 OrderIntent를 만들고 Risk Engine, Approval, BrokerAdapter 순서로 처리한다. Production은 기본 off다.

## Consequences
흐름은 길어지지만 안전성과 감사 가능성이 높아진다.
