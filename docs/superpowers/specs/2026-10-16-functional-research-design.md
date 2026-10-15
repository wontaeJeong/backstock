# 기능 우선 전략 연구 워크벤치

## 사용자 요청과 진행 기준

운영 고도화보다 사용 가능한 기능을 우선한다. 사용자는 추가 질문 없이 추천 기능을 구현하고 검증 후
머지까지 진행하도록 승인했다. 특정 매매법은 사전 요구하지 않는다. Python/FastAPI·Next.js·기존
snapshot/Decimal engine을 유지하며, 실주문·실제 credential·자동 외부 배포는 제외한다.

## 이번 기능 목록과 완료 조건

1. **전략 보관함**: 이름/설명과 불변 버전 저장, 검색, 불러오기·복제·수정 후 새 버전 저장,
   JSON import/export. 보관/복원으로 목록을 관리하되 원본 버전을 덮어쓰거나 삭제하지 않는다.
2. **데이터 보관함**: 업로드/수집 snapshot 검색·목록·상세·재사용·보관/복원. 종목·주기·기간·품질을 표시한다.
3. **실행 기록**: 서버에 남은 실행 검색·페이지 탐색·다시 열기·보관/복원, 이름 대신 ID만 요구하지 않는다.
   원래 저장한 payload의 hash를 검증해 모델에 필드가 추가되어도 과거 결과를 손상으로 오인하지 않는다.
4. **분석**: 총수익/순손익/낙폭 외에 CAGR, 일별 변동성·Sharpe·Sortino, 승률·손익비·profit factor·
   expectancy·회전율·노출·평균 보유 기간·완료 거래와 미청산 구분. 데이터 부족/분모 0은 null과 사유로
   표시한다. 분봉 Sharpe는 뉴욕 날짜별 마지막 평가액을 일 단위로 집계하고 연율화 가정을 명시한다.
5. **결과 탐색**: 자산/낙폭·월별 수익·완료 거래·매수/매도 근거와 bar별 포트폴리오 리플레이, CSV/JSON export.
   금융 계산은 서버에 둔다. CSV 문자열의 spreadsheet formula injection을 방지하고 전체 행을 보존한다.
6. **비교**: 저장한 2~8개 실행 비교, 동일 데이터/기간/원금 여부 경고, 별도 QQQ snapshot을 사용하는
   비용 없는 단순보유 benchmark. QQQ를 읽지 않고 QQQ 결과라 표시하지 않는다.
7. **조건값 실험**: 지표 기간/조건 임계값/투자 비중/리스크/비용을 최대 2축, 총 16조합으로 실제 engine 실행한다.
   기초 snapshot을 한 번 고정하여 매 조합마다 다른 원격 데이터를 읽지 않는다. 결과는 실제 run ID에 연결한다.
   실패·시간 초과를 수익률 0으로 채우지 않고 in-sample 선택/과최적화 경고를 노출한다.
8. **시간순 검증**: rolling train/test 구간, 학습 구간에서만 조건값 선택 후 다음 구간에 적용한다.
   test의 지표 준비에는 과거 train history만 사용할 수 있으나 train 구간의 주문·포지션은 전달하지 않는다.
   최대 4 folds, 총 32 engine runs·30초 cooperative experiment budget. 미실행은 명시한다.
9. **고정 예산 포트폴리오**: 2~5개 종목/전략에 원금을 분할한 독립 subaccount 결과를 합산한다.
   총 비중 100% 이하, 남은 현금 명시, USD·주기 일치, 공통 평가 시각만 비교하고 누락/제외를 경고한다.
   공유 현금·동적 리밸런싱 포트폴리오로 가장하지 않는다. 상관계수는 충분한 공통 일별 표본이 있을 때만 계산한다.
10. **단기매매 체결 가정**: spread bps, latency ms, volume participation/all-or-none 미체결 가정,
    stop/stop-limit·시장가/지정가, 정규장 진입 시간/요일과 장 마감 신규 진입 제한·청산 조건.
    intrabar 순서를 추정하지 않는 보수 정책과 zero-latency 기준 대비 비용·지연 재실험을 제공한다.
11. **고해상도 데이터 실험**: 실제 Yahoo 1분/5분의 공급자 기간 제한을 명시한 수집, 로컬 tick/quote 파일
    (timezone-aware unique timestamp, price/size, optional bid/ask), 다음 eligible event 체결.
    tick은 거래 print/제공 quote의 재생이지 거래소 queue·실제 주문 충격/부분 체결·HFT 실전 입증이 아니다.
    free provider 실패 시 자동 fallback 금지. 합성 데모는 모든 화면에서 구분한다.
12. **지표/편집 확장**: 기존 SMA/EMA/RSI/ATR/돌파/거래량 외에 rolling VWAP, Bollinger upper/lower,
    MACD(명시적 fast/slow/signal)와 시간 조건, 주문 설정, JSON 편집·검증을 연결한다.
13. **가상매매 연습**: 실제 자금 없는 paper 계좌, 제안→사용자 승인/거절→가상 체결/취소,
    현금·포지션·비용·감사 이력, 잔고/수량/주문 상한·kill switch·idempotency.
    시세는 명시적으로 저장된 snapshot/사용자 제공 시각의 가상 시세이며 실시간 broker로 가장하지 않는다.

## 제약과 안전

Python 3.12 / Node 24 / pnpm 11.1.2. 원래의 계산·비용·미래 참조 방지·승인/idempotency 테스트는
생략하지 않는다. 기능 없는 버튼/가짜 성공/미실행 0/실주문 기본 활성화를 금지한다.
운영 인증·분산 queue·Kubernetes·백업·새로운 CI 플랫폼은 이번 범위가 아니다. 사용자가 실제 broker를
연결하지 않아도 모든 핵심 기능이 offline fixture로 동작해야 한다.

## UI

한국어 탭/탐색으로 전략 작성, 보관함, 분석/비교, 실험, 가상매매를 연결한다. 현재 편집 중인 전략에서
실험과 저장을 바로 시작할 수 있고, 불러오기/복제는 입력을 명확히 갱신한다. 로딩/빈 상태/실패·복귀를
제공한다. 실패한 요청은 이전 성공과 구분한다. 390px/1440px에서 실제 브라우저로 검증한다.
상세 목록은 25행 페이지, 표·그래프 내부 스크롤, 실제 표시 글자 14px 이상을 유지한다.

## 구현 결정

기존 filesystem adapter를 확장하여 로컬 기능을 먼저 완결한다. mutable paper 계좌는 lock+atomic
replace, 불변 전략/실행/실험과 감사 이벤트는 content hash·write-once 게시를 사용한다. 데이터 단위와
원본 계보를 유지한다. remote tick/실시간 feed·broker credential 연결은 구현했다고 주장하지 않는다.
