# Test Plan

## Domain
money, position, ledger, order state, fee/tax/slippage, indicator, DSL.

## Golden
buy-and-hold, MA entry/exit, limit 미체결, stop gap, 비용 역전, split/dividend, 다중 종목, 종료 정책.

현재 engine suite는 buy-and-hold, round-trip 비용, limit 미체결/gap, 다중 종목, 종료 정책을 검증한다.
MA entry/exit은 Prompt 06, stop과 split/dividend 실행은 Prompt 07 이후 범위다.

## Property
fill <= order quantity, sell <= position, equity identity, margin off에서 cash 제약, 결정성, 상태 전이.

Hypothesis로 Decimal ledger의 buy/sell round-trip, equity identity와 non-negative cash/position을 검증한다.
engine은 같은 입력의 동일 result, future bar 추가 시 과거 event/fill 불변, strategy history no-future를
별도로 검증한다.

## Provider
recorded yfinance, invalid/empty symbol, timezone provenance, split/dividend와 volume adjustment, 명시적
`RAW`/`SPLIT_ADJUSTED`/`TOTAL_RETURN_ADJUSTED`, schema 변화, raw checksum 보존.

## Dataset quality와 snapshot
중복/역순, non-positive/OHLC/volume, 빈/범위, calendar 누락, 비정상 변화, action 불일치, provider 교차
경고, lossless deterministic Parquet/checksum, storage relocation, write-once manifest, tamper/path traversal 거부.

## API
upload type/streaming size/path, Parquet signature/row/column bound, invalid raw 미승격, `DATASET_INVALID`,
snapshot 생성/조회, validation, pagination, idempotency, job lifecycle, cancellation, 오류 형식.

## Security
redaction, upload path traversal, DSL limit, approval bypass, production off, MCP scope denial.

## E2E
dataset → strategy → run → result, 비교, paper approval, 오류·경고 표시.
