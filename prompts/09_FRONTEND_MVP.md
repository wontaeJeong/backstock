# 9단계 — 웹 앱 MVP

`00_GLOBAL_RULES.md`와 이전 구현을 적용한다.

## 화면

- Dashboard: 최근 실행, 전략, snapshot, 실패
- Market Data: 종목 검색, provider, 기간, Yahoo symbol, 수집, 업로드, 품질, snapshot
- Strategy: 목록, 폼/JSON 편집, validation, 버전, diff, 조건 요약
- Backtest Setup: 전략, snapshot, 자본, 비용, 슬리피지, 체결, benchmark
- Run: 상태, 진행률, 취소, 로그
- Result: 지표, equity, drawdown, 월별 수익, 주문·체결·포지션, 비용, 재현성
- Comparison: 실행과 설정 diff
- Paper Broker: 주문 후보, 승인, 거절, 상태

## UX

- 수익률과 위험을 같은 수준으로 표시
- provider와 quality warning을 숨기지 않음
- 전략 변경 시 새 버전 안내
- 실주문 UI 기본 비활성화
- loading/empty/error 상태
- 접근성 있는 form/table
- 긴 목록 pagination/virtualization

## 작업

1. typed API client를 만든다.
2. schema 기반 form validation을 적용한다.
3. 차트에 거래 marker와 hover 정보를 표시한다.
4. job polling 또는 SSE를 연결한다.
5. 샘플 데이터·전략 demo flow를 제공한다.
6. Playwright 핵심 E2E를 작성한다.
7. 사용자 가이드를 갱신한다.

## 완료 조건

- 브라우저에서 데이터→전략→실행→결과 흐름이 동작한다.
