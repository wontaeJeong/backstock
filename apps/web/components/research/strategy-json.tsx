"use client"
import { useState } from "react"
import { api, downloadJson, strategyJson } from "../../lib/features"
import type { Draft } from "../../lib/research"
import { buildStrategy } from "../../lib/research"
import { ActionButton } from "../ui"
import { useOperation } from "./panel-kit"

export function StrategyJson({
  draft,
  onChange,
}: {
  draft: Draft
  onChange: (text: string | undefined) => void
}) {
  const { busy, act, feedback } = useOperation(),
    [notice, setNotice] = useState("")
  let text = draft.advancedJson ?? ""
  if (draft.advancedJson === undefined) {
    try {
      text = JSON.stringify(buildStrategy(draft), null, 2)
    } catch {
      text = "간편 폼 입력을 완성하세요."
    }
  }
  return (
    <section className="editor-section">
      <h3>고급 JSON · 손실 없는 전략 편집</h3>
      {feedback}
      <p role="status">{notice}</p>
      <p className="helper">
        fixed_quantity / fixed_notional / percent_equity / atr_risk, ATR·trailing risk, 중첩
        all/any/not, 요일은 전체 JSON으로 편집할 수 있습니다. JSON 모드에서는 위 간편 전략 폼 대신
        이 정의만 실행·저장·실험에 사용합니다. 데이터·원금·실행 비용은 위 설정을 사용합니다.
      </p>
      <label className="form-field">
        고급 전략 JSON
        <textarea
          rows={12}
          value={text}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
        />
      </label>
      <div className="starter-buttons">
        <ActionButton
          disabled={busy}
          onClick={() =>
            void act(async () => {
              await api("strategies/validate", strategyJson(text))
              setNotice("전략 검증 완료")
            })
          }
        >
          JSON 검증
        </ActionButton>
        <ActionButton
          onClick={() => void act(async () => downloadJson(strategyJson(text), "strategy.json"))}
        >
          전략 JSON 내보내기
        </ActionButton>
        <ActionButton
          onClick={() => {
            onChange(undefined)
            setNotice("간편 폼 정의로 전환했습니다. 이전 JSON은 내보내기로 보존하세요.")
          }}
        >
          간편 폼으로 명시적 전환
        </ActionButton>
      </div>
      <label className="form-field">
        전략 JSON 가져오기
        <input
          type="file"
          accept=".json,application/json"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file)
              void act(async () => {
                if (file.size > 65536) throw new Error("전략 JSON은 64 KiB 이하입니다.")
                const value = strategyJson(await file.text())
                onChange(JSON.stringify(value, null, 2))
                setNotice("JSON 가져오기 완료 · 전체 조건 보존")
              })
          }}
        />
      </label>
      {draft.advancedJson !== undefined && (
        <p className="notice">
          고급 JSON 모드 활성 · 간편 조건·sizing·risk 폼 변경은 이 정의를 덮어쓰지 않습니다.
        </p>
      )}
    </section>
  )
}
