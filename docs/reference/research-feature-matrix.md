# 연구 워크벤치 기능·검증 범위

로컬 연구용이며 실제 투자 성과·실시간 거래 가능성의 증거가 아니다. 금액/비율은 서버 Decimal 문자열이며
UI는 금융 수치를 재계산하지 않는다. 미정의·미실행·실패·취소를 0% 성공으로 바꾸지 않는다.

| 기능 | 구현·근거 | 제한/별도 범위 |
| --- | --- | --- |
| 전략·데이터·실행 보관함 | 서버 검색, 25건 페이지, archive/restore, 전략 immutable 버전·복제, snapshot 재사용 | filesystem 검색, 사용자 ACL/대규모 DB 인덱스 없음 |
| 조건/JSON 편집 | 한국어 지표/조건, 새 VWAP/Bollinger/MACD 파라미터, 네 가지 sizing, %/ATR 손절·익절·추적 손절과 기간·배수, 진입 요일, 서버 validation, import/export | 임의 중첩 all/any/not 조건만 고급 JSON으로 보존; sizing/risk/session 폼은 가져온 JSON의 해당 분기만 손실 없이 수정 |
| 실행 가정 | 시장가/지정가/stop/stop-limit, DAY/GTC, 뉴욕 세션, spread/latency/optional volume cap | 전량/미체결·bar-grid 근사, 실제 queue/부분 체결/충격 없음 |
| 데이터 | curated 현재 종목 검색, Yahoo 일봉/최근 분봉 명시적 기간 preset, CSV/Parquet raw tick·quote | remote tick·live feed·PIT universe 없음, provider 실패 fallback 없음, 업로드 시세 출처 미검증 |
| 분석 | 서버 payoff/수익·위험·비용/null 이유, 낙폭·월별 수익·FIFO lot·분포 원본, CSV, 검증된 OHLC/tick·quote 창과 bar-state replay·정확한 시각 체결 표식 | 25개 관측 창·종가/print 선; OHLC 내부 candle 경로를 추측하지 않음. 청산 lot 통계는 미청산 제외 |
| 비교·QQQ | 서버 실행 선택·브라우저 선택 유지, 동일 기준 검사, 별도 QQQ snapshot/remote 데이터와 공통 시각 정규화 비교 | demo QQQ는 별도 합성·같은 패턴 경고, 원래 equity를 주가라고 표시하지 않음 |
| 실험 | 현재 편집 요청 기반 2축 grid·비용 시나리오, 순차 walk-forward·중첩 오류, 2~5 구성 고정 예산 포트폴리오·서버 요약 | grid는 in-sample; train/test 독립 자본·OOS 복리 연결 없음; 현금 공유/재조정 없음; 실패/불완전 summary null |
| Paper | 계좌 create/list/get, 수동 후보·approve/reject/cancel, 수동 mark, 감사·내부 대사·kill; 모든 POST 뒤 현재 GET; 모든 후보에 25건 작업 페이지·검색·종료 후 페이지 보정 | 과거 수동 가격 연습, freshness 미검증, 실제 broker/credential/계좌번호/실주문 UI 없음; create 자동 retry 없음 |
| 접근성·보존 | 한국어 오류 초점/입력 유지·키보드 복귀, 25행 페이지·내부 스크롤, 고정 표시 16px SVG·경계 검사 | raw 식별자·metadata·definition/reason은 원본 보존; 자동 번역으로 원본 의미 변경 안 함 |

## 검증 위치

- `tests/research/test_ui_bridges.py`: 실제 snapshot preview·decode 전 cap·무결성, payoff hand calculation,
  portfolio 손익/낙폭 hand calculation·불완전 null·원본 불변.
- `apps/web/lib/features.test.ts`, `components/research/features.test.tsx`: 요청 전파, 고급 JSON 보존,
  실제 MACD sweep 경로, proxy method allowlist, paper 성공/실패 후 current GET, null·25행·체결 표식.
- `tests/e2e/features.spec.ts`: 실제 API/engine 보관함·import/export·tick quote·CSV/별도 QQQ·비교·grid/
  walk-forward/portfolio·paper 승인/위험 거절/취소/kill·키보드·390/1440 SVG/표 검증.
- 기존 `tests/e2e/research.spec.ts`의 16개 viewport 실행도 유지한다.

의도적 제외: live feed, exchange queue/partial fill, PIT 목록, corporate-action 실행 원장,
KIS/MCP 주문 통합, 인증/사용자 격리, 비동기 queue, 분산 lock/운영. synthetic 동일 패턴의 상관계수는
실제 분산 효과가 아니다. 현재 가격 표시로 수동/과거 quote를 오인하지 않도록 출처와 시각을 함께 표시한다.

## 검토 수정 1회차

- 분석/가격/CSV는 같은 응답 run_id·snapshot_id 검증 묶음이다. 실행 전환은 동기적으로 별도 상태 소유자를
  마운트하고, 실패/로딩 시 이전 근거를 숨긴다. 늦은 이전 요청은 새 대상을 덮지 않는다.
- QQQ는 기준 실행+QQQ snapshot 선택, 비교는 선택된 실행 집합에 묶는다. 선택 변경 시 이전 결과를 숨긴다.
  계좌·보관함 종류 전환도 이전 객체를 새 선택 아래 표시하지 않는다.
- 출처는 manifest.provider의 synthetic_demo/yfinance/local_file/unknown으로 중앙 분류한다.
  source=snapshot은 재사용이라는 별도 정보일 뿐 업로드 증거가 아니다. unknown은 Yahoo로 추정하지 않는다.
- 보관함은 편집 검색어와 제출 검색어를 구분한다. Enter/검색 버튼만 제출하며 글자별 GET/입력 잠금은 없다.
  페이지 이동은 제출 조건을 사용하고 오래된 응답을 버린다.
- 가져온 전략의 폼은 유효한 편집 분기를 독립적으로 JSON에 반영한다. 다른 분기가 미완성인 동안은
  전체 실행·저장·실험을 차단하되, 그 사이의 risk/sizing/session 편집을 버리지 않는다. 복구 후 현재
  모든 편집 분기를 같은 정의로 사용하며 미편집 AST/Decimal은 재생성하지 않는다.
- `tests/e2e/task4-review.spec.ts`는 실제 엔진 sizing/risk 요청·import, 26번째 이전 후보 취소+current GET,
  지연 검색/정상 타이핑, 분석/가격 실패와 늦은 응답의 실제 390/1440 브라우저 회귀를 제공한다.
