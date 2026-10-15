"use client"
import type { Draft } from "../../lib/research"
import { FormField } from "../ui"
import { Field } from "./panel-kit"
export function SizingControls({
  draft,
  update,
}: {
  draft: Draft
  update: <K extends keyof Draft>(key: K, value: Draft[K]) => void
}) {
  return (
    <section aria-label="한국어 매수 수량 설정">
      {draft.formError && <p className="notice">{draft.formError}</p>}
      <label className="form-field">
        매수 수량 방식
        <select
          aria-label="매수 수량 방식"
          value={draft.sizingMethod}
          onChange={(e) => update("sizingMethod", e.target.value as Draft["sizingMethod"])}
        >
          <option value="percent_equity">평가자산 비중 (%)</option>
          <option value="fixed_quantity">고정 주식 수량</option>
          <option value="fixed_notional">고정 투자 금액 (USD)</option>
          <option value="atr_risk">ATR 위험 예산</option>
        </select>
      </label>
      {draft.sizingMethod === "percent_equity" && (
        <FormField
          id="allocation"
          label="매수 시 자산 사용 비중 (%)"
          type="number"
          min="0.01"
          max="100"
          step="any"
          value={draft.allocation}
          onChange={(e) => update("allocation", e.target.value)}
          helper="다음 시가 상승·비용으로 현금이 부족하면 주문이 거절될 수 있습니다."
          required
        />
      )}
      {draft.sizingMethod === "fixed_quantity" && (
        <Field
          label="고정 매수 수량 (주)"
          value={draft.quantity}
          onChange={(v) => update("quantity", v)}
        />
      )}
      {draft.sizingMethod === "fixed_notional" && (
        <Field
          label="고정 투자 금액 (USD)"
          value={draft.notional}
          onChange={(v) => update("notional", v)}
        />
      )}
      {draft.sizingMethod === "atr_risk" && (
        <>
          <Field
            label="거래당 위험 예산 (%)"
            value={draft.riskPercent}
            onChange={(v) => update("riskPercent", v)}
          />
          <Field
            label="수량 계산 ATR 기간 (bar)"
            value={draft.sizingAtrPeriod}
            onChange={(v) => update("sizingAtrPeriod", v)}
          />
          <Field
            label="수량 계산 ATR 배수"
            value={draft.sizingAtrMultiple}
            onChange={(v) => update("sizingAtrMultiple", v)}
          />
        </>
      )}
      <p className="helper">
        수량은 서버가 계산합니다. 정수 수량·현금·비용 제한을 적용하며 위험 예산은 손실 상한 보장이
        아닙니다.
      </p>
    </section>
  )
}
