# 11단계 — Paper Broker와 승인 흐름

`00_GLOBAL_RULES.md`와 이전 구현을 적용한다.

```text
Strategy -> OrderIntent -> RiskCheck -> ProposedOrder
-> Approval -> PaperBroker -> Status/Fill -> Reconciliation
```

## 작업

1. BrokerAdapter protocol을 정의한다.
2. MockBrokerAdapter와 PaperBrokerAdapter를 구현한다.
3. paper cash, position, order, fill을 관리한다.
4. `PROPOSED`, `APPROVED`, `REJECTED`, `EXPIRED` 승인 상태를 구현한다.
5. 승인 없이 broker에 전달할 수 없게 한다.
6. client order id와 idempotency를 구현한다.
7. 상태 동기화와 reconciliation을 구현한다.
8. stale quote, market closed, risk rejection을 처리한다.
9. UI에 주문 후보와 거절 사유를 표시한다.
10. audit log를 남긴다.
11. production feature flag off 테스트를 작성한다.

## 완료 조건

- 외부 증권사 없이 주문 lifecycle을 검증한다.
- 승인과 실행이 분리된다.
