# 나스닥 연구 MVP 검증 기록

## 결론과 제한

로컬 연구 MVP의 한국어 전략 작성 → 과거 데이터 snapshot → 실제 engine 실행 → 원금 대비
손익/낙폭·체결 근거·JSON export 흐름을 검증했다. 틱·호가·실제 지연 기반 초단타 검증,
실주문, 공개 운영 인증, 비동기 worker job까지 완성되었다는 의미는 아니다.
수익률 예시는 성능 향상이나 투자 수익 보장으로 해석하지 않는다.

## 검증 환경과 결과

Mac ARM64 / Python 3.12.12 / Node 24.16.0 / pnpm 11.1.2.
전용 워크트리에서 실행했으며 기본 main의 기존 미커밋 파일은 변경하지 않았다.

| 검증 | 관찰 결과 |
| --- | --- |
| frozen uv/pnpm 설치 | 성공 |
| Ruff check / format --check | 통과 |
| mypy | 103개 Python 소스 통과 |
| pytest | 166개 통과 |
| pnpm lint / typecheck / test | 통과, 웹 unit 7개 |
| pnpm build | production standalone 성공 |
| production Playwright | Chromium 1440px/390px 총 10개 통과 |
| 실제 Yahoo acquisition | AAPL, `[2024-01-01, 2024-02-01)`, 21개 일봉 snapshot 및 engine succeeded |
| Docker images | API/migration/worker/web 모두 build 성공 |
| production Compose | migration 성공 후 stack 기동, web→API filesystem readiness 통과 |
| 컨테이너 실제 simulation | production web proxy→API→synthetic minute snapshot→engine, 120 bar/체결 1건 |
| PostgreSQL 17 | 실제 upgrade, downgrade base, re-upgrade 및 FK/check/exclusion 제약 검사 통과 |
| public static artifact | production 이미지의 분봉 CSV 형식 예시 다운로드 성공 |

Docker의 최초 포트 18000은 다른 프로젝트가 사용 중이어서 해당 프로젝트를 건드리지 않고
28000/23000으로 변경했다. 이미지 build와 stack 기동을 한 명령으로 실행한 검증은 120초에
시간 제한되었으나, build 성공을 확인하고 별도 stack/시뮬레이션 검사로 완료했다.
Yahoo smoke는 외부 네트워크에 의존하므로 CI에 강제하지 않고 offline fixture를 별도로 검증한다.
원격 GitHub CI와 수동 이미지 발행은 이 로컬 결과와 구분한다. 이미지 발행 workflow는 실행하지 않았다.

## UX 실측

기존 화면은 foundation 상태라 수익 결과 화면과 E2E 자체가 없었다. 의미 없는 0% 기준선을 만들지 않았다.
개발 중 모바일 금액이 두 줄로 끊기고, 결과 이동이 고정 상단 바까지 스크롤하는 문제가 있었으며
통화 표시·숫자 영역·DOM commit 후 main 내부 이동을 보완했다.

| 측정 항목 | 1440px | 390px |
| --- | --- | --- |
| document scrollWidth | 1440px | 390px |
| main 전체 scrollHeight | 2732px | 4183px |
| 실행 후 결과 제목 위치 | 약 16px | 약 85px |
| 상단 탐색 높이 | 좌측 1000px | 69px |
| viewBox 축소 반영 SVG 실제 글자 | 약 14.15px | 14px |

그래프와 표는 자체 가로 스크롤을 제공한다. 키보드로 체결 목록을 펼치고 접근 가능한 scroll
region을 확인했다. 상세 근거는 기본 접기, 긴 행은 25건 단위 페이지로 나누며 전체 원본은 JSON으로
보존한다. export는 실제 API 응답과 deep equality로 비교해 경고 severity 등 metadata 손실도 검사했다.

## 재현 가능한 회귀 사례

- 지표가 준비되기 전 `not` 조건이 주문을 만들던 문제: RED→GREEN.
- 분봉 DAY가 다음 bar에서 만료되던 문제: 세션 경계로 수정, 이후 세션 체결 금지 검사.
- 미체결 GTC 중복 주문, 일봉으로 표시한 분봉, USD가 아닌 snapshot, 과도한 숫자/조건 트리 거부.
- 부분 파일이 노출되던 immutable 게시: atomic no-replace 게시로 보완.
- 결과 무결성·전략 hash·snapshot checksum, 비용으로 순손익이 감소하되 slippage 이중 차감하지 않음.
- 초단타 한계 표시, 실패 시 입력 보존 및 가짜 0%/합성 fallback 금지, 설정 변경 시 이전 결과 구분.
