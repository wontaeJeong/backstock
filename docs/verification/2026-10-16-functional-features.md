# 기능 우선 확장 검증 기록

## 현재 상태

기능별 backend와 web 통합을 분리해 검증했다. 각 task의 구현과 집중 재리뷰를 마쳤으며 최종
전체 브랜치 리뷰·원격 CI·머지는 별도 단계다. 자세한 기능/제한은
[기능 매트릭스](../reference/research-feature-matrix.md)를 따른다.

## 연구 backend (Task 1)

- 전략/데이터/실행 보관함·보관/복원·검색/페이지, 상세 분석/CSV, 비교/별도 QQQ,
  frozen-snapshot grid·rolling train/test·독립 예산 포트폴리오 구현.
- 최초 전체 Python197, 공통 일별 상관 표본 보완 후 Python202 통과, Ruff/format/mypy117 통과.
- task 리뷰와 상관 표본 scoped 재리뷰 통과. fold-level error가 null일 때 nested test.error를 UI가
  표시해야 한다는 진단 사항은 최종 통합에서 확인한다.

## 데이터·지표·단기 체결 backend (Task 2)

- tick/quote CSV·Parquet, 별도 spread/slippage·latency·명시적 거래량 한도,
  stop/stop-limit·session controls·VWAP/Bollinger/MACD·remote minute·curated catalog 구현.
- 구현 보고 기준 Python258/Ruff/format/mypy123 통과. frontend 통합은 Task4에서 검증한다.
- 리뷰의 spread-limit 관통·pending exit와 flatten 충돌·cap 대기 stop의 발동 시각을 재현해 보완했다.
  구현 보고 기준 집중53/전체Python311 및 Ruff/format/mypy125 통과, scoped 재리뷰로 확인한다.
- controller 실제 Yahoo smoke: AAPL1m, `[2026-10-12T18:10:38Z,2026-10-15T18:10:38Z)`,
  1,169개 finalized bar를 실제 취득하여 immutable snapshot→engine succeeded와 체결을 확인했다.
  normalized checksum: `sha256:e949d5a7ccf6d6cb2fe3a9fedb19ab8a5e8b725e47c1ef57a8536fc3234a20df`.
  이 일회성 외부 가용성 관찰은 향후 Yahoo 가용성을 보장하지 않으며 offline fixture와 구분한다.

## 수동 가상매매 backend (Task 3)

- 구현 보고 기준 Python337(paper26), Ruff/format/mypy131 통과. 계좌/후보/승인/거절/취소,
  수동 시세 평가·내부 대사·kill switch·영속 idempotency와 감사 구현. backend 독립 리뷰 통과,
  웹 POST→GET 최신 상태 갱신은 최종 통합에서 확인한다.
- controller 실제 HTTP/store smoke: 초기1000, 제안 후 현금1000, 2주@참조가100 승인(기본1/0/5bps)
  후 현금799.87999. 동일 승인 retry에도 fill1개, 수동 mark120 후 equity1039.87999와 동일 현금,
  내부 대사 consistent=true, kill 활성 후 신규 제안409/KILL_SWITCH를 확인했다.
- 실제 broker/시세를 사용하지 않았고 수동 과거/시나리오 입력이다. 모든 POST 후 UI는 현재 계좌를
  다시 조회해 저장된 과거 idempotency 응답이 최신 상태로 오인되지 않게 해야 한다.

## 웹 통합과 scoped 리뷰 보완 (Task 4)

- 전략/데이터/실행 보관함·검색/보관/복원, 상세 통계·실제 가격/상태 replay·전체 CSV, 비교·별도QQQ,
  현재 전략 기반 grid/walk-forward/독립 예산 portfolio, paper 전체 조작을 실제 API/engine에 연결했다.
- fixed 수량/금액/percent equity/ATR sizing·%/ATR 손절/익절/추적 손절·요일을 한국어 폼으로 제공한다.
  임의 중첩 AST는 손실 없는 JSON 모드로 보존하며, 기본 sizing/risk에 JSON 작성을 요구하지 않는다.
- scoped 리뷰에서 분석 대상/출처 혼합, 기본 폼 누락, 26번째 이전 pending 조작 누락, Yahoo snapshot
  provenance, 검색 잠금을 재현해 수정했다. 추가 재리뷰에서 발견한 “다른 폼 분기가 미완성일 때 바꾼
  위험 설정이 복구 후 누락됨”도 신규 unit19개·실제 엔진 viewport2개 RED→GREEN으로 보완했다.
- 수정 후 Python343/Ruff/format/mypy133, 웹52 unit·production E2E54 통과 보고.
  controller는 앞선 동일 backend/source 단계에서 전체343/33/52를 직접 재검증했으며 추가 최종 검증을 수행한다.
- 각 scoped gate의 Important는 모두 재리뷰에서 addressed. 원격 CI/전체 브랜치 최종 리뷰를 대신하지 않는다.
- 실제 레이아웃: 기본 분석 main 길이390px=3367px/1440px=2626px, 핵심 수치 y≈465px/277px,
  SVG16px 및 viewBox 내부 bounds, 표14px·행≈68px·25행 페이지·1680px 내부 가로 스크롤.
  직접 모든 risk/JSON을 펼친 편집 화면은6483px/4904px이며 기본 분석/기본 실행 흐름과 구분한다.
- controller Linux 컨테이너: API/worker build·migration·health, tick engine18개 분석통계·전략 저장,
  실제 grid2개, paper 제안/승인/정확 retry/내부 대사 HTTP smoke 통과. UI 수정 중 backend만 검증한
  것으로 최종 production web 이미지 검증과 구분한다.

## 유지할 해석 제한

실제 broker/실시간 feed·queue·부분 체결·시장 충격·완전한 거래소 calendar/기업 이벤트 원장/PIT
universe는 제공한다고 주장하지 않는다. 시나리오 체결·수익과 미검증 가정을 UI에서 구분한다.
