import ky, { HTTPError, TimeoutError } from "ky"
import { NextResponse } from "next/server"
import { ZodError, z } from "zod"

const healthResponseSchema = z.object({ status: z.literal("ready") })
const { NEXT_PUBLIC_API_URL: configuredApiUrl } = process.env
const apiUrl = configuredApiUrl ?? "http://localhost:8000"

export async function GET() {
  try {
    const response = await ky
      .get(`${apiUrl}/health/ready`, { retry: 0, timeout: 3_000 })
      .json<unknown>()
    return NextResponse.json(healthResponseSchema.parse(response))
  } catch (error) {
    if (
      error instanceof HTTPError ||
      error instanceof TimeoutError ||
      error instanceof TypeError ||
      error instanceof ZodError
    ) {
      return NextResponse.json({ status: "unavailable" }, { status: 503 })
    }
    throw error
  }
}
