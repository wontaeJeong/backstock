# Backtesting Accuracy Standard

## 정보 가용 시점

- 일봉 종가는 장 마감 후 확정된다.
- 종가 기반 신호는 기본 다음 거래일 시가부터 체결 가능하다.
- 재무 데이터는 실제 공시 시점 이후에만 사용 가능하다.
- 현재 엔진은 strategy evaluator에 현재 bar까지의 immutable history만 전달하고, 해당 평가에서 생성된
  주문은 같은 bar에서 체결하지 않는다.

## Look-ahead 방지

금지:
- 음수 shift
- 미래 window
- 전체 기간 통계로 과거 정규화
- 동일 종가 신호·체결
- 미래 universe 정보

## Survivorship Bias

현재 상장 종목만 사용하면 상장폐지 종목이 빠질 수 있다. Universe 출처와 기준 시점을 저장하고 point-in-time이 아니면 경고한다.

## Corporate Action

split, reverse split, dividend를 명시적으로 처리한다. 공급자 보정과 내부 보정을 중복 적용하지 않는다. 가격·volume 보정의 일관성을 검사한다.

yfinance `auto_adjust=True`는 `TOTAL_RETURN_ADJUSTED` OHLC만 소급 보정하고 volume을 `RAW`로 유지한다.
`SPLIT_ADJUSTED`와 혼동하거나 모호한 `ADJUSTED` label로 게시하지 않는다. 두 adjustment 의미와
취득 시점을 별도 metadata로 기록하며 소급 보정 값을 point-in-time 데이터로 취급하지 않는다.

## 비용

commission, tax, exchange fee, slippage를 실행 config에 저장하고 0이어도 UI에 표시한다.

현재 엔진은 commission, 매도세, adverse slippage를 각각 Decimal로 계산해 fill, event, summary에
분리 기록한다. 매도 가격이 0 이하가 되는 slippage와 매도 대금을 넘는 commission+tax 설정은 입력에서
거부한다. exchange fee model은 아직 구현하지 않았으며 Prompt 07 실행 정책 범위다.

## Intrabar 모호성

OHLC만으로 bar 내부 순서를 알 수 없다. Stop과 target이 모두 닿으면 conservative 정책을 기본으로 하고 ambiguous를 표시할 수 있게 한다.

## 주문 현실성

tick/lot size, volume participation, partial fill, market closed, trading halt, stale quote, price limit, insufficient cash, duplicate order를 고려한다. 미구현 항목은 결과 제한으로 표시한다.

현재 일봉 실행 모델은 MARKET/LIMIT, DAY/GTC, long-only를 지원한다. 매수 limit은 bar open이 limit보다
유리하면 open에, 아니면 low가 limit에 닿았을 때 limit에 체결한다. 매도는 대칭 규칙을 사용한다. 체결 전
현금과 보유 수량을 다시 검사하고, 부족하면 주문을 명시적으로 거절한다. partial fill, stop, volume
participation, 거래소 calendar 제약은 아직 지원하지 않는다.

주문과 취소 intent의 timestamp는 현재 strategy evaluation bar와 같아야 하며, 다른 시점의 취소는 현재
bar timestamp의 `order_cancel_rejected` event로 남기고 적용하지 않는다.

종료 시 기본값은 미체결 주문을 expire하고 포지션을 마지막 close로 평가하는 것이다. 명시적으로
`LIQUIDATE_AT_LAST_CLOSE`를 선택하면 마지막 close에서 비용을 반영해 청산한다.

## 시간·숫자

timezone-aware datetime과 거래소 캘린더를 사용한다. 금액은 Decimal 또는 integer minor unit을 사용한다.

## 재현성 metadata

code revision, engine/metric version, strategy hash, snapshot checksum, config, seed를 저장한다.

현재 result는 immutable snapshot id/checksum, strategy version, code revision, engine version, seed를
포함한다. 같은 입력은 canonical `(timestamp, instrument_id)` 순서로 처리되어 동일한 result를 만든다.

## 필수 테스트

golden fixture, property invariant, no-future, split/dividend, gap, cost, cash constraint, repeatability, 독립 지표 계산.

Prompt 05 구현은 hand-calculated buy-and-hold/round-trip, limit/gap, 비용, cash/position 제약,
다중 종목 순서, 종료 정책, 취소/실패, 결정성, no-future, Decimal ledger Hypothesis invariant를 검증한다.
split/dividend 실행과 독립 고급 지표는 후속 analytics 범위다.
