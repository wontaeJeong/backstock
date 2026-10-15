import { fireEvent, render, screen, within } from "@testing-library/react"
import { expect, it } from "vitest"
import { ValueChart } from "./analysis-panel"
import { Records, Statistics, useOperation } from "./panel-kit"

it("미정의 통계는 0으로 바꾸지 않고 이유와 정의를 제공한다", () => {
  render(
    <Statistics
      value={{
        payoff_ratio: {
          value: null,
          reason: "requires both classes",
          definition: "mean win / mean loss",
        },
      }}
    />,
  )
  expect(screen.getByText("미정의 · requires both classes")).toBeInTheDocument()
  expect(screen.getByText("mean win / mean loss")).toBeInTheDocument()
  expect(screen.getByText("평균 이익/손실 비율")).toBeInTheDocument()
})
it("초기 서버 조회가 필요한 패널은 첫 렌더부터 변경 버튼을 잠근다", () => {
  function InitialPanel() {
    const { busy } = useOperation(true)
    return (
      <button type="button" disabled={busy}>
        초기 조회 대기
      </button>
    )
  }
  render(<InitialPanel />)
  expect(screen.getByRole("button", { name: "초기 조회 대기" })).toBeDisabled()
})
it("가격 재생은 실제 체결 표식과 선택 bar를 연결한다", () => {
  render(
    <ValueChart
      title="원본 가격"
      field="close"
      points={[
        { timestamp: "t1", close: "100" },
        { timestamp: "t2", close: "102" },
      ]}
      markers={[{ fill_id: "f1", timestamp: "t2", side: "buy", execution_price: "103" }]}
      cursor={2}
    />,
  )
  expect(screen.getByText("매수 t2 · 체결가 103")).toBeInTheDocument()
  expect(screen.getByText("선택 bar 2")).toBeInTheDocument()
})
it("상세 목록은 25행씩 원본 전체를 탐색하며 내부 가로 스크롤을 제공한다", () => {
  render(
    <Records
      title="실제 기록"
      items={Array.from({ length: 60 }, (_, index) => ({ index, timestamp: `t${index}` }))}
    />,
  )
  fireEvent.click(screen.getByText("실제 기록 · 60건"))
  const table = screen.getByRole("table", { hidden: true })
  expect(within(table).getAllByRole("row", { hidden: true })).toHaveLength(26)
  fireEvent.click(screen.getByRole("button", { name: "다음 25건", hidden: true }))
  expect(within(table).getByText("t25")).toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "다음 25건", hidden: true }))
  expect(within(table).getAllByRole("row", { hidden: true })).toHaveLength(11)
  expect(within(table).getByText("t59")).toBeInTheDocument()
})
