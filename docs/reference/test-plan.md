# Test Plan

## Domain
money, position, ledger, order state, fee/tax/slippage, indicator, DSL.

## Golden
buy-and-hold, MA entry/exit, limit 미체결, stop gap, 비용 역전, split/dividend, 다중 종목, 종료 정책.

## Property
fill <= order quantity, sell <= position, equity identity, margin off에서 cash 제약, 결정성, 상태 전이.

## Provider
recorded yfinance, invalid/empty symbol, timezone, action, adjusted/raw, schema 변화.

## API
validation, pagination, idempotency, job lifecycle, cancellation, 오류 형식.

## Security
redaction, upload path traversal, DSL limit, approval bypass, production off, MCP scope denial.

## E2E
dataset → strategy → run → result, 비교, paper approval, 오류·경고 표시.
