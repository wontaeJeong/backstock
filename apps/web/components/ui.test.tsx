import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AppShell } from "./app-shell"
import { ActionButton, FormField, StatusBadge } from "./ui"

describe("ActionButton", () => {
  it("disables submission while loading", () => {
    // Given
    render(<ActionButton loading>Run backtest</ActionButton>)

    // When
    const button = screen.getByRole("button", { name: "처리 중" })

    // Then
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute("aria-busy", "true")
  })
})

describe("StatusBadge", () => {
  it("exposes status as text instead of color alone", () => {
    // Given
    render(<StatusBadge label="Valid with warnings" tone="warning" />)

    // When
    const status = screen.getByText("Valid with warnings")

    // Then
    expect(status).toBeVisible()
  })
})

describe("FormField", () => {
  it("connects validation guidance to the invalid control", () => {
    // Given
    render(<FormField id="period" label="기간" error="기간을 확인하세요." />)

    // When
    const field = screen.getByRole("textbox", { name: "기간" })

    // Then
    expect(field).toHaveAttribute("aria-invalid", "true")
    expect(field).toHaveAccessibleDescription("기간을 확인하세요.")
  })
})

describe("AppShell", () => {
  it("exposes the current route in shared navigation", () => {
    // Given
    render(
      <AppShell currentPath="/design-system">
        <main>Showcase</main>
      </AppShell>,
    )

    // When
    const currentLink = screen.getByRole("link", { name: "Components" })

    // Then
    expect(currentLink).toHaveAttribute("aria-current", "page")
  })
})
