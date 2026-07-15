# MCP Integration

MCP는 application service의 adapter이며 비즈니스 로직을 복제하지 않는다.

## 연구 Tool

search_instruments, list/create_dataset_snapshot, validate/create_strategy_version, run_backtest, get_status/summary, list_trades, compare_backtests.

## Paper Tool

list_proposed_orders, approve/reject_paper_order, get_paper_portfolio.

실주문 tool은 MVP에 등록하지 않는다.

## 원칙

- 장시간 실행은 run id 반환
- cursor pagination과 응답 크기 제한
- Pydantic schema 재사용
- tool별 scope와 서버 authorization
- approval identity와 audit
- prompt injection으로 risk 우회 금지
- stale proposal 승인 금지
- 실주문은 별도 server/scope/flag 검토

## 권장 Scope

market_data:read/write, strategy:read/write, backtest:run/read, paper_order:read/approve, broker:production. 마지막 scope는 기본 발급하지 않는다.
