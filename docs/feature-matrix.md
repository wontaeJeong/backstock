# 기능 우선 구현 범위

이 목록은 전략 연구와 가상매매 기능의 완료 기준이다. 운영 고도화보다 실제로 사용할 수 있는
기능을 우선하며, 계산 정확성·미래 참조 방지·승인·명시적인 데이터 한계는 생략하지 않는다.
아래는 구현된 기능과 실제 API/engine fixture E2E의 연결 현황이다. 최종 브랜치 리뷰·원격 CI·머지는
별도 검증 단계이며, 자세한 UI 제한과 근거는 [기능·검증 범위](reference/research-feature-matrix.md)를 따른다.

| 기능 묶음 | 현재 기준선 | 이번 추가 범위 | 완료 증거 |
| --- | --- | --- | --- |
| 전략 작성·저장 | 한국어 단일 전략 편집/JSON 확인 | 버전 보관함, 검색/복제/불러오기, JSON 편집·import/export, 네 가지 sizing·%/ATR risk·trailing·요일 폼 | 실제 sizing/risk 요청·import/form roundtrip 및 고급 AST 보존 E2E/unit |
| 데이터 관리 | 단건 업로드/일봉 수집 | snapshot 검색·상세·재사용·보관/복원, 제한 명시 원격 분봉, tick/quote 파일 | preview cap/integrity·실제 tick 업로드·manifest 원래 provider 재사용/unknown 분류·실 Yahoo1m smoke |
| 실행 관리 | 실행 ID 재조회·최근 5건 메모리 비교 | 서버 실행 기록 검색/페이지/보관·복원, 저장 실행 선택 비교 | reload/archive·제출 검색·run/snapshot scope 및 실패/늦은 전환 E2E |
| 수익·위험 분석 | 원금 대비 수익·순손익·최대 낙폭 | CAGR/변동성/Sharpe/Sortino·승률·profit factor/payoff·expectancy·노출·보유 기간 | 서버 손계산 golden·undefined null 이유·분석 E2E |
| 결과 탐색 | equity/체결/주문/JSON | 낙폭·월별 수익·완료 거래, bar 상태 리플레이, 전체 CSV | actual bar/quote·체결 표식·slider·전체 CSV E2E; 자동 애니메이션/캔들 wick 없음 |
| benchmark | 같은 종목 비용 없는 가격 비율 | 별도 QQQ 데이터와 공통 시각 비교 | 별도 AAPL/QQQ 업로드 fixture E2E·별도 데이터 검증 |
| 조건값 탐색 | 한 번에 한 설정 재실행 | 지표/조건/비중/리스크/비용의 bounded grid, 실패·미실행 명시 | 실제 run IDs·snapshot 고정·실험 E2E |
| 시간순 검증 | 없음 | train에서만 설정 선택, 다음 test 구간의 독립 자본/주문, 여러 fold | future perturbation·fresh capital·warmup backend 및 실제 fold E2E |
| 다중 종목 | 단일 종목 | 2~5개 독립 예산 분할 포트폴리오·잔여 현금·공통 시각 평가/상관 | daily correlation·실제 portfolio E2E·서버 금융 요약/null golden |
| 단기매매 가정 | 일봉/분봉 next-open, 수수료/slippage | spread·quote·latency·선택적 거래량 한도·stop/stop-limit·시간 조건 | execution/session 조합 회귀53·UI 요청 전파 E2E |
| 지표 | SMA/EMA/RSI/ATR/돌파·거래량/수익률 | rolling VWAP·Bollinger·MACD, 명시적 lookback | Decimal/no-future/warmup 테스트·실제 MACD 파라미터 unit |
| 가상매매 | 미구현 | paper 계좌·주문 제안/승인/거절/취소·수동 평가·내부 대사·감사·kill/idempotency | paper26/API-store smoke·모든 pending25건 작업 페이지/검색·26번째 이전 후보 kill 중 취소·POST 후 current GET |

fixed 수량/금액·percent equity·ATR sizing·%/ATR 손절·익절·추적 손절·요일은 한국어 폼으로
편집한다. 임의 중첩 조건처럼 간편 폼으로 정확히 나타낼 수 없는 고급 AST는 손실 없는 JSON
모드에서 보존·검증·실행한다. 모든 고급 전략을 시각적 조건 트리로 편집하는 기능은 아니다.

## 이번에 완성했다고 주장하지 않을 항목

- 실제 broker의 모의투자/실전 계좌 연결, 실제 credential, 자동 실주문.
- 유료 실시간 tick feed 계약, 거래소 호가 queue·실제 지연/시장 충격/부분 체결 재현.
- 완전한 point-in-time 상장 universe와 corporate-action 현금/주식 원장, 완전한 거래소 calendar.
- 공유 현금·동적 리밸런싱 다중 전략 engine(이번 포트폴리오는 명시적인 고정 예산 분할).
- 다중 사용자 인증·공개 운영 보안·분산 worker/queue·Kubernetes·운영 백업.

위 항목은 빈 구현으로 완료 처리하지 않는다. 연구 결과를 실전 초단타 유효성이나 미래 수익 보장으로
표시하지 않으며, 현재 데이터/체결 모델에서 확인한 결과와 미검증 가정을 구분한다.
