# Backtesting Accuracy Standard

## 정보 가용 시점

### 분봉 연구 계약

분봉 파일 timestamp는 bar **종료 시각**이다. 09:31 종료 1분 bar는 09:30~09:31 가격이며,
09:31에 신호를 확정하고 다음 bar의 09:31 open부터 체결할 수 있다. 이는 처리 지연 0의 근사다.
open-labelled 파일을 그대로 넣지 말고 종료 시각으로 변환해야 한다. 명시적 UTC offset이 필요하며,
뉴욕 정규장 09:30~16:00 bar 종료 시각·동일 날짜 내 간격을 검사한다. 구간 첫/마지막 날은 부분
세션일 수 있다. 휴장·조기폐장·날짜 전체 누락은 calendar가 없어 검증하지 못한다. 누락을 보간하지 않는다.
limit 체결의 정확한 장중 시각과 bar 내부 경로는 재현하지 않는다. 시장가/전량 체결 근사이며
스프레드·호가 queue·체결 지연·부분 체결은 미검증이다. 초단타 실전 유효성의 증거로 사용하면 안 된다.
같은 종목에 미체결 주문이 있으면 중복 주문은 거절한다. 분봉 DAY는 세션 경계에 만료하며
일봉 DAY는 다음 eligible bar에서 미체결이면 만료한다. 종가 손절·익절은 거래소 보호 주문이 아니다.

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

웹의 수수료·매도세·슬리피지는 bps(1 bps = 0.01%)다. 기본 1/0/5 bps는 사용 예시이며 증권사의
실제 수수료가 아니다. 슬리피지는 체결 가격에 이미 반영되므로 순손익에서 다시 빼지 않는다.
최종 평가금액은 현금+마지막 종가의 보유 자산이며 미실현 손익을 포함한다.
최대 낙폭은 초기 원금을 포함한 자산 고점 대비 하락률이다. 같은 종목 단순보유는 비용과 정수 수량
제약 없는 가격 비율 참고값이며 QQQ를 읽지 않은 실행을 QQQ benchmark로 부르지 않는다.

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
