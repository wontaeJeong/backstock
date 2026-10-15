import { readFile } from "node:fs/promises"
import { expect, test } from "@playwright/test"

test("비개발자가 규칙을 편집하고 실제 엔진의 합성 실험 결과를 확인한다", async ({ page }, testInfo) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "내 규칙으로, 과거를 검증하다" })).toBeVisible()
  await expect(page.getByText("아직 실행한 시뮬레이션이 없습니다.")).toBeVisible()
  await page.getByLabel("매수 조건 1 기준 기간").fill("7")
  await page.getByRole("button", { name: "합성 데모로 실행" }).click()
  await expect(page.getByRole("heading", { name: "시뮬레이션 결과" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "시뮬레이션 결과" })).toBeInViewport()
  await expect(page.getByText("원금 대비 수익률", { exact: true })).toBeVisible()
  await expect(page.getByText("합성 데이터 · 실제 시세 아님", { exact: true })).toBeVisible()
  await expect(page.getByRole("img", { name: /자산 변화/ })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath("research-result.png"), fullPage: true })
  const metrics = await page.evaluate(() => {
    const main = document.querySelector("main")
    return { width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
      mainHeight: main?.scrollHeight, mainWidth: main?.clientWidth,
      resultTop: document.querySelector("#result-title")?.getBoundingClientRect().top,
      sidebarHeight: document.querySelector(".sidebar")?.getBoundingClientRect().height,
      sidebarTop: document.querySelector(".sidebar")?.getBoundingClientRect().top,
      chartTextSizes: Array.from(document.querySelectorAll("svg text")).map(e => {
        const svg = e.closest("svg")
        return parseFloat(getComputedStyle(e).fontSize) * (svg ? svg.getBoundingClientRect().width / svg.viewBox.baseVal.width : 1)
      }) }
  })
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.width)
  expect(metrics.chartTextSizes.every(size => size >= 14)).toBe(true)
  expect(metrics.mainHeight).toBeLessThan(6000)
  expect(metrics.sidebarTop).toBe(0)
  await testInfo.attach("layout-measurements", { body: JSON.stringify(metrics), contentType: "application/json" })
  await page.locator("summary").filter({ hasText: /^체결 내역/ }).focus()
  await page.keyboard.press("Enter")
  await expect(page.getByRole("region", { name: "체결 내역 가로 스크롤" })).toBeVisible()
  await page.getByLabel("원금 (USD)").fill("20000")
  await expect(page.getByText(/설정이 변경되었습니다/)).toBeVisible()
})

test("업로드한 실제 형식의 분봉을 선택한 규칙으로 시뮬레이션한다", async ({ page }) => {
  await page.goto("/")
  await page.getByLabel("데이터 주기").selectOption("1m")
  await page.getByLabel("데이터 출처").selectOption("snapshot")
  await page.getByLabel("과거 시세 파일 업로드").setInputFiles("apps/web/public/sample-minute-bars.csv")
  await expect(page.getByText(/파일 검증 완료/)).toBeVisible()
  await page.getByRole("button", { name: "직접 조건 만들기" }).click()
  await page.getByRole("button", { name: "시뮬레이션 실행", exact: true }).click()
  await expect(page.getByRole("heading", { name: "시뮬레이션 결과" })).toBeInViewport()
  await expect(page.getByText("사용자 파일 · 시세 출처 미검증")).toBeVisible()
  await expect(page.getByText("1m · 5개 bar · USD")).toBeVisible()
  await expect(page.getByText(/체결 1건 \/ 청산 0건/)).toBeVisible()
})

test("다른 출처의 쓰기 요청과 임의 proxy 경로를 거부한다", async ({ request }) => {
  const crossOrigin = await request.post("/api/research/simulations", { headers: { origin: "https://elsewhere.example" }, data: {} })
  expect(crossOrigin.status()).toBe(403)
  expect((await request.get("/api/research/arbitrary-url")).status()).toBe(404)
})

test("분봉 실험의 한계를 표시하고 결과를 저장한다", async ({ page }) => {
  await page.goto("/")
  await page.getByLabel("데이터 주기").selectOption("1m")
  const reportResponse = page.waitForResponse(response => response.url().endsWith("/api/research/simulations") && response.status() === 201)
  await page.getByRole("button", { name: "합성 데모로 실행" }).click()
  await expect(page.getByText(/호가·스프레드·실제 지연/).first()).toBeVisible()
  await expect(page.getByRole("heading", { name: "시뮬레이션 결과" })).toBeVisible()
  const download = page.waitForEvent("download")
  await page.getByRole("button", { name: "결과 JSON 저장" }).click()
  const artifact = await download
  expect(artifact.suggestedFilename()).toMatch(/^simulation-.*\.json$/)
  const file = await artifact.path()
  if (!file) throw new Error("다운로드 경로가 없습니다.")
  expect(JSON.parse(await readFile(file, "utf8"))).toEqual(await (await reportResponse).json())
})

test("API 실패를 수익률 0이나 데모 성공으로 바꾸지 않는다", async ({ page }) => {
  await page.route("**/api/research/simulations", route => route.fulfill({ status: 502, contentType: "application/json", body: JSON.stringify({ message: "시세 공급자 조회에 실패했습니다." }) }))
  await page.goto("/")
  await page.getByRole("button", { name: "합성 데모로 실행" }).click()
  await expect(page.getByRole("alert").filter({ hasText: "실행하지 못했습니다." })).toContainText("시세 공급자 조회에 실패했습니다.")
  await expect(page.getByLabel("원금 (USD)")).toHaveValue("10000")
  await expect(page.getByRole("heading", { name: "시뮬레이션 결과" })).not.toBeVisible()
})
