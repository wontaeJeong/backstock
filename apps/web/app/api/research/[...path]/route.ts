import { NextResponse } from "next/server"

type Context = { params: Promise<{ path: string[] }> }
async function proxy(request: Request, context: Context) {
  const { path } = await context.params
  const pathname = path.join("/")
  const allowed =
    request.method === "GET"
      ? /^(research\/catalog|strategies\/metadata|simulations\/[a-f0-9]{64})$/.test(pathname)
      : ["simulations", "datasets"].includes(pathname)
  if (!allowed) return NextResponse.json({ message: "지원하지 않는 요청입니다." }, { status: 404 })
  const origin = request.headers.get("origin")
  const publicOrigin = `${request.headers.get("x-forwarded-proto") ?? new URL(request.url).protocol.replace(":", "")}://${request.headers.get("host") ?? new URL(request.url).host}`
  if (origin && origin !== publicOrigin)
    return NextResponse.json({ message: "다른 출처의 요청은 허용하지 않습니다." }, { status: 403 })
  const headers = new Headers()
  for (const name of ["content-type", "x-filename"]) {
    const value = request.headers.get(name)
    if (value) headers.set(name, value)
  }
  const { API_INTERNAL_URL: configuredApiUrl } = process.env
  const apiUrl = configuredApiUrl ?? "http://127.0.0.1:8000"
  const target = new URL(`/${pathname}`, apiUrl)
  if (pathname === "datasets") target.search = new URL(request.url).search
  const options: RequestInit & { duplex: "half" } = {
    method: request.method,
    headers,
    body: request.method === "GET" ? null : request.body,
    duplex: "half",
    cache: "no-store",
    signal: AbortSignal.timeout(45_000),
  }
  try {
    const upstream = await fetch(target, options)
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    })
  } catch {
    return NextResponse.json(
      { message: "API에 연결하지 못했습니다. 서버 상태를 확인하고 다시 시도하세요." },
      { status: 503 },
    )
  }
}

export const GET = proxy
export const POST = proxy
