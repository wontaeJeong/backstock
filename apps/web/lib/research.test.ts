import { describe, expect, it } from "vitest"

import { buildStrategy, defaultDraft, simulationReportSchema } from "./research"

describe("코드 없는 전략 작성", () => {
  it("사용자가 고른 지표와 조건을 DSL로 보존한다", () => {
    const draft = defaultDraft()
    draft.symbol = "NVDA"
    draft.interval = "1m"
    draft.allocation = "33.3"
    const rule = draft.entry.rules[0]
    if (!rule) throw new Error("기본 매수 조건이 필요합니다.")
    rule.left.period = "7"
    const strategy = buildStrategy(draft)
    expect(strategy.universe).toEqual(["NASDAQ:NVDA"])
    expect(strategy.timeframe).toBe("1m")
    expect(strategy.position_sizing).toEqual({ method: "percent_equity", percent: "0.333" })
    expect(strategy.entry.condition).toMatchObject({
      op: "all",
      conditions: [{ left: { period: 7 } }],
    })
  })

  it("미래 참조와 잘못된 숫자는 요청 전에 거부한다", () => {
    const draft = defaultDraft()
    const rule = draft.entry.rules[0]
    if (!rule) throw new Error("기본 매수 조건이 필요합니다.")
    rule.left.period = "0"
    expect(() => buildStrategy(draft)).toThrow()
    rule.left.period = "5"
    draft.allocation = "101"
    expect(() => buildStrategy(draft)).toThrow()
  })

  it("비어 있거나 잘못된 결과를 성공으로 표시하지 않는다", () => {
    expect(simulationReportSchema.safeParse({ result: { status: "succeeded" } }).success).toBe(
      false,
    )
  })
})
