/* biome-ignore-all lint/complexity/useLiteralKeys: TypeScript requires indexed access for server JSON records. */
"use client"
import { useEffect, useRef, useState } from "react"
import type { z } from "zod"
import { pageSchema, paperSchema } from "../../lib/feature-schemas"
import { api, type JsonObject, paperMutation } from "../../lib/features"
import { ActionButton } from "../ui"
import { Field, RawArtifact, Records, useOperation } from "./panel-kit"

export function PaperPanel() {
  const [loadedAccount, setAccount] = useState<z.infer<typeof paperSchema>>(),
    [list, setList] = useState<z.infer<typeof pageSchema>>(),
    [page, setPage] = useState(1),
    [chosen, setChosen] = useState("")
  const account = loadedAccount?.account_id === chosen ? loadedAccount : undefined
  const selectedAccount = useRef(""),
    getSequence = useRef(0)
  const [orderPage, setOrderPage] = useState(1),
    [orderQuery, setOrderQuery] = useState("")
  const orders = [...(account?.orders ?? [])]
    .reverse()
    .filter((o) => JSON.stringify(o).toLocaleLowerCase().includes(orderQuery.toLocaleLowerCase()))
  const orderPages = Math.max(1, Math.ceil(orders.length / 25)),
    visiblePage = Math.min(orderPage, orderPages)
  function chooseAccount(id: string) {
    selectedAccount.current = id
    getSequence.current++
    setChosen(id)
    setRetry(undefined)
    setReconciliation(undefined)
    setOrderPage(1)
    setOrderQuery("")
  }
  const [name, setName] = useState("오프라인 연습"),
    [cash, setCash] = useState("1000"),
    [commission, setCommission] = useState("1"),
    [tax, setTax] = useState("0"),
    [slippage, setSlippage] = useState("5")
  const [symbol, setSymbol] = useState("AAPL"),
    [side, setSide] = useState("buy"),
    [quantity, setQuantity] = useState("2"),
    [price, setPrice] = useState("100"),
    [quoteAt, setQuoteAt] = useState("2024-01-02T15:00:00Z"),
    [mark, setMark] = useState("120")
  const [reconciliation, setReconciliation] = useState<JsonObject>(),
    [retry, setRetry] = useState<{ path: string; body: JsonObject; account: string }>()
  const { busy, act, feedback } = useOperation(true)
  const loadList = async (p = page) =>
    setList(pageSchema.parse(await api(`paper/accounts?page=${p}&page_size=25`)))
  async function get(id = chosen) {
    if (selectedAccount.current !== id) return
    const sequence = ++getSequence.current
    setAccount(undefined)
    const next = paperSchema.parse(await api(`paper/accounts/${id}`))
    if (sequence !== getSequence.current || selectedAccount.current !== id) return
    if (next.account_id !== id) throw new Error("현재 계좌 응답 식별자가 선택과 다릅니다.")
    setAccount(next)
    setOrderPage((old) =>
      Math.min(
        old,
        Math.max(
          1,
          Math.ceil(
            next.orders.filter((o) =>
              JSON.stringify(o).toLocaleLowerCase().includes(orderQuery.toLocaleLowerCase()),
            ).length / 25,
          ),
        ),
      ),
    )
    localStorage.setItem("research-paper", next.account_id)
    setReconciliation(undefined)
  }
  // biome-ignore lint/correctness/useExhaustiveDependencies: Restore once on mount; later account/page changes are explicit user requests.
  useEffect(() => {
    void act(async () => {
      await loadList()
      const id = localStorage.getItem("research-paper")
      if (id) {
        chooseAccount(id)
        await get(id)
      }
    })
  }, [])
  async function mutate(
    path: string,
    body: JsonObject,
    previous?: { account: string; body: JsonObject; path: string },
  ) {
    if (!account) throw new Error("먼저 연습 계좌를 선택하세요.")
    const action = previous ?? {
      account: account.account_id,
      path,
      body: { ...body, idempotency_key: crypto.randomUUID() },
    }
    setRetry(action)
    await paperMutation(action.account, action.path, action.body, (v) => {
      const next = paperSchema.parse(v)
      if (next.account_id !== action.account)
        throw new Error("현재 계좌 응답 식별자가 요청과 다릅니다.")
      if (selectedAccount.current === action.account) {
        setAccount(next)
        setOrderPage((old) =>
          Math.min(
            old,
            Math.max(
              1,
              Math.ceil(
                next.orders.filter((o) =>
                  JSON.stringify(o).toLocaleLowerCase().includes(orderQuery.toLocaleLowerCase()),
                ).length / 25,
              ),
            ),
          ),
        )
      }
    })
    setRetry(undefined)
    setReconciliation(undefined)
  }
  return (
    <section className="feature-panel">
      <h2 id="workbench-panel-title" tabIndex={-1}>
        Paper 연습
      </h2>
      {feedback}
      <p className="notice">
        수동 과거/시나리오 가격 · 실제 증권 계좌·현재 거래소 시세·실주문이 아닙니다. 승인 시 과거
        참조가로만 연습합니다. 가격 freshness·실제 거래 가능성을 검증하지 않습니다.
      </p>
      <fieldset disabled={busy}>
        <details className="result-detail" open>
          <summary>연습 계좌 생성 · 자동 재시도 없음</summary>
          <div className="form-grid">
            <Field label="연습 이름" value={name} onChange={setName} />
            <Field label="연습 원금 USD" value={cash} onChange={setCash} />
            <Field label="Paper 수수료 bps" value={commission} onChange={setCommission} />
            <Field label="Paper 매도세 bps" value={tax} onChange={setTax} />
            <Field label="Paper 슬리피지 bps" value={slippage} onChange={setSlippage} />
          </div>
          <ActionButton
            onClick={() =>
              void act(async () => {
                let id = account?.account_id
                try {
                  const created = paperSchema.parse(
                    await api("paper/accounts", {
                      name,
                      initial_cash: cash,
                      costs: {
                        commission_bps: commission,
                        sell_tax_bps: tax,
                        slippage_bps: slippage,
                      },
                    }),
                  )
                  id = created.account_id
                  chooseAccount(id)
                } finally {
                  if (id) await get(id)
                  await loadList()
                }
              })
            }
          >
            연습 계좌 생성
          </ActionButton>
          <p>생성 실패 시 목록을 확인하세요. 생성 요청을 자동 재시도하지 않습니다.</p>
        </details>
        <label className="form-field">
          연습 계좌 선택
          <select value={chosen} onChange={(e) => chooseAccount(e.target.value)}>
            <option value="">선택</option>
            {account && !list?.items.some((a) => a["account_id"] === account.account_id) && (
              <option value={account.account_id}>{account.name} · 현재 선택 계좌</option>
            )}
            {list?.items.map((a) => (
              <option key={String(a["account_id"])} value={String(a["account_id"])}>
                {String(a["name"])} · {String(a["account_id"]).slice(0, 16)}
              </option>
            ))}
          </select>
        </label>
        <div className="starter-buttons">
          <ActionButton disabled={!chosen} onClick={() => void act(() => get())}>
            현재 계좌 조회
          </ActionButton>
          <ActionButton
            disabled={page === 1}
            onClick={() =>
              void act(async () => {
                setPage(page - 1)
                await loadList(page - 1)
              })
            }
          >
            계좌 이전 25개
          </ActionButton>
          <ActionButton
            disabled={!list || page * 25 >= list.total}
            onClick={() =>
              void act(async () => {
                setPage(page + 1)
                await loadList(page + 1)
              })
            }
          >
            계좌 다음 25개
          </ActionButton>
          <ActionButton onClick={() => void act(() => loadList())}>계좌 목록 새로고침</ActionButton>
        </div>
        {account && (
          <>
            <h3>{account.name} · paper</h3>
            <dl className="feature-statistics">
              <div>
                <dt>현금 USD</dt>
                <dd data-testid="paper-cash">{account.cash}</dd>
              </div>
              <div>
                <dt>평가액 USD (현금 + 수동 평가)</dt>
                <dd data-testid="paper-equity">{account.equity}</dd>
              </div>
            </dl>
            <p>Kill switch: {account.kill_switch ? "ON" : "OFF"}</p>
            <div className="form-grid">
              <Field label="수동 종목 식별자" value={symbol} onChange={setSymbol} />
              <label className="form-field">
                방향
                <select value={side} onChange={(e) => setSide(e.target.value)}>
                  <option value="buy">매수</option>
                  <option value="sell">매도</option>
                </select>
              </label>
              <Field label="연습 수량" value={quantity} onChange={setQuantity} />
              <Field label="후보 참조 가격" value={price} onChange={setPrice} />
              <Field
                label="수동 가격 시각 (UTC offset 필수)"
                value={quoteAt}
                onChange={setQuoteAt}
              />
            </div>
            <ActionButton
              onClick={() =>
                void act(() =>
                  mutate("proposals", {
                    symbol,
                    side,
                    quantity: Number(quantity),
                    reference_price: price,
                    quote_at: quoteAt,
                  }),
                )
              }
            >
              승인 후보 생성
            </ActionButton>
            <p>후보 생성은 현금을 바꾸지 않습니다. 승인 때만 잔액·보유·위험을 재검사합니다.</p>
            <Field
              label="주문 후보 검색 (종목·ID·상태)"
              value={orderQuery}
              onChange={(v) => {
                setOrderQuery(v)
                setOrderPage(1)
              }}
            />
            <p>
              후보 작업 목록 {visiblePage} / {orderPages} · 전체 {orders.length}건 (최신 등록 순)
            </p>
            <div className="starter-buttons">
              <ActionButton
                disabled={visiblePage === 1}
                onClick={() => setOrderPage(visiblePage - 1)}
              >
                후보 이전 25개
              </ActionButton>
              <ActionButton
                disabled={visiblePage === orderPages}
                onClick={() => setOrderPage(visiblePage + 1)}
              >
                후보 다음 25개
              </ActionButton>
            </div>
            <ul className="library-list" aria-label="작업 가능한 주문 후보">
              {orders.slice((visiblePage - 1) * 25, visiblePage * 25).map((o) => (
                <li key={String(o["order_id"])} data-order-id={String(o["order_id"])}>
                  <code>{String(o["order_id"])}</code>
                  <strong>{String(o["state"])}</strong>
                  <p>
                    {String(o["side"])} {String(o["symbol"])} × {String(o["quantity"])} · 과거
                    참조가 {String(o["reference_price"])} · {String(o["quote_at"])} ·{" "}
                    {String(o["reason"] ?? "")}
                  </p>
                  {o["state"] === "pending_approval" && (
                    <div className="starter-buttons">
                      {[
                        ["approve", "승인"],
                        ["reject", "거절"],
                        ["cancel", "취소"],
                      ].map(([path, label]) => (
                        <ActionButton
                          key={path}
                          onClick={() =>
                            void act(() => mutate(`orders/${String(o["order_id"])}/${path}`, {}))
                          }
                        >
                          {label}
                        </ActionButton>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
            <div className="form-grid">
              <Field label="수동 평가 가격" value={mark} onChange={setMark} />
            </div>
            <ActionButton
              onClick={() =>
                void act(() => mutate("quotes", { symbol, price: mark, quote_at: quoteAt }))
              }
            >
              수동 가격 반영
            </ActionButton>
            <p>수동 mark는 평가액만 바꾸고 현금·체결·후보 참조가는 바꾸지 않습니다.</p>
            <ActionButton
              onClick={() =>
                void act(() => mutate("kill-switch", { enabled: !account.kill_switch }))
              }
            >
              Kill switch {account.kill_switch ? "끄기" : "켜기"}
            </ActionButton>
            <ActionButton
              onClick={() =>
                void act(async () => {
                  const result = await api(`paper/accounts/${account.account_id}/reconciliation`)
                  if (
                    selectedAccount.current === account.account_id &&
                    result["account_id"] === account.account_id
                  )
                    setReconciliation(result)
                })
              }
            >
              내부 원장 대사
            </ActionButton>
            {retry && (
              <ActionButton onClick={() => void act(() => mutate(retry.path, retry.body, retry))}>
                마지막 작업 같은 키로 재조회·재시도
              </ActionButton>
            )}
            <p>
              재시도 응답은 과거 상태일 수 있어 모든 변경 성공·실패 후 현재 GET 계좌를 다시
              읽습니다. 차단 해제 후 의도적 새 승인은 새 버튼 작업으로 수행하세요.
            </p>
            {reconciliation && (
              <>
                <p>
                  내부 paper 원장 일치: {reconciliation["consistent"] === true ? "예" : "아니오"} ·
                  외부 broker 대사 아님
                </p>
                <RawArtifact value={reconciliation} />
              </>
            )}
            <Records title="보유 포지션 · 수동 가격 출처·시각" items={account.positions} />
            <Records title="모든 주문" items={account.orders} />
            <Records title="Paper 체결" items={account.fills} />
            <Records title="감사 기록" items={account.audit} />
            <RawArtifact value={account} />
          </>
        )}
      </fieldset>
    </section>
  )
}
