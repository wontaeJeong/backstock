/** Acquisition identity comes from the verified manifest, never the reuse request mode. */
export function provenanceLabel(provider: string): string {
  if (provider === "synthetic_demo") return "합성 데이터 · 실제 시세 아님"
  if (provider === "yfinance") return "Yahoo 과거 시세 · 현재 거래소 가격 아님"
  if (provider === "local_file") return "사용자 파일 · 시세 출처 미검증"
  return `미확인 데이터 공급자 · 출처 미검증 (${provider})`
}
