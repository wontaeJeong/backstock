"use client"

import { useId } from "react"
import type { Operand, OperandKind, Rule, RuleGroup } from "../../lib/research"
import { ActionButton } from "../ui"

const fields: { value: OperandKind; label: string }[] = [
  { value: "close", label: "종가" },
  { value: "open", label: "시가" },
  { value: "volume", label: "거래량" },
  { value: "sma", label: "단순 이동평균" },
  { value: "ema", label: "지수 이동평균" },
  { value: "rsi", label: "RSI (상대강도)" },
  { value: "atr", label: "ATR (변동폭)" },
  { value: "volume_ratio", label: "평균 대비 거래량" },
  { value: "return", label: "기간 수익률 (소수)" },
  { value: "constant", label: "직접 입력한 숫자" },
  ...(
    [
      "vwap",
      "bollinger_middle",
      "bollinger_upper",
      "bollinger_lower",
      "macd",
      "macd_signal",
      "macd_histogram",
      "rolling_high",
      "rolling_low",
      "volume_average",
    ] as const
  ).map((value) => ({ value, label: value })),
]
const ops = [
  ["gt", "보다 큼 (>)"],
  ["gte", "이상 (≥)"],
  ["lt", "보다 작음 (<)"],
  ["lte", "이하 (≤)"],
  ["crosses_above", "위로 돌파"],
  ["crosses_below", "아래로 돌파"],
] as const

function ValueEditor({
  label,
  value,
  onChange,
}: {
  label: string
  value: Operand
  onChange: (value: Operand) => void
}) {
  const id = useId()
  const indicator = !["constant", "close", "open", "volume"].includes(value.kind)
  return (
    <div className="rule-value">
      <label htmlFor={`${id}-kind`}>{label}</label>
      <select
        id={`${id}-kind`}
        value={value.kind}
        onChange={(event) => onChange({ ...value, kind: event.target.value as OperandKind })}
      >
        {fields.map((field) => (
          <option key={field.value} value={field.value}>
            {field.label}
          </option>
        ))}
      </select>
      {indicator && !value.kind.startsWith("macd") && (
        <label className="inline-input">
          기간 (bar 수)
          <input
            aria-label={`${label} 기간`}
            type="number"
            min="1"
            max="3000"
            value={value.period}
            onChange={(event) => onChange({ ...value, period: event.target.value })}
            required
          />
        </label>
      )}
      {value.kind.startsWith("macd") &&
        (
          [
            ["fast", "빠른 기간", "12"],
            ["slow", "느린 기간", "26"],
            ["signal", "signal 기간", "9"],
          ] as const
        ).map(([key, title, fallback]) => (
          <label className="inline-input" key={key}>
            {title}
            <input
              aria-label={`${label} ${title}`}
              type="number"
              min="1"
              max="5000"
              value={value[key] ?? fallback}
              onChange={(e) => onChange({ ...value, [key]: e.target.value })}
            />
          </label>
        ))}
      {value.kind.startsWith("bollinger") && (
        <label className="inline-input">
          표준편차 배수
          <input
            aria-label={`${label} 표준편차 배수`}
            value={value.multiplier ?? "2"}
            onChange={(e) => onChange({ ...value, multiplier: e.target.value })}
          />
        </label>
      )}
      {value.kind === "constant" && (
        <label className="inline-input">
          비교 숫자
          <input
            aria-label={`${label} 숫자`}
            type="number"
            step="any"
            value={value.value}
            onChange={(event) => onChange({ ...value, value: event.target.value })}
            required
          />
        </label>
      )}
    </div>
  )
}

export function RuleBuilder({
  title,
  group,
  onChange,
}: {
  title: string
  group: RuleGroup
  onChange: (group: RuleGroup) => void
}) {
  const id = useId()
  const update = (index: number, rule: Rule) =>
    onChange({
      ...group,
      rules: group.rules.map((old, position) => (position === index ? rule : old)),
    })
  return (
    <fieldset className="rule-group">
      <legend>{title}</legend>
      <label htmlFor={`${id}-match`}>조건 결합</label>
      <select
        id={`${id}-match`}
        value={group.match}
        onChange={(event) =>
          onChange({ ...group, match: event.target.value as RuleGroup["match"] })
        }
      >
        <option value="all">모든 조건이 맞으면</option>
        <option value="any">하나라도 맞으면</option>
      </select>
      {group.rules.map((rule, index) => (
        <div className="rule-row" key={rule.id}>
          <div className="rule-row__heading">
            <span>조건 {index + 1}</span>
            <ActionButton
              variant="quiet"
              aria-label={`${title} 조건 ${index + 1} 삭제`}
              onClick={() =>
                onChange({ ...group, rules: group.rules.filter((item) => item.id !== rule.id) })
              }
              disabled={group.rules.length === 1}
            >
              삭제
            </ActionButton>
          </div>
          <ValueEditor
            label={`${title} 조건 ${index + 1} 기준`}
            value={rule.left}
            onChange={(left) => update(index, { ...rule, left })}
          />
          <label htmlFor={`${id}-op-${rule.id}`}>비교 방법</label>
          <select
            id={`${id}-op-${rule.id}`}
            value={rule.op}
            onChange={(event) => update(index, { ...rule, op: event.target.value as Rule["op"] })}
          >
            {ops.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <ValueEditor
            label={`${title} 조건 ${index + 1} 비교 대상`}
            value={rule.right}
            onChange={(right) => update(index, { ...rule, right })}
          />
        </div>
      ))}
      <ActionButton
        disabled={group.rules.length >= 4}
        onClick={() =>
          onChange({
            ...group,
            rules: [
              ...group.rules,
              {
                id: crypto.randomUUID(),
                left: { kind: "close", period: "5", value: "100" },
                op: "gt",
                right: { kind: "constant", period: "5", value: "100" },
              },
            ],
          })
        }
      >
        조건 추가
      </ActionButton>
      <p className="helper">
        기간은 선택한 주기의 bar 개수입니다. 지표 준비 데이터가 부족하면 매매하지 않습니다.
      </p>
    </fieldset>
  )
}
