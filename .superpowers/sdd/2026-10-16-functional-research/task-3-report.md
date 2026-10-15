# Task 3 report — 승인 기반 수동 paper backend

## 상태

**DONE** — implementation commit `cc7970d` (base `2df0d48`).
전용 worktree/branch를 그대로 사용했다. 새 worktree/branch, push, PR, merge, 하위 agent는 만들지 않았다.
부모 세션의 독립 spec/code review 및 이후 UI 통합 검증 대상이다.

## 실제 구현

- 순수 `packages/domain/paper.py`: Decimal long-only cash/position/cost basis/realized PnL,
  후보→명시적 승인→risk→labeled paper fill, 거절/취소, 수동 평가 mark, 내부 원장 대사.
  과거 pending 객체/미등록 주문으로 domain approve를 다시 호출하는 우회도 거부한다.
- `packages/application/paper.py`: use cases, bounded typed requests, `PaperStore` Protocol,
  operation+account/order target+정규화 payload의 계좌별 요청 바인딩. raw key는 SHA256만 보존한다.
- `packages/broker/paper_store.py`: 같은 계좌 POSIX flock, fsync+atomic replace, 현재 상태·감사·요청
  바인딩의 단일 authoritative commit. 사전 write-once content-addressed 계좌 commit/응답 사본과
  해시 검증. 응답은 별도 immutable blob 참조여서 현재 파일에 과거 전체 계좌 응답을 중첩 복제하지 않는다.
- `apps/api/paper.py`와 composition: 생성/목록/조회, 후보, approve/reject/cancel, quote marks,
  kill-switch, reconciliation을 실제 서비스/저장소에 연결. POST streaming 64 KiB, thread limiter 2,
  generic request-body validation/redacted error envelope.
- `PAPER_TRADING_ENABLED=false`: 503. 기본 true는 **오프라인 paper만** 활성화한다.
  production 관련 플래그를 true로 설정해도 실제 체결은 언제나 `manual_historical_paper`다.
  SDK, credential, broker network 경로가 없고 기존 execution core/frontend는 변경하지 않았다.

## Task 4 인계 계약

정확한 타입/필드/enum/에러/목록/비용/한도와 Python 표준 라이브러리 실행 예시는
`docs/reference/research-features-api.md`의 **승인 기반 수동 paper API (Task 3)** 절에 있다.

- 경로 prefix: `/paper/accounts`; 목록은 `{items,total,page,page_size}`; Decimal 출력은 문자열.
- 계좌 생성 `{name,initial_cash,costs?}`. 비용 기본 commission/sell-tax/slippage = **1/0/5 bps**,
  생성 시 고정; 각각 0..100 bps로 설정 가능하다.
- 후보 `{symbol,side,quantity,reference_price,quote_at,idempotency_key}`;
  order action은 `{idempotency_key}`; mark는 `{symbol,price,quote_at,idempotency_key}`;
  kill은 `{enabled,idempotency_key?}`다. 모두 성공 시 전체 typed account를 반환한다.
- 성공/차단의 정확한 재시도는 저장된 당시 응답/오류를 재생한다. **UI는 모든 POST 뒤 현재 GET 계좌를
  다시 조회**해야 한다. 과거 replay가 후속 kill/mark를 실제로 되돌리지 않는 테스트도 있다.
  HTTP 오류 request_id는 현재 요청 값이다. 같은 계좌 내 다른 action/order/가격/수량으로 키를
  재사용하면 409 `IDEMPOTENCY_CONFLICT`; 계좌 생성은 키를 받지 않으므로 자동 재시도하지 않는다.
- kill은 새 후보/승인만 막고 안전한 거절/취소/mark/조회/대사는 유지한다. 차단 결과가 저장된 키로는
  해제 후 자동 체결되지 않는다. 새 승인을 의도하면 새 키가 필요하다.
- marks는 cash/fill/pending reference를 변경하지 않는다. 최종 제출 mark로 평가하며 timestamp가
  최신 거래소 시각이라는 보장은 없다. 초기 포지션 mark는 fill의 참조가다.
- 원금 1000/수량 2/참조가 100/기본 비용: 현금 **799.87999**, 실행가 **100.05**, 수수료 **0.02001**.
  mark 120이면 equity **1039.87999**, 현금/체결 수는 그대로다.

## TDD 및 실제 검증

- 첫 RED: paper API 부재로 새 14개 테스트가 기대한 201 대신 404로 실패했다.
- 추가 RED: 원자 교체 후 OSError가 API에 전파됨 → sanitized 503 처리 후 동일 키 retry의 1회 체결 확인.
- 추가 RED: proposal 감사의 order_id 누락 → 생성된 주문 연결.
- 추가 RED: adverse 실행가 포함 notional 상한 우회 → 승인 시 실행 notional도 검사.
- 추가 RED: stale pending domain 객체로 재승인 가능 → 현재 계좌의 등록 주문/상태/내용 일치 검사.
- 실제 저장/서비스/API를 사용해 승인 bypass, 자금/보유 부족, 비용 round-trip, key conflict/정규화/
  restart/replay, 동시 같은 키 승인 및 서로 다른 주문 경쟁, atomic 교체 직전/직후 실패 주입,
  marks, 내부 대사/변조 탐지/읽기 전용, kill-safe actions, feature-off, production flags,
  body/숫자 경계, audit 사본 보존, key/auth/body 로그 redaction을 검증했다. mock success/skip은 없다.
- 동시 테스트에서 upstream FastAPI/Pydantic app **생성**의 warning race를 관찰했다. 실제 배포처럼
  app들을 먼저 생성한 뒤 독립 클라이언트의 요청을 동시에 전송하도록 fixture만 수정했다.

최종 실행 (Python **3.12.12**, 현재 uv 환경, 네트워크 불필요):

| 명령 | 결과 |
| --- | --- |
| `uv run --no-sync pytest` | **337 passed**, paper **26**, architecture 포함, skip/failure 없음 |
| `uv run --no-sync ruff check .` | All checks passed |
| `uv run --no-sync ruff format --check .` | 131 files already formatted |
| `uv run --no-sync mypy .` | Success: 131 source files |
| `git diff --check` | 통과 |
| 실제 `create_app().openapi()` | paper paths 7개(approve/reject/cancel은 literal action path), 요청/계좌 typed schemas 등록 |

frontend 변경/브라우저 검증은 이 task 범위가 아니며 부모 세션/Task 4가 수행한다.

## 제한·운영 가정

- 수동 과거/시나리오 연습이다. quote freshness/실제 시장 가격/달력/유동성/부분 체결/실 broker
  계좌 대사/실주문/credential 입력을 제공하지 않는다. future timestamp도 명시적 시나리오 입력으로
  취급하며 실시간 관측으로 표시하지 않는다.
- POSIX 로컬 filesystem 전용이다. NFS/분산 transaction, 외부 감사 서명, 인증/사용자별 격리,
  rate limiting, 장기 artifact 정리는 없다. 공개 서비스/실제 자산에 사용하면 안 된다.
- 감사·응답 commit 사본은 보존되며 교체 전 실패의 미참조 blob이 남을 수 있다.
  1,000개 바인딩 후 신규 위험/marks는 차단하지만 기존 replay/안전한 종료/kill/read는 유지한다.
  장기 저장 효율/안전 작업의 남용 방지는 별도 운영 과제다.
- 초기 현금≤1e9, 가격≤1e6, 정수 수량≤1e6, 참조/실행 notional≤1e6. 비용 포함 이동평균 원가,
  Decimal 계산이며 통화별 minor-unit 반올림/환전은 없다. DB migration은 필요 없다.
- 부모 작업의 `docs/superpowers/plans/2026-10-16-functional-research.md` 미커밋 수정은 건드리거나
  이 task commit에 포함하지 않았다. deferred `fold.error` nested cause도 그대로 보존했다.
