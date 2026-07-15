# 5단계 — 이벤트 기반 백테스트 엔진

`00_GLOBAL_RULES.md`와 이전 구현을 적용한다.

벡터 수익률만 계산하지 말고 주문·체결·원장을 명시적으로 시뮬레이션한다.

```text
ClockEvent -> MarketEvent -> StrategyEvaluation -> Signal
-> OrderIntent -> RiskEvaluation -> Order -> Fill
-> LedgerUpdate -> MetricsUpdate
```

## 필수 기능

- 일봉 clock
- 초기 자본
- 롱 포지션
- 단일·다중 종목
- 현금·포지션 원장
- realized/unrealized P&L
- 시장가·지정가
- 주문 취소·만료
- 수수료·세금·슬리피지
- benchmark
- 이벤트 로그
- 실행 취소·실패
- seed와 재현성 metadata

## 시간 규칙

- 종가 기반 신호는 기본 다음 거래일 시가 체결
- same-close 체결은 금지 또는 비현실적 모드로 명시
- 데이터 종료 시 열린 주문·포지션 정책 설정

## 작업

1. DB/HTTP 독립 순수 엔진 API를 만든다.
2. 주문 상태 머신과 cash/position ledger를 구현한다.
3. 모든 주문과 체결 근거를 이벤트에 남긴다.
4. fee/tax/slippage 모델을 구현한다.
5. 결과 요약과 상세 이벤트 저장을 분리한다.
6. 수작업 가능한 golden fixture를 만든다.
7. buy-and-hold, 현금 부족, 지정가 미체결, gap, 비용, 다중 종목을 검증한다.
8. Hypothesis invariant test를 추가한다.
9. 동일 입력 재실행 결과를 비교한다.

## 완료 조건

- 결정적 결과를 낸다.
- 모든 거래를 설명할 수 있다.
- golden 및 invariant test가 통과한다.
