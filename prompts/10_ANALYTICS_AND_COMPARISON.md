# 10단계 — 성과 분석과 실행 비교

`00_GLOBAL_RULES.md`와 이전 구현을 적용한다.

## 지표

total return, CAGR, annualized volatility, Sharpe, Sortino, max drawdown, Calmar, win rate, average win/loss, payoff ratio, profit factor, expectancy, exposure, turnover, trade count, holding period, fee, tax, slippage, benchmark return, excess return

## 분석

- 월·연도 수익률
- rolling return/volatility/Sharpe
- drawdown 구간
- 종목별 기여도
- 규칙별 성과
- 비용 전후
- 파라미터별 실행 비교
- in-sample/out-of-sample
- 비용 민감도

## 작업

1. 수학적 정의와 annualization을 문서화한다.
2. risk-free rate를 config로 둔다.
3. 거래 없음, 0분산, 짧은 기간을 안전하게 처리한다.
4. benchmark가 없으면 null과 설명을 반환한다.
5. JSON/CSV export를 구현한다.
6. 비교 API와 UI를 구현한다.
7. 자동 요약은 사실 설명으로 제한하고 투자 권고를 생성하지 않는다.
8. 독립 fixture로 지표를 검증한다.

## 완료 조건

- 모든 지표에 정의와 테스트가 있다.
- 비용 가정 변화가 명확히 보인다.
