# Strategy DSL

## 목적

안전하고 검증 가능한 JSON AST로 전략을 표현한다. 임의 Python 코드를 실행하지 않는다.

## 상위 구조

```json
{
  "schema_version": "1",
  "name": "example",
  "universe": ["KRX:005930"],
  "timeframe": "1d",
  "entry": {},
  "exit": {},
  "position_sizing": {},
  "risk": {},
  "order": {}
}
```

## 연산

- 논리: all, any, not
- 비교: gt, gte, lt, lte, eq, crosses_above, crosses_below
- 값: constant, bar field, indicator, position, portfolio, calendar

## MVP 지표

SMA, EMA, RSI, ATR, rolling high/low, volume average/ratio, return.

각 지표는 input, parameter, minimum lookback, output type, availability timing을 제공한다.

## 주문

market, limit, stop, stop-limit, take-profit, trailing-stop, time-in-force.

## Sizing

fixed quantity, fixed notional, percent of equity, ATR risk sizing.

## Validation

알 수 없는 operator, 잘못된 type, 0 이하 period, 음수 shift, 미래 참조, 지원하지 않는 timeframe, 위험한 sizing, 과도한 expression depth를 거절한다.

## Versioning

schema validation → canonical JSON → hash → immutable StrategyVersion. 변경 시 새 version.

## 추적

Signal과 OrderIntent에 strategy version, rule path, evaluated values, timestamp, input reference, decision/rejection을 남긴다.
