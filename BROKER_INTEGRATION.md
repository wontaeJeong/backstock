# Broker Integration

## 흐름

```text
Strategy -> OrderIntent -> Risk -> ProposedOrder
-> Approval -> BrokerAdapter -> Reconciliation
```

## BrokerAdapter

계좌, cash, position, quote, place/cancel/get/list order를 공통 계약으로 제공한다.

## Adapter

- MockBrokerAdapter: 고정 응답과 failure injection
- PaperBrokerAdapter: 가상 cash/position/order/fill
- KisBrokerAdapter: 한국투자증권, 모의투자 우선

## 상태

PROPOSED, RISK_REJECTED, PENDING_APPROVAL, APPROVED, REJECTED, SUBMITTING, SUBMITTED, PARTIALLY_FILLED, FILLED, CANCELLED, EXPIRED, UNKNOWN.

## Idempotency

내부 order id와 client order id를 사용한다. Timeout 후 상태 조회 없이 POST를 재전송하지 않는다.

## Reconciliation

cash mismatch, position mismatch, unknown order, missing fill, duplicate order, stale status를 감지하고 audit event를 만든다.

## KIS 단계

공식 문서 확인 → auth → 계좌/포지션 → quote → 주문 조회 → fake contract → 모의투자 → reconciliation → 운영 runbook → 명시적 production.

## Production 조건

모의투자 E2E, 공식 명세 contract, 승인, 주문 상한, kill switch, audit, secret manager, alert, reconciliation, runbook.
