import type { ReactNode } from "react"

import { StatusBadge } from "./ui"

type AppPath = "/" | "/design-system"

const navigationItems = [
  { href: "/", label: "전략 연구실" },
  { href: "/design-system", label: "디자인 구성요소" },
] as const satisfies readonly { readonly href: AppPath; readonly label: string }[]

export function AppShell({
  children,
  currentPath,
}: Readonly<{ children: ReactNode; currentPath: AppPath }>) {
  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="주요 탐색">
        <div className="brand-lockup" lang="en">
          <span className="brand-mark" aria-hidden="true" />
          <span>Stock Strategy Lab</span>
        </div>
        <nav>
          {navigationItems.map(({ href, label }) => (
            <a aria-current={href === currentPath ? "page" : undefined} href={href} key={href}>
              {label}
            </a>
          ))}
        </nav>
        <div className="sidebar__status">
          <StatusBadge label="연구 모드" tone="info" />
          <p>실주문 없음 · 수동 과거 가격 Paper 연습만 제공합니다.</p>
        </div>
      </aside>
      {children}
    </div>
  )
}
