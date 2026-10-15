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
        기본 수량·금액·자산 비중·ATR 위험 예산과 손절·익절·추적 손절·세션은 한국어 폼에서
        편집합니다. 중첩 all/any/not 조건은 JSON으로 손실 없이 보존하며 수량·위험·세션 폼은 원본의
        해당 분기만 갱신합니다. 실행·저장·실험은 같은 현재 정의를 사용합니다. 데이터·원금·실행
        비용은 별도 설정입니다.
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
          disabled={busy || Boolean(draft.formError)}
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
          disabled={Boolean(draft.formError)}
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
          고급 JSON 모드 활성 · 중첩 조건은 보존합니다. 수량·위험·세션 폼은 해당 JSON 분기에
          반영됩니다.
        </p>
      )}
    </section>
  )
}
