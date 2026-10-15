import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { AnalysisPanel } from "./analysis-panel"
import { LibraryPanel } from "./library-panel"
import { PaperPanel } from "./paper-panel"
import { A, B, C, fixtureAnalysis, fixtureBars, fixtureReport, json } from "./review-fixtures"

beforeEach(() => {
  localStorage.clear()
  HTMLElement.prototype.scrollIntoView = vi.fn()
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
const empty = { items: [], total: 0, page: 1, page_size: 25 }
function analysisFetch(failurePath = "") {
  return vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input)
    if (failurePath && path.includes(B) && path.includes(failurePath))
      return json({ message: "검증 실패" }, 409)
    if (path.includes("/analysis")) {
      const id = path.includes(B) ? B : A
      return json(fixtureAnalysis(id, id === A ? "A_ONLY_METRIC" : "B_ONLY_METRIC"))
    }
    if (path.includes("/bars")) return json(fixtureBars(path.includes(B) ? B : A))
    return json(empty)
  })
}
it("I4 재사용 Yahoo snapshot을 업로드 파일로 오인하지 않는다", async () => {
  vi.stubGlobal("fetch", analysisFetch())
  render(<AnalysisPanel report={fixtureReport(A, "yfinance")} onRun={() => {}} />)
  await screen.findByText("A_ONLY_METRIC")
  expect(screen.queryByText(/사용자 파일 · 시세 출처 미검증/)).not.toBeInTheDocument()
  expect(screen.getByText(/Yahoo 과거 시세/)).toBeInTheDocument()
})

for (const failure of ["/analysis", "/bars"])
  it(`I1 ${failure} 실패 전환은 이전 통계·가격·CSV를 즉시 숨긴다`, async () => {
    vi.stubGlobal("fetch", analysisFetch(failure))
    const view = render(<AnalysisPanel report={fixtureReport(A, "yfinance")} onRun={() => {}} />)
    await screen.findByText("A_ONLY_METRIC")
    view.rerender(<AnalysisPanel report={fixtureReport(B, "local_file")} onRun={() => {}} />)
    expect(screen.queryByText("A_ONLY_METRIC")).not.toBeInTheDocument()
    expect(screen.queryByRole("link", { name: "체결 CSV" })).not.toBeInTheDocument()
    expect(
      screen.queryByRole("img", { name: "검증된 snapshot 가격 · USD" }),
    ).not.toBeInTheDocument()
    await screen.findByText(/검증 실패/)
    expect(screen.queryByText("A_ONLY_METRIC")).not.toBeInTheDocument()
  })
it("I1 늦게 온 A 응답이 이미 선택된 B를 덮지 않는다", async () => {
  let resolveA: (value: Response) => void = () => {}
  const normal = analysisFetch()
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      String(input).includes(`${A}/analysis`)
        ? new Promise<Response>((resolve) => {
            resolveA = resolve
          })
        : normal(input),
    ),
  )
  const view = render(<AnalysisPanel report={fixtureReport(A)} onRun={() => {}} />)
  await waitFor(() => expect(normal).toHaveBeenCalled())
  view.rerender(<AnalysisPanel report={fixtureReport(B)} onRun={() => {}} />)
  await screen.findByText("B_ONLY_METRIC")
  await act(async () => resolveA(json(fixtureAnalysis(A, "LATE_A_METRIC"))))
  expect(screen.queryByText("LATE_A_METRIC")).not.toBeInTheDocument()
  expect(screen.getByText("B_ONLY_METRIC")).toBeInTheDocument()
})
it("M1 검색은 제출 때만 조회하고 로딩 중에도 정상 타이핑을 보존한다", async () => {
  const calls: string[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      calls.push(String(input))
      return json(empty)
    }),
  )
  render(
    <LibraryPanel
      strategy={() => ({})}
      onStrategy={() => {}}
      onSnapshot={() => {}}
      onRun={() => {}}
    />,
  )
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "현재 전략 저장" })).not.toBeDisabled(),
  )
  fireEvent.change(screen.getByLabelText("보관함 검색"), { target: { value: "Tesla" } })
  expect(calls).toHaveLength(1)
  expect(screen.getByLabelText("보관함 검색")).not.toBeDisabled()
  fireEvent.click(screen.getByRole("button", { name: "검색" }))
  await waitFor(() => expect(calls).toHaveLength(2))
  expect(calls[1]).toContain("q=Tesla")
})
it("I3 26번째 이전 pending 후보에도 안전한 취소 버튼이 있다", async () => {
  const id = `paper_${"a".repeat(32)}`
  localStorage.setItem("research-paper", id)
  const orders = Array.from({ length: 26 }, (_, i) => ({
    order_id: `order-${i}`,
    symbol: "AAPL",
    side: "buy",
    quantity: 1,
    reference_price: "100",
    quote_at: "2024-01-02T15:00:00Z",
    state: "pending_approval",
  }))
  const account = {
    account_id: id,
    name: "많은 후보",
    cash: "1000",
    equity: "1000",
    kill_switch: true,
    positions: [],
    orders,
    fills: [],
    audit: [],
  }
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) =>
      String(input).includes("?") ? json({ ...empty, items: [account], total: 1 }) : json(account),
    ),
  )
  render(<PaperPanel />)
  await screen.findByText("Kill switch: ON")
  fireEvent.click(screen.getByRole("button", { name: "후보 다음 25개" }))
  expect(
    within(screen.getByRole("list", { name: "작업 가능한 주문 후보" })).getByText("order-0"),
  ).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "취소" })).not.toBeDisabled()
})

it("I1 QQQ 결과는 기준 실행과 snapshot 선택이 바뀌면 즉시 사라진다", async () => {
  const normal = analysisFetch()
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) =>
      String(input).endsWith("research/benchmark")
        ? json({
            run_id: A,
            snapshot_id: C,
            provider: "QQQ_OLD_RESULT",
            benchmark_return: "0.01",
            reason: null,
            warnings: [],
            points: [],
          })
        : String(input).includes("datasets?q=QQQ")
          ? json({
              ...empty,
              total: 1,
              items: [{ snapshot_id: C, provider: "local_file", interval: "1d" }],
            })
          : normal(input),
    ),
  )
  const view = render(<AnalysisPanel report={fixtureReport(A)} onRun={() => {}} />)
  await screen.findByText("A_ONLY_METRIC")
  fireEvent.click(screen.getByText("실행 비교·QQQ 설정"))
  fireEvent.click(screen.getByRole("button", { name: "QQQ 별도 데이터 비교" }))
  await screen.findByText(/QQQ · QQQ_OLD_RESULT/)
  fireEvent.change(screen.getByLabelText(/QQQ snapshot 선택/), { target: { value: C } })
  expect(screen.queryByText(/QQQ · QQQ_OLD_RESULT/)).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "QQQ 별도 데이터 비교" }))
  await screen.findByText(/QQQ · QQQ_OLD_RESULT/)
  view.rerender(<AnalysisPanel report={fixtureReport(B)} onRun={() => {}} />)
  expect(screen.queryByText(/QQQ · QQQ_OLD_RESULT/)).not.toBeInTheDocument()
})
it("I1 비교 결과는 현재 선택 집합에만 속하며 늦은 이전 비교를 무시한다", async () => {
  localStorage.setItem("research-compare", JSON.stringify([A, B]))
  let resolve: (value: Response) => void = () => {}
  const normal = analysisFetch()
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      String(input).endsWith("research/compare")
        ? new Promise<Response>((r) => {
            resolve = r
          })
        : String(input).includes("library/runs")
          ? Promise.resolve(
              json({
                ...empty,
                total: 3,
                items: [fixtureReport(A), fixtureReport(B), fixtureReport(C)],
              }),
            )
          : normal(input),
    ),
  )
  render(<AnalysisPanel report={fixtureReport(A)} onRun={() => {}} />)
  await screen.findByText("A_ONLY_METRIC")
  fireEvent.click(screen.getByText("실행 비교·QQQ 설정"))
  fireEvent.click(screen.getByRole("button", { name: "선택 실행 비교" }))
  fireEvent.click(screen.getAllByRole("checkbox")[2] as HTMLElement)
  await act(async () =>
    resolve(
      json({
        comparable: true,
        rows: [{ run_id: A }, { run_id: B }],
        warnings: [],
        differences: [],
      }),
    ),
  )
  expect(screen.queryByText("동일 기준 비교 가능")).not.toBeInTheDocument()
})
it("I1 잘못된 응답 run/snapshot ID를 분석·가격에 적용하지 않는다", async () => {
  const normal = analysisFetch()
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) =>
      String(input).includes("/bars") ? json(fixtureBars(B)) : normal(input),
    ),
  )
  render(<AnalysisPanel report={fixtureReport(A)} onRun={() => {}} />)
  await screen.findByText(/응답 실행·snapshot 식별자가 선택과 다릅니다/)
  expect(screen.queryByText("A_ONLY_METRIC")).not.toBeInTheDocument()
  expect(screen.queryByRole("link", { name: "체결 CSV" })).not.toBeInTheDocument()
})
it("M1 제출된 검색 응답만 적용하며 새 입력은 로딩 중에도 보존한다", async () => {
  let late: (value: Response) => void = () => {}
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      String(input).includes("q=old")
        ? new Promise<Response>((resolve) => {
            late = resolve
          })
        : Promise.resolve(
            json({ ...empty, items: [{ strategy_id: A, name: "NEW_SCOPE" }], total: 1 }),
          ),
    ),
  )
  render(
    <LibraryPanel
      strategy={() => ({})}
      onStrategy={() => {}}
      onSnapshot={() => {}}
      onRun={() => {}}
    />,
  )
  await screen.findByText("NEW_SCOPE")
  fireEvent.change(screen.getByLabelText("보관함 검색"), { target: { value: "old" } })
  fireEvent.submit(screen.getByLabelText("보관함 검색").closest("form") as HTMLFormElement)
  expect(screen.getByLabelText("보관함 검색")).not.toBeDisabled()
  fireEvent.change(screen.getByLabelText("보관함 검색"), { target: { value: "new" } })
  fireEvent.submit(screen.getByLabelText("보관함 검색").closest("form") as HTMLFormElement)
  await screen.findByText("NEW_SCOPE")
  await act(async () =>
    late(json({ ...empty, items: [{ strategy_id: B, name: "OLD_SCOPE" }], total: 1 })),
  )
  expect(screen.queryByText("OLD_SCOPE")).not.toBeInTheDocument()
  expect(screen.getByLabelText("보관함 검색")).toHaveValue("new")
})

it("M1 페이지 이동은 미제출 입력이 아닌 제출된 검색을 재사용한다", async () => {
  const urls: string[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      urls.push(String(input))
      return json({ ...empty, total: 50, items: [{ strategy_id: A, name: "row" }] })
    }),
  )
  render(
    <LibraryPanel
      strategy={() => ({})}
      onStrategy={() => {}}
      onSnapshot={() => {}}
      onRun={() => {}}
    />,
  )
  await screen.findByText("row")
  fireEvent.change(screen.getByLabelText("보관함 검색"), { target: { value: "submitted" } })
  fireEvent.click(screen.getByRole("button", { name: "검색" }))
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "보관함 다음" })).not.toBeDisabled(),
  )
  fireEvent.change(screen.getByLabelText("보관함 검색"), { target: { value: "unsubmitted" } })
  fireEvent.click(screen.getByRole("button", { name: "보관함 다음" }))
  await waitFor(() => expect(urls.at(-1)).toContain("page=2"))
  expect(urls.at(-1)).toContain("q=submitted")
})
it("I1 보관함 종류 변경 후 늦은 이전 종류 결과는 적용하지 않는다", async () => {
  let resolve: (value: Response) => void = () => {}
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      String(input).includes("library/strategies?")
        ? new Promise<Response>((r) => {
            resolve = r
          })
        : Promise.resolve(
            json({
              ...empty,
              total: 1,
              items: [{ snapshot_id: B, canonical_symbol: "NEW_DATASET" }],
            }),
          ),
    ),
  )
  render(
    <LibraryPanel
      strategy={() => ({})}
      onStrategy={() => {}}
      onSnapshot={() => {}}
      onRun={() => {}}
    />,
  )
  fireEvent.change(screen.getByLabelText("보관함 종류"), { target: { value: "datasets" } })
  await screen.findByText("NEW_DATASET")
  await act(async () =>
    resolve(json({ ...empty, total: 1, items: [{ strategy_id: A, name: "OLD_STRATEGY" }] })),
  )
  expect(screen.queryByText("OLD_STRATEGY")).not.toBeInTheDocument()
  expect(screen.getByRole("button", { name: "snapshot 재사용" })).toBeInTheDocument()
})
it("I1 계좌 선택이 바뀌면 늦은 이전 GET 계좌를 새 선택 밑에 표시하지 않는다", async () => {
  const a = `paper_${"a".repeat(32)}`,
    b = `paper_${"b".repeat(32)}`
  const account = (id: string, cash: string) => ({
    account_id: id,
    name: id,
    cash,
    equity: cash,
    kill_switch: false,
    positions: [],
    orders: [],
    fills: [],
    audit: [],
  })
  let resolve: (value: Response) => void = () => {}
  localStorage.setItem("research-paper", a)
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      String(input).includes("?")
        ? Promise.resolve(
            json({ ...empty, total: 2, items: [account(a, "1000"), account(b, "2000")] }),
          )
        : String(input).endsWith(a)
          ? new Promise<Response>((r) => {
              resolve = r
            })
          : Promise.resolve(json(account(b, "2000"))),
    ),
  )
  render(<PaperPanel />)
  await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(3))
  fireEvent.change(screen.getByLabelText("연습 계좌 선택"), { target: { value: b } })
  expect(screen.queryByTestId("paper-cash")).not.toBeInTheDocument()
  await act(async () => resolve(json(account(a, "1000"))))
  expect(screen.queryByTestId("paper-cash")).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "현재 계좌 조회" }))
  await waitFor(() => expect(screen.getByTestId("paper-cash")).toHaveTextContent("2000"))
})
