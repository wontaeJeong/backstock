/* biome-ignore-all lint/complexity/useLiteralKeys: TypeScript requires indexed access for full-fidelity strategy JSON. */
import { expect, it } from "vitest"
import {
  allowedResearchPath,
  importDraft,
  numericPaths,
  paperMutation,
  strategyJson,
} from "./features"
import { buildRequest, buildStrategy, defaultDraft } from "./research"

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
