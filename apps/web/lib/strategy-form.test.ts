/* biome-ignore-all lint/complexity/useLiteralKeys: Imported strategy protocol keys are preserved verbatim. */
import { expect, it } from "vitest"
import { importDraft } from "./features"
import { buildRequest, buildStrategy, type Draft, defaultDraft } from "./research"
import { updateDraftSetting } from "./strategy-form"

function originalDefinition() {
  return {
    ...buildStrategy(defaultDraft()),
    timeframe: "1m",
    entry: {
      condition: {
        op: "not",
        condition: {
          op: "lt",
          left: { type: "bar_field", field: "close", shift: 0 },
          right: { type: "constant", value: "0.000000000001" },
        },
      },
    },
    position_sizing: { method: "fixed_notional", notional: "500.00000001" },
    risk: {
      stop_loss: { mode: "percent", value: "3", atr_period: 14 },
      take_profit: { mode: "percent", value: "12.000000000001", atr_period: 17 },
      trailing_stop: null,
      max_holding_bars: null,
    },
    session: {
      entry_start: "09:30",
      entry_end: "15:00",
      flatten_at: "15:50",
      weekdays: [0, 1, 2, 3, 4],
    },
  }
}
function imported() {
  return importDraft({ ...defaultDraft(), source: "demo" }, JSON.stringify(originalDefinition()))
}
function assertCurrentDefinition(draft: Draft) {
  expect(draft.formError).toBeUndefined()
  const current = JSON.parse(draft.advancedJson ?? "null")
  expect(buildStrategy(draft)).toEqual(current) // save reads buildStrategy
  expect(buildRequest(draft).strategy).toEqual(current) // simulation and experiment base read buildRequest
  expect(current.entry).toEqual(originalDefinition().entry)
  expect(current["order"]).toEqual(buildStrategy(defaultDraft())["order"])
  return current
}

it("R1 sizing 미완성 중 위험·요일 편집을 금액 복구 후 모두 실행한다", () => {
  let draft = updateDraftSetting(imported(), "notional", "")
  expect(() => buildRequest(draft)).toThrow()
  draft = updateDraftSetting(draft, "stopLoss", "9")
  draft = updateDraftSetting(draft, "weekdays", [1, 2, 4])
  expect(() => buildStrategy(draft)).toThrow()
  draft = updateDraftSetting(draft, "notional", "600.00000001")
  const current = assertCurrentDefinition(draft)
  expect(current.position_sizing).toEqual({ method: "fixed_notional", notional: "600.00000001" })
  expect(current.risk).toEqual({
    ...originalDefinition().risk,
    stop_loss: { mode: "percent", value: "9", atr_period: 14 },
  })
  expect(current.session).toEqual({ ...originalDefinition().session, weekdays: [1, 2, 4] })
})

const edits: {
  key: keyof Draft
  value: Draft[keyof Draft]
  check: (definition: ReturnType<typeof originalDefinition>) => void
}[] = [
  {
    key: "takeProfit",
    value: "19.000000000001",
    check: (current) => expect(current.risk.take_profit.value).toBe("19.000000000001"),
  },
  {
    key: "trailingMode",
    value: "percent",
    check: (current) =>
      expect(current.risk.trailing_stop).toMatchObject({ mode: "percent", value: "3" }),
  },
  {
    key: "holdingBars",
    value: "7",
    check: (current) => expect(current.risk.max_holding_bars).toBe(7),
  },
  {
    key: "entryStart",
    value: "09:45",
    check: (current) => expect(current.session.entry_start).toBe("09:45"),
  },
  {
    key: "entryEnd",
    value: "14:45",
    check: (current) => expect(current.session.entry_end).toBe("14:45"),
  },
  {
    key: "flattenAt",
    value: "15:45",
    check: (current) => expect(current.session.flatten_at).toBe("15:45"),
  },
]
for (const edit of edits)
  it(`R1 무효 sizing 중 ${edit.key} 분기도 복구 후 보존한다`, () => {
    let draft = updateDraftSetting(imported(), "notional", "")
    draft = updateDraftSetting(draft, edit.key, edit.value)
    expect(() => buildRequest(draft)).toThrow()
    draft = updateDraftSetting(draft, "notional", "600")
    const current = assertCurrentDefinition(draft)
    edit.check(current)
    expect(current.risk.stop_loss).toEqual(originalDefinition().risk.stop_loss)
  })

for (const invalidRisk of ["stopLoss", "takeProfit", "trailingStop"] as const) {
  for (const method of [
    "fixed_quantity",
    "fixed_notional",
    "percent_equity",
    "atr_risk",
  ] as const) {
    it(`R1 ${invalidRisk} 미완성 중 ${method}·세션 편집을 위험 복구 후 적용한다`, () => {
      let draft = imported()
      if (invalidRisk === "trailingStop")
        draft = updateDraftSetting(draft, "trailingMode", "percent")
      draft = updateDraftSetting(draft, invalidRisk, "invalid")
      draft = updateDraftSetting(draft, "sizingMethod", method)
      draft = updateDraftSetting(draft, "quantity", "7")
      draft = updateDraftSetting(draft, "notional", "700.00000001")
      draft = updateDraftSetting(draft, "allocation", "33.333333333333")
      draft = updateDraftSetting(draft, "riskPercent", "1.234567890123")
      draft = updateDraftSetting(draft, "sizingAtrPeriod", "19")
      draft = updateDraftSetting(draft, "sizingAtrMultiple", "2.000000000001")
      draft = updateDraftSetting(draft, "entryStart", "09:45")
      draft = updateDraftSetting(draft, "weekdays", [1, 4])
      expect(() => buildRequest(draft)).toThrow()
      draft = updateDraftSetting(draft, invalidRisk, "8.000000000001")
      const current = assertCurrentDefinition(draft)
      const expected = {
        fixed_quantity: { method, quantity: 7 },
        fixed_notional: { method, notional: "700.00000001" },
        percent_equity: { method, percent: "0.33333333333333" },
        atr_risk: {
          method,
          risk_percent: "0.01234567890123",
          atr_period: 19,
          atr_multiple: "2.000000000001",
        },
      }[method]
      expect(current.position_sizing).toEqual(expected)
      expect(current.session).toEqual({
        ...originalDefinition().session,
        entry_start: "09:45",
        weekdays: [1, 4],
      })
      const riskKey = {
        stopLoss: "stop_loss",
        takeProfit: "take_profit",
        trailingStop: "trailing_stop",
      }[invalidRisk]
      expect(current.risk[riskKey].value).toBe("8.000000000001")
      if (invalidRisk !== "takeProfit")
        expect(current.risk.take_profit).toEqual(originalDefinition().risk.take_profit)
    })
  }
}
