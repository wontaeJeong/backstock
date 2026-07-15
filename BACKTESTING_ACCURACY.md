# Backtesting Accuracy Standard

## 정보 가용 시점

- 일봉 종가는 장 마감 후 확정된다.
- 종가 기반 신호는 기본 다음 거래일 시가부터 체결 가능하다.
- 재무 데이터는 실제 공시 시점 이후에만 사용 가능하다.

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

## 비용

commission, tax, exchange fee, slippage를 실행 config에 저장하고 0이어도 UI에 표시한다.

## Intrabar 모호성

OHLC만으로 bar 내부 순서를 알 수 없다. Stop과 target이 모두 닿으면 conservative 정책을 기본으로 하고 ambiguous를 표시할 수 있게 한다.

## 주문 현실성

tick/lot size, volume participation, partial fill, market closed, trading halt, stale quote, price limit, insufficient cash, duplicate order를 고려한다. 미구현 항목은 결과 제한으로 표시한다.

## 시간·숫자

timezone-aware datetime과 거래소 캘린더를 사용한다. 금액은 Decimal 또는 integer minor unit을 사용한다.

## 재현성 metadata

code revision, engine/metric version, strategy hash, snapshot checksum, config, seed를 저장한다.

## 필수 테스트

golden fixture, property invariant, no-future, split/dividend, gap, cost, cash constraint, repeatability, 독립 지표 계산.
