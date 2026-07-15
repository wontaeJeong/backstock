import "@fontsource/fira-code/latin-400.css"
import "@fontsource/fira-code/latin-600.css"
import "@fontsource/fira-sans/latin-400.css"
import "@fontsource/fira-sans/latin-600.css"
import type { Metadata } from "next"
import type { ReactNode } from "react"

import { ReactDevTools } from "../components/react-dev-tools"
import "./globals.css"

export const metadata: Metadata = {
  title: "Stock Strategy Lab",
  description: "Reproducible stock strategy research and paper-trading workspace",
}

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ko">
      <body>
        <a className="skip-link" href="#main-content">
          본문으로 건너뛰기
        </a>
        {process.env.NODE_ENV === "development" && <ReactDevTools />}
        {children}
      </body>
    </html>
  )
}
