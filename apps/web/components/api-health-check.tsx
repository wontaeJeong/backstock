"use client"

import ky, { HTTPError, TimeoutError } from "ky"
import { useState } from "react"

import { ActionButton, StatusBadge } from "./ui"

type HealthState =
  | Readonly<{ kind: "idle" }>
  | Readonly<{ kind: "loading" }>
  | Readonly<{ kind: "ready" }>
  | Readonly<{ kind: "error" }>

const initialState = { kind: "idle" } as const satisfies HealthState

function HealthFeedback({ state }: Readonly<{ state: HealthState }>) {
  switch (state.kind) {
    case "idle":
      return null
    case "loading":
      return (
        <span className="health-check__result" role="status">
          <span aria-hidden="true" className="loading-indicator" />
          API 준비 상태를 확인하고 있습니다.
        </span>
      )
    case "ready":
      return (
        <span className="health-check__result" role="status">
          <StatusBadge label="API ready" tone="success" />
          <span>/health/ready 응답 확인</span>
        </span>
      )
    case "error":
      return (
        <span className="health-check__result" role="alert">
          <StatusBadge label="Unavailable" tone="error" />
          <span>상태를 확인하지 못했습니다. 다시 시도하세요.</span>
        </span>
      )
    default: {
      const exhaustiveState: never = state
      return exhaustiveState
    }
  }
}

export function ApiHealthCheck() {
  const [state, setState] = useState<HealthState>(initialState)

  async function checkHealth(): Promise<void> {
    setState({ kind: "loading" })

    try {
      await ky.get("/api/health", { retry: 0, timeout: 3_000 })
      setState({ kind: "ready" })
    } catch (error) {
      if (
        error instanceof HTTPError ||
        error instanceof TimeoutError ||
        error instanceof TypeError
      ) {
        setState({ kind: "error" })
        return
      }
      throw error
    }
  }

  return (
    <div className="health-check">
      <ActionButton
        aria-describedby="health-check-feedback"
        loading={state.kind === "loading"}
        onClick={() => void checkHealth()}
        variant="primary"
      >
        {state.kind === "error" ? "다시 확인" : "API 상태 확인"}
      </ActionButton>
      <div className="health-check__feedback" id="health-check-feedback">
        <HealthFeedback state={state} />
      </div>
    </div>
  )
}
