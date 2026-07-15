# 6단계 — 조건주문 DSL과 지표

`00_GLOBAL_RULES.md`와 이전 구현을 적용한다.

임의 Python 실행 없이 일반적인 조건주문 전략을 표현하는 JSON AST를 구현한다.

## 지원

- `all`, `any`, `not`
- `gt/gte/lt/lte/eq`
- `crosses_above`, `crosses_below`
- SMA, EMA, RSI, ATR
- rolling high/low
- volume average/ratio
- return
- 보유 기간과 포지션 손익
- stop-loss, take-profit, trailing-stop
- fixed quantity/notional
- equity %, ATR risk sizing

## 작업

1. JSON Schema와 Pydantic 모델을 만든다.
2. parser/evaluator와 lookback 계산을 구현한다.
3. warm-up 기간을 명시적으로 처리한다.
4. 진입, 청산, sizing, risk, order rule을 분리한다.
5. 미래 offset, 음수 shift, 과도한 expression depth를 거절한다.
6. 전략을 canonical JSON + hash의 immutable version으로 저장한다.
7. validation API와 operator/indicator metadata API를 만든다.
8. 이동평균 교차, 평균회귀, 변동성 돌파, 리밸런싱 템플릿을 제공한다.
9. 평가 결과에 rule path와 사용 값을 남긴다.
10. `STRATEGY_DSL.md`를 실제 schema에 맞게 갱신한다.

## 완료 조건

- 코드 없이 전략을 정의한다.
- 동일 전략 버전은 변경되지 않는다.
- DSL이 OrderIntent를 생성한다.
