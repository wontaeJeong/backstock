# 7단계 — 리스크 정책과 주문 체결

`00_GLOBAL_RULES.md`와 이전 구현을 적용한다.

## 주문 유형

MARKET, LIMIT, STOP, STOP_LIMIT, TAKE_PROFIT, TRAILING_STOP

## 리스크 정책

- 종목별 최대 비중
- 총 노출
- 거래당 최대 손실
- 일일 손실 제한
- 최대 동시 포지션
- 현금 buffer
- 최소 주문 금액
- turnover 제한
- cooldown
- 중복 주문 방지
- stale quote와 거래 정지 차단

## 체결 모델

- next open/close
- limit touch
- stop trigger
- gap handling
- volume participation
- partial fill
- tick/lot size
- 주문 유효기간
- 한국 시장 가격 제한 확장 지점

같은 OHLC bar에서 stop과 target이 모두 닿는 경우 `conservative`, `optimistic`, `stop_first`, `target_first`, `reject_as_ambiguous` 정책을 지원하고 기본은 conservative다.

## 작업

1. RiskPolicy와 구조화된 rejection reason을 구현한다.
2. ExecutionModel 인터페이스를 만든다.
3. partial fill과 remaining quantity를 처리한다.
4. fixed bps, fixed tick, volume slippage를 구현한다.
5. fee/tax 설정을 시장별 버전으로 관리한다.
6. 리스크 전후 주문 정보를 이벤트 로그에 저장한다.
7. 실제 시장 규칙 값을 영구 하드코딩하지 않는다.
8. edge case 테스트를 작성한다.

## 완료 조건

- 신호와 최종 주문 후보의 차이를 설명한다.
- 체결 가정이 결과에 표시된다.
