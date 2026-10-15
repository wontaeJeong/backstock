/* biome-ignore-all lint/complexity/useLiteralKeys: TypeScript requires indexed access for full-fidelity strategy JSON. */
import { expect, it } from "vitest"
import {
  allowedResearchPath,
  importDraft,
  numericPaths,
  paperMutation,
  strategyJson,
} from "./features"
import { provenanceLabel } from "./provenance"
import { buildRequest, buildStrategy, defaultDraft } from "./research"
import { updateDraftSetting } from "./strategy-form"

it("I4 출처는 snapshot 재사용 방식이 아니라 원래 provider로 구분한다", () => {
  expect(provenanceLabel("yfinance")).toContain("Yahoo")
  expect(provenanceLabel("local_file")).toContain("사용자 파일")
  expect(provenanceLabel("unknown_private_provider")).not.toContain("Yahoo")
  expect(provenanceLabel("unknown_private_provider")).toContain("미확인")
})
it("I2 고정 수량·금액·ATR 예산과 ATR/trailing 위험을 폼 요청으로 만든다", () => {
  const base = {
    ...defaultDraft(),
    sizingMethod: "fixed_quantity" as const,
    quantity: "2",
    notional: "500.00000001",
    riskPercent: "1.25",
    sizingAtrPeriod: "17",
    sizingAtrMultiple: "2.123456789012",
    stopLossMode: "atr_multiple" as const,
    stopLoss: "2.5",
    stopLossPeriod: "19",
    takeProfitMode: "atr_multiple" as const,
    takeProfit: "4.5",
    takeProfitPeriod: "21",
    trailingMode: "atr_multiple" as const,
    trailingStop: "3.25",
    trailingPeriod: "23",
  }
  expect(buildStrategy(base).position_sizing).toEqual({ method: "fixed_quantity", quantity: 2 })
  expect(buildStrategy({ ...base, sizingMethod: "fixed_notional" }).position_sizing).toEqual({
    method: "fixed_notional",
    notional: "500.00000001",
  })
  expect(buildStrategy({ ...base, sizingMethod: "atr_risk" }).position_sizing).toEqual({
    method: "atr_risk",
    risk_percent: "0.0125",
    atr_period: 17,
    atr_multiple: "2.123456789012",
  })
  expect(buildStrategy(base)["risk"]).toMatchObject({
    stop_loss: { mode: "atr_multiple", value: "2.5", atr_period: 19 },
    take_profit: { mode: "atr_multiple", value: "4.5", atr_period: 21 },
    trailing_stop: { mode: "atr_multiple", value: "3.25", atr_period: 23 },
  })
  expect(() =>
    buildStrategy({ ...base, stopLossMode: "percent", stopLossPeriod: "" }),
  ).not.toThrow()
  expect(() =>
    buildStrategy({ ...base, stopLossMode: "atr_multiple", stopLossPeriod: "" }),
  ).toThrow()
})
it("I2 중첩 정의의 sizing/risk 폼 편집은 나머지 AST·세션·Decimal을 보존한다", () => {
  const original = {
    ...buildStrategy(defaultDraft()),
    entry: {
      condition: {
        op: "not",
        condition: {
          op: "gt",
          left: { type: "bar_field", field: "close" },
          right: { type: "constant", value: "100.000000000001" },
        },
      },
    },
    position_sizing: { method: "fixed_notional", notional: "500.00000001" },
    risk: {
      stop_loss: { mode: "atr_multiple", value: "2.000000000001", atr_period: 19 },
      trailing_stop: { mode: "percent", value: "5.000000000001", atr_period: 17 },
    },
    session: { weekdays: [1, 3], entry_start: "09:40", entry_end: "15:00", flatten_at: "15:50" },
  }
  const imported = importDraft(defaultDraft(), JSON.stringify(original))
  expect(imported.sizingMethod).toBe("fixed_notional")
  expect(imported.notional).toBe("500.00000001")
  expect(imported.stopLossPeriod).toBe("19")
  expect(buildStrategy(imported)).toEqual(original)
  const changed = buildStrategy(updateDraftSetting(imported, "notional", "600.00000001"))
  expect(changed.entry).toEqual(original.entry)
  expect(changed["session"]).toEqual(original.session)
  expect(changed["risk"]).toEqual(original.risk)
  expect(changed.position_sizing).toEqual({ method: "fixed_notional", notional: "600.00000001" })
  expect(buildStrategy(updateDraftSetting(imported, "weekdays", [0, 4]))["session"]).toEqual({
    ...original.session,
    weekdays: [0, 4],
  })
  expect(() => buildStrategy(updateDraftSetting(imported, "notional", ""))).toThrow()
})

it("tick execution options and actual MACD parameters reach request", () => {
  const draft = {
    ...defaultDraft(),
    interval: "tick" as const,
    source: "demo" as const,
    spread: "12",
    latency: "50",
    participation: "0.2",
    orderType: "stop_limit" as const,
    limitOffset: "10",
    stopOffset: "5",
    entryStart: "09:35",
    entryEnd: "15:00",
    flattenAt: "15:55",
  }
  const first = draft.entry.rules[0]
  if (!first) throw new Error("missing default rule")
  first.left = {
    kind: "macd_signal",
    period: "999",
    value: "0",
    fast: "3",
    slow: "8",
    signal: "4",
  }
  const request = buildRequest(draft)
  expect(request).toMatchObject({ spread_bps: "12", latency_ms: 50, volume_participation: "0.2" })
  expect(request.strategy).toMatchObject({
    order: { order_type: "stop_limit", limit_offset_bps: "10", stop_offset_bps: "5" },
    session: { entry_start: "09:35", flatten_at: "15:55" },
  })
  expect(JSON.stringify(request.strategy)).toContain('"fast_period":3')
  expect(numericPaths(request)).toContain("strategy.entry.condition.conditions.0.left.fast_period")
  expect(numericPaths(request)).not.toContain("strategy.entry.condition.conditions.0.left.period")
})
it("비용·위험 Decimal 입력 문자열을 부동소수점으로 다시 직렬화하지 않는다", () => {
  const value = "0.10000000000000001"
  const draft = { ...defaultDraft(), spread: value, stopLoss: value }
  expect(buildRequest(draft).spread_bps).toBe(value)
  expect(buildStrategy(draft)["risk"]).toMatchObject({ stop_loss: { value } })
})

it("advanced JSON remains lossless and never falls back to generated form", () => {
  const draft = defaultDraft()
  const original = {
    ...buildStrategy(draft),
    position_sizing: {
      method: "atr_risk",
      risk_percent: "0.02",
      atr_period: 14,
      atr_multiple: "2",
    },
    entry: {
      condition: {
        op: "not",
        condition: {
          op: "gt",
          left: { type: "bar_field", field: "close" },
          right: { type: "constant", value: "50" },
        },
      },
    },
  }
  const json = JSON.stringify(original)
  expect(strategyJson(json)).toEqual(original)
  expect(buildRequest({ ...draft, advancedJson: json }).strategy).toEqual(original)
  expect(() => buildRequest({ ...draft, advancedJson: "{" })).toThrow()
})
it("불러온 전략의 종목·주기는 실행 데이터 설정과 함께 전환하고 불완전 편집은 유지한다", () => {
  const draft = defaultDraft()
  const text = JSON.stringify({
    ...buildStrategy(draft),
    universe: ["NASDAQ:TSLA"],
    timeframe: "tick",
  })
  const imported = importDraft(draft, text)
  expect(imported.symbol).toBe("TSLA")
  expect(imported.interval).toBe("tick")
  expect(importDraft(imported, "{").advancedJson).toBe("{")
  expect(importDraft(imported, "{").symbol).toBe("TSLA")
})

it("proxy permits exact methods and denies arbitrary paths", () => {
  expect(allowedResearchPath("GET", `research/datasets/${"a".repeat(64)}/bars`)).toBe(true)
  expect(allowedResearchPath("POST", `paper/accounts/paper_${"a".repeat(32)}/quotes`)).toBe(true)
  expect(allowedResearchPath("POST", "research/library/runs")).toBe(false)
  expect(allowedResearchPath("GET", "https://example.com")).toBe(false)
})

it("paper POST failure and historical success always read current account", async () => {
  for (const fail of [true, false]) {
    const calls: string[] = []
    const fetcher = async (_path: string, init?: RequestInit) => {
      calls.push(init?.method ?? "GET")
      return new Response(JSON.stringify(init?.method ? { message: "old" } : { cash: "123" }), {
        status: init?.method && fail ? 409 : 200,
      })
    }
    let current: unknown
    try {
      await paperMutation(
        "paper_x",
        "quotes",
        {},
        (value) => {
          current = value
        },
        fetcher,
      )
    } catch {
      /* denial expected */
    }
    expect(calls).toEqual(["POST", "GET"])
    expect(current).toEqual({ cash: "123" })
  }
})
