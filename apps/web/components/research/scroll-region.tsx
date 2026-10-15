import type { ReactNode } from "react"

export function ScrollRegion({
  label,
  className,
  children,
}: {
  label: string
  className: string
  children: ReactNode
}) {
  return (
    // biome-ignore lint/a11y/noNoninteractiveTabindex: Horizontal scroll regions must be keyboard focusable.
    <section className={className} aria-label={label} tabIndex={0}>
      {children}
    </section>
  )
}
