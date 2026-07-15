# ADR-0001: MVP 제품 범위

- Status: Accepted
- Date: 2026-07-16

## Context
처음부터 분봉, 최적화, 실주문까지 구현하면 정확성과 안전성 검증이 어렵다.

## Decision
일봉 백테스트, JSON DSL, Yahoo/파일 데이터, 분석, paper broker를 MVP로 한다. 실주문, 고빈도, 임의 코드 실행은 제외한다.

## Consequences
핵심 정확성을 먼저 검증할 수 있으며 장중 전략은 후속 범위가 된다.
