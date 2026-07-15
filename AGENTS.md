# AGENTS.md

이 저장소에서 코딩 에이전트가 따라야 하는 규칙이다.

## 먼저 읽기

1. `PRD.md`
2. `ARCHITECTURE.md`
3. `BACKTESTING_ACCURACY.md`
4. `DATA_PROVIDERS.md`
5. `STRATEGY_DSL.md`
6. `SECURITY.md`
7. 관련 ADR

## 작업 원칙

- 기존 코드를 조사하고 요청 범위만 변경한다.
- 비어 있는 구현, 가짜 성공, test skip으로 완료 처리하지 않는다.
- 외부 API는 adapter 뒤에 둔다.
- 네트워크 없이 fixture 테스트가 가능해야 한다.
- 불명확한 결정은 `docs/assumptions.md` 또는 ADR에 기록한다.
- 문서와 구현을 함께 갱신한다.
- 완료 시 변경, 설계, 테스트, 제한을 보고한다.

## 의존 방향

허용:

```text
web/api/worker/mcp -> application -> domain
application -> market_data/strategy/backtest/risk/broker interfaces
adapters -> interfaces
```

금지:

```text
domain -> FastAPI/Next.js/SQLAlchemy
strategy -> broker SDK
backtest -> HTTP endpoint
MCP handler -> DB나 broker 직접 접근
```

## 백테스트 금지

- 종가를 보고 같은 종가에 체결
- 미래 shift/offset
- 최신 데이터로 과거 결과 덮어쓰기
- raw/adjusted 혼합
- 현재 상장 목록을 완전한 과거 universe로 표시
- 누락 데이터를 경고 없이 forward-fill
- 비용을 0으로 숨김
- OHLC bar 내부 순서를 아는 것처럼 처리
- provider silent fallback
- 금액 float 오차 방치

## 주문 안전 금지

- 전략에서 broker 직접 호출
- 승인 없는 주문
- production 기본 활성화
- 실제 credential 테스트
- token·계좌번호 로그
- idempotency 없는 재시도
- MCP로 risk policy 우회

## 구현 기준

### Python
Python 3.12, uv, type hints, Pydantic v2, SQLAlchemy 2, timezone-aware datetime, Decimal/integer money, 순수 계산과 I/O 분리.

### TypeScript
strict mode, `any` 최소화, schema 기반 type, loading/empty/error, 접근성, 계산 로직 UI 복제 금지.

### DB
migration 필수, immutable version/snapshot update 금지, 상태 전이 transaction, order idempotency constraint.

## 필수 테스트

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
pnpm lint
pnpm typecheck
pnpm test
pnpm exec playwright test
```

백테스트 변경 시 golden/property/no-future/cost/invariant test를 추가한다. Provider 변경 시 offline fixture, timezone, adjusted/raw, checksum을 검사한다. Broker/MCP 변경 시 approval bypass, idempotency, secret redaction, feature flag off를 검사한다.

## 완료 정의

기능 동작, 관련 테스트·타입·lint 통과, migration·문서 갱신, 정확성·보안 회귀 없음, 제한 명시.
