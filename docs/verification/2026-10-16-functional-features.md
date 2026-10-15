# 기능 우선 확장 검증 기록

## 현재 상태

기능별 backend와 web 통합을 분리해 검증한다. 아래 하위 작업 통과는 전체 UI/제품 완료를 의미하지 않는다.
최종 테스트·원격 CI·머지는 전체 통합과 독립 리뷰 후 별도로 기록한다.

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

## 유지할 해석 제한

실제 broker/실시간 feed·queue·부분 체결·시장 충격·완전한 거래소 calendar/기업 이벤트 원장/PIT
universe는 제공한다고 주장하지 않는다. 시나리오 체결·수익과 미검증 가정을 UI에서 구분한다.
