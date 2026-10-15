"use client"
import type { Draft, RiskMode } from "../../lib/research"
import { Field } from "./panel-kit"
export function RiskControls({
  draft,
  update,
}: {
  draft: Draft
  update: <K extends keyof Draft>(key: K, value: Draft[K]) => void
}) {
  return (
    <details className="editor-section editor-disclosure">
      <summary>03 · 손절·익절·보유 기간</summary>
      {(
        [
          { title: "손절", mode: "stopLossMode", value: "stopLoss", period: "stopLossPeriod" },
          {
            title: "익절",
            mode: "takeProfitMode",
            value: "takeProfit",
            period: "takeProfitPeriod",
          },
          {
            title: "추적 손절",
            mode: "trailingMode",
            value: "trailingStop",
            period: "trailingPeriod",
          },
        ] as const
      ).map((rule) => (
        <div key={rule.mode} className="form-grid">
          <label className="form-field">
            {rule.title} 방식
            <select
              aria-label={`${rule.title} 방식`}
              value={draft[rule.mode]}
              onChange={(e) => update(rule.mode, e.target.value as RiskMode)}
            >
              <option value="off">사용 안 함</option>
              <option value="percent">비율 (%)</option>
              <option value="atr_multiple">ATR 배수</option>
            </select>
          </label>
          {draft[rule.mode] !== "off" && (
            <>
              <Field
                label={`${rule.title} ${draft[rule.mode] === "percent" ? "(%)" : "ATR 배수"}`}
                value={draft[rule.value]}
                onChange={(v) => update(rule.value, v)}
              />
              {draft[rule.mode] === "atr_multiple" && (
                <Field
                  label={`${rule.title} ATR 기간 (bar)`}
                  value={draft[rule.period]}
                  onChange={(v) => update(rule.period, v)}
                />
              )}
            </>
          )}
        </div>
      ))}
      <Field
        label="최대 보유 bar 수"
        value={draft.holdingBars}
        onChange={(v) => update("holdingBars", v)}
      />
      <p className="helper">
        최대 보유 bar 수만 비우면 기간 제한 없음. 활성 위험 값·ATR 기간은 필수이며 위험 해제는 ‘사용
        안 함’을 선택하세요. 손절·익절·추적 손절은 종가 조건이며 다음 eligible 이벤트에서만
        체결합니다. ATR 배수와 기간은 서버 계산에 모두 적용합니다.
      </p>
    </details>
  )
}
