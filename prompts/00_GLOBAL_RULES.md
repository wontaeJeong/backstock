# 공통 작업 지침

이 지침을 이후 모든 단계에 적용한다. 저장소의 `AGENTS.md`, `PRD.md`, `ARCHITECTURE.md`, `BACKTESTING_ACCURACY.md`를 먼저 읽는다.

## 목표

과거 주식 데이터로 조건주문 및 프로그램 매매 전략을 백테스트하는 웹 앱을 구현한다. 초기 제품은 연구와 paper trading이 목적이며, 실제 주문은 기본 비활성화한다. 시장 데이터, 전략, 리스크, 주문 실행은 분리하고 향후 한국투자증권 OpenAPI와 MCP를 연결할 수 있게 한다.

## 작업 규칙

- 기존 코드를 조사하고 합리적인 구조는 유지한다.
- 요청 범위 밖의 전면 재작성은 하지 않는다.
- 질문으로 작업을 멈추지 말고 합리적 기본값을 선택해 `docs/assumptions.md`에 기록한다.
- placeholder, 빈 구현, 가짜 성공 응답, 테스트 skip으로 완료 처리하지 않는다.
- 외부 API가 없어도 fixture, fake, mock adapter로 검증 가능하게 한다.
- 공급자 실패를 성공으로 위장하거나 다른 공급자로 조용히 전환하지 않는다.
- 각 단계 종료 시 구현 내용, 설계 결정, 변경 파일, 실행 명령, 테스트 결과, 제한 사항을 보고한다.

## 정확성 규칙

- 시점 `t` 종가로 만든 신호는 기본적으로 `t+1` 이전에 체결하지 않는다.
- 전략의 데이터 window를 제한하고 미래 shift를 금지한다.
- look-ahead bias, survivorship bias, corporate action, data snooping을 검토한다.
- 수수료, 세금, 슬리피지, 호가 단위, 거래 정지, 가격 제한, 부분 체결을 고려한다.
- 동일 코드·전략·snapshot·설정·seed에서는 동일 결과가 나와야 한다.
- raw/adjusted price를 혼합하지 않는다.
- timezone-aware datetime과 거래소 캘린더를 사용한다.
- 금액은 Decimal 또는 정수 단위로 처리한다.
- 데이터 누락을 경고 없이 보간하지 않는다.

## 주문 안전 규칙

- 전략은 주문을 전송하지 않고 `OrderIntent`만 생성한다.
- 리스크 검사, 승인, 브로커 전송을 분리한다.
- production trading은 별도 feature flag, credential, 상한, kill switch가 필요하다.
- 기본 환경은 mock 또는 paper broker다.
- API key, token, 계좌번호 전체를 로그에 남기지 않는다.
- 주문 재시도는 idempotency key와 상태 조회를 사용한다.

## 기본 검증

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

## 완료 보고

1. 구현 내용
2. 설계 결정
3. 변경 파일
4. 실행·검증 명령
5. 테스트 결과
6. 제한 사항
7. 다음 단계 주의점
