"use client"
import type { Draft } from "../../lib/research"
import { Field } from "./panel-kit"
export function ExecutionControls({
  draft,
  update,
}: {
  draft: Draft
  update: <K extends keyof Draft>(key: K, value: Draft[K]) => void
}) {
  return (
    <details className="editor-section editor-disclosure">
      <summary>주문·세션·spread·latency·거래량 제한</summary>
      <div className="form-grid">
        <label className="form-field">
          주문 종류
          <select
            aria-label="주문 종류"
            disabled={draft.advancedJson !== undefined}
            value={draft.orderType}
            onChange={(e) => update("orderType", e.target.value as Draft["orderType"])}
          >
            {["market", "limit", "stop", "stop_limit"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label className="form-field">
          주문 유효기간
          <select
            disabled={draft.advancedJson !== undefined}
            value={draft.tif}
            onChange={(e) => update("tif", e.target.value as Draft["tif"])}
          >
            <option value="day">DAY</option>
            <option value="gtc">GTC</option>
          </select>
        </label>
        {["limit", "stop_limit"].includes(draft.orderType) && (
          <Field
            label="지정가 offset (bps)"
            disabled={draft.advancedJson !== undefined}
            value={draft.limitOffset}
            onChange={(v) => update("limitOffset", v)}
          />
        )}
        {["stop", "stop_limit"].includes(draft.orderType) && (
          <Field
            label="stop offset (bps)"
            disabled={draft.advancedJson !== undefined}
            value={draft.stopOffset}
            onChange={(v) => update("stopOffset", v)}
          />
        )}
        <Field
          label="전체 spread (bps)"
          value={draft.spread}
          onChange={(v) => update("spread", v)}
        />
        <Field
          label="체결 지연 (ms)"
          value={draft.latency}
          onChange={(v) => update("latency", v)}
        />
        <Field
          label="거래량 참여율 (0 초과 1 이하, 비우면 무제한)"
          value={draft.participation}
          onChange={(v) => update("participation", v)}
        />
        {draft.interval !== "1d" && (
          <>
            <Field
              label="뉴욕 진입 시작 (HH:MM)"
              value={draft.entryStart}
              onChange={(v) => update("entryStart", v)}
            />
            <Field
              label="뉴욕 진입 종료 (HH:MM)"
              value={draft.entryEnd}
              onChange={(v) => update("entryEnd", v)}
            />
            <Field
              label="뉴욕 마감 청산 신호 (HH:MM)"
              value={draft.flattenAt}
              onChange={(v) => update("flattenAt", v)}
            />
          </>
        )}
      </div>
      <fieldset className="editor-fieldset">
        <legend>뉴욕 진입 요일</legend>
        {["월", "화", "수", "목", "금"].map((label, index) => (
          <label key={label}>
            <input
              type="checkbox"
              checked={draft.weekdays.includes(index)}
              onChange={(e) =>
                update(
                  "weekdays",
                  e.target.checked
                    ? [...draft.weekdays, index].sort()
                    : draft.weekdays.filter((v) => v !== index),
                )
              }
            />
            {label}
          </label>
        ))}
      </fieldset>
      <p className="helper">
        quote가 있으면 bid/ask를 사용하고 spread를 중복 적용하지 않습니다. latency는 다음 eligible
        이벤트/open까지 올림, 거래량은 전량 또는 미체결 시나리오입니다. 마감 청산도 다음 이벤트가
        없어 미체결될 수 있습니다. 실시간 호가·부분 체결·queue는 없습니다.
      </p>
    </details>
  )
}
