# Metrics Reference

구현 시 수식, annualization, edge case를 확정해 갱신한다.

- Total return: `ending_equity / starting_equity - 1`
- CAGR: `(ending / starting)^(1/years) - 1`
- Volatility: period return 표준편차 × annualization factor 제곱근
- Sharpe: annualized excess return / annualized volatility
- Sortino: downside deviation 사용
- Maximum drawdown: 이전 peak 대비 최대 하락률
- Profit factor: gross profit / absolute gross loss
- Expectancy: win_rate × avg_win - loss_rate × avg_loss
- Turnover: 선택한 정의를 코드와 UI에 명시

거래 없음, 0분산, 손실 없음의 JSON 표현을 명시적으로 처리한다.
