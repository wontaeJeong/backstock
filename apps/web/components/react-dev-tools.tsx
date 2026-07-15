"use client"

import { useEffect } from "react"

export function ReactDevTools() {
  const { NEXT_PUBLIC_DISABLE_REACT_DEVTOOLS: disableReactDevTools } = process.env

  useEffect(() => {
    if (disableReactDevTools !== "1") {
      void import("react-grab")
      void import("react-scan")
    }
  }, [disableReactDevTools])

  return null
}
