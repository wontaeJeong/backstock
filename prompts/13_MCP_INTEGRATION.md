# 13단계 — MCP 연동

`00_GLOBAL_RULES.md`와 이전 구현을 적용한다.

MCP는 application service를 호출하는 얇은 adapter로 구현한다.

## 조회·연구 Tool

- search_instruments
- list_dataset_snapshots
- create_market_data_snapshot
- validate_strategy
- create_strategy_version
- run_backtest
- get_backtest_status
- get_backtest_summary
- list_backtest_trades
- compare_backtests

## Paper Tool

- list_proposed_orders
- approve_paper_order
- reject_paper_order
- get_paper_portfolio

실주문 tool은 MVP에 등록하지 않는다.

## 작업

1. 기존 Pydantic schema를 재사용한다.
2. 장시간 실행은 run id를 반환한다.
3. 응답 크기 제한과 cursor pagination을 적용한다.
4. tool별 scope와 서버 측 authorization을 구현한다.
5. paper approval은 identity와 audit log를 요구한다.
6. prompt injection이 risk policy를 우회하지 못하게 한다.
7. handler unit test와 MCP Inspector smoke test를 작성한다.
8. MCP handler가 DB나 broker를 직접 호출하지 않게 한다.

## 완료 조건

- MCP로 백테스트 실행·조회가 가능하다.
- 권한과 승인이 서버에서 강제된다.
