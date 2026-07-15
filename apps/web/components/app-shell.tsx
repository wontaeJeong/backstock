import type { ReactNode } from "react"

import { StatusBadge } from "./ui"

type AppPath = "/" | "/design-system"

const navigationItems = [
  { href: "/", label: "Foundation" },
  { href: "/design-system", label: "Components" },
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
        <nav lang="en">
          {navigationItems.map(({ href, label }) => (
            <a aria-current={href === currentPath ? "page" : undefined} href={href} key={href}>
              {label}
            </a>
          ))}
        </nav>
        <div className="sidebar__status">
          <StatusBadge label="Paper mode" tone="info" />
          <p>실주문 기능은 비활성화되어 있습니다.</p>
        </div>
      </aside>
      {children}
    </div>
  )
}
