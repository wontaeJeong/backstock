# Broker Integration

## 현재 구현: 수동·오프라인 paper 연습

`/paper/accounts`는 실제 증권 계좌가 아닌 생성된 `paper_<hex32>` 연습 계좌다.
`PaperService` → `PaperStore` Protocol → API에서 조합한 `FilePaperStore` 경계로 구현한다.
domain에는 Decimal 계산·long-only 원장만 있고 broker SDK, HTTP, credential 의존성이 없다.
`paper_trading_enabled`(기본 true)를 false로 설정하면 paper API도 503으로 차단한다.
`broker_mode=production`이나 `broker_production_enabled=true`를 설정해도 이 서비스는 **항상 paper**이며
실주문 경로로 바뀌지 않는다. 실제 production 주문 구현/credential 입력은 없다.

- 후보 생성은 현금/포지션을 바꾸지 않는다. 명시적 승인 시 kill switch·주문 금액·현금·수량을 다시
  검사하고 성공한 경우에만 `approved_paper_fill` 감사 이벤트와 labeled paper fill을 함께 기록한다.
- 매수/매도만 가능하며 공매도·마진·부분 체결·자동 전략 실행은 없다. 승인 실패는 409이며 자금 부족/
  보유 부족/금액 초과는 `risk_rejected`로 남긴다. 거절·취소는 pending 후보만 종료한다.
- 사용자가 입력한 `reference_price`/`quote_at`은 수동 과거/시나리오 가격이다. 현재 broker 호가나
  거래 가능 가격을 확인하지 않는다. 승인 시각과 가격 관측 시각을 분리한다. 후보 참조가에 선언된
  adverse slippage/수수료/매도세를 한 번만 적용한다(기본 5/1/0 bps; 실제 증권사 비용 아님).
- 수동 quote mark는 포지션 평가액/미실현 손익만 바꾼다. 현금·기존 fill·대기 후보는 바꾸지 않는다.
  마지막 **제출한** mark를 사용하며 최신 거래소 시각/실시간 가격이라는 보장이 없다.
- reconciliation은 초기 현금·paper fill·포지션·원가·실현손익·승인 감사 연결을 검사하는 **내부 원장
  대사**다. 외부 broker 잔고를 조회하거나 비교하지 않는다. kill switch 중에도 조회·대사·취소·거절은
  가능하고 새 후보/승인은 차단한다.
- 같은 계좌의 OS file lock 안에서 상태·감사·해시된 요청 바인딩을 한 JSON으로 원자 교체한다.
  write-once content-addressed commit 사본은 과거 감사 근거다. 교체 전 실패는 기존 상태를 유지하며,
  교체 후 응답 실패는 저장된 요청 결과를 재생하여 중복 체결을 막는다. 단일 POSIX 로컬 filesystem
  전용이고 NFS/분산 DB transaction/다중 사용자 인증을 제공하지 않는다.

정확한 요청·응답·상태·한도·재시도 규칙과 실행 예시는
[`docs/reference/research-features-api.md`](docs/reference/research-features-api.md)의 Task 3을 따른다.
filesystem 저장이므로 DB migration은 없다.

## 후속 broker 통합 설계 (아래는 현재 실주문 구현이 아님)

### 목표 흐름

```text
Strategy -> OrderIntent -> Risk -> ProposedOrder
-> Approval -> BrokerAdapter -> Reconciliation
```

### BrokerAdapter

계좌, cash, position, quote, place/cancel/get/list order를 공통 계약으로 제공한다.

### 계획된 Adapter

- MockBrokerAdapter: 고정 응답과 failure injection
- PaperBrokerAdapter: 향후 공통 broker 계약에 연결(현재 수동 paper는 위의 별도 서비스)
- KisBrokerAdapter: 한국투자증권, 모의투자 우선

### 목표 상태

PROPOSED, RISK_REJECTED, PENDING_APPROVAL, APPROVED, REJECTED, SUBMITTING, SUBMITTED, PARTIALLY_FILLED, FILLED, CANCELLED, EXPIRED, UNKNOWN.

### 향후 broker Idempotency

내부 order id와 client order id를 사용한다. Timeout 후 상태 조회 없이 POST를 재전송하지 않는다.

### 향후 외부 broker Reconciliation

cash mismatch, position mismatch, unknown order, missing fill, duplicate order, stale status를 감지하고 audit event를 만든다.

### KIS 단계

공식 문서 확인 → auth → 계좌/포지션 → quote → 주문 조회 → fake contract → 모의투자 → reconciliation → 운영 runbook → 명시적 production.

### Production 조건

모의투자 E2E, 공식 명세 contract, 승인, 주문 상한, kill switch, audit, secret manager, alert, reconciliation, runbook.
