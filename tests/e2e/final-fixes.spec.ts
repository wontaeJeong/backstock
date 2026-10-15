import { expect, test } from "@playwright/test"

test("I1 gap trigger and later limit fill retain distinct times through CSV and replay", async ({page}) => {
  await page.goto("/")
  await page.getByLabel("데이터 주기").selectOption("1m")
  await page.getByLabel("데이터 출처").selectOption("snapshot")
  await page.getByLabel("과거 시세 파일 업로드").setInputFiles({name:"gap.csv",mimeType:"text/csv",buffer:Buffer.from("timestamp,open,high,low,close,volume\n2024-01-02T14:31:00Z,100,100,100,100,100\n2024-01-02T14:32:00Z,120,125,100,121,100\n2024-01-02T14:33:00Z,122,122,122,122,100\n")})
  await expect(page.getByText(/파일 검증 완료/)).toBeVisible()
  await page.locator("summary").filter({hasText:"전략 JSON 편집·가져오기"}).click()
  const editor=page.getByLabel("고급 전략 JSON")
  const definition=JSON.parse(await editor.inputValue())
  definition.entry={condition:{op:"gt",left:{type:"bar_field",field:"close",shift:0},right:{type:"constant",value:"0"}}}
  definition.exit={condition:null}
  definition.position_sizing={method:"fixed_quantity",quantity:1}
  definition.risk={stop_loss:null,take_profit:null,trailing_stop:null,max_holding_bars:null}
  definition.order={order_type:"stop_limit",time_in_force:"gtc",stop_offset_bps:"1000",limit_offset_bps:"1500"}
  await editor.fill(JSON.stringify(definition))
  const pending=page.waitForResponse(r=>r.url().endsWith("/api/research/simulations") && r.status()===201)
  await page.getByRole("button",{name:"시뮬레이션 실행",exact:true}).click()
  const report=await(await pending).json()
  expect(report.result.orders[0].triggered_at).toBe("2024-01-02T14:31:00Z")
  expect(report.result.fills[0].timestamp).toBe("2024-01-02T14:32:00Z")
  expect(report.result.fills[0].execution_price).toMatch(/^115(?:\.0+)?$/)
  const csv=await page.request.get(`/api/research/research/runs/${report.run_id}/export.csv?kind=fills`)
  expect(csv.ok()).toBeTruthy()
  expect(await csv.text()).toContain("2024-01-02 14:32:00+00:00")
  await page.getByRole("button",{name:"상세 분석",exact:true}).click()
  const chart=page.getByRole("img",{name:"검증된 snapshot 가격 · USD"})
  await expect(chart).toBeVisible()
  await expect(chart.locator("title").filter({hasText:"매수"})).toHaveText(/2024-01-02T14:32:00Z/)
  await page.getByLabel("재생 bar").fill("2")
  await expect(page.getByText("현재 bar 2",{exact:true})).toBeVisible()
})

for (const imported of [false, true]) test(`I2 ${imported ? "imported" : "simple"} active blank risk blocks all consumers and recovers`, async ({ page }) => {
  await page.goto("/")
  await page.getByLabel("데이터 출처").selectOption("demo")
  await page.locator("summary").filter({ hasText: "전략 JSON 편집·가져오기" }).click()
  if (imported) {
    const text = await page.getByLabel("고급 전략 JSON").inputValue()
    await page.getByLabel("전략 JSON 가져오기").setInputFiles({name:"risk.json",mimeType:"application/json",buffer:Buffer.from(text)})
    await expect(page.getByText("JSON 가져오기 완료 · 전체 조건 보존",{exact:true})).toBeVisible()
  }
  await page.locator("summary").filter({ hasText: "03 · 손절·익절·보유 기간" }).click()
  await page.getByLabel("손절 방식", { exact: true }).selectOption("percent")
  await page.getByLabel("손절 (%)", { exact: true }).fill("")
  const posts: string[] = []
  page.on("request", r => { if (r.method() === "POST") posts.push(r.url()) })
  await page.getByRole("button", { name: "시뮬레이션 실행", exact: true }).click()
  await expect(page.getByRole("alert").filter({ hasText: "실행하지 못했습니다." })).toBeVisible()
  expect(posts).toHaveLength(0)
  const exportButton = page.getByRole("button",{name:"전략 JSON 내보내기",exact:true})
  if (imported) await expect(exportButton).toBeDisabled()
  else {
    await exportButton.click()
    await expect(page.getByRole("alert").filter({hasText:"요청하지 못했습니다."})).toBeVisible()
  }
  await page.getByRole("button",{name:"보관함",exact:true}).click()
  await page.getByRole("button",{name:"현재 전략 저장",exact:true}).click()
  await expect(page.getByRole("alert").filter({hasText:"요청하지 못했습니다."}).first()).toBeVisible()
  expect(posts).toHaveLength(0)
  await page.getByRole("button",{name:"실험",exact:true}).click()
  for (const name of ["Grid 실행", "Walk-forward 실행", "고정 예산 포트폴리오 실행"]) {
    await page.getByRole("button",{name,exact:true}).click()
    await expect(page.getByRole("alert").filter({hasText:"요청하지 못했습니다."}).first()).toBeVisible()
  }
  expect(posts).toHaveLength(0)
  await page.getByRole("button",{name:"전략 편집",exact:true}).click()
  await page.getByLabel("손절 (%)",{exact:true}).fill("8")
  const response = page.waitForResponse(r=>r.url().endsWith("/api/research/simulations") && r.status()===201)
  await page.getByRole("button",{name:"시뮬레이션 실행",exact:true}).click()
  expect((await (await response).json()).request.strategy.risk.stop_loss.value).toBe("8")
  await page.getByLabel("손절 (%)",{exact:true}).fill("")
  await page.getByLabel("손절 방식",{exact:true}).selectOption("off")
  const offResponse = page.waitForResponse(r=>r.url().endsWith("/api/research/simulations") && r.status()===201)
  await page.getByRole("button",{name:"시뮬레이션 실행",exact:true}).click()
  expect((await (await offResponse).json()).request.strategy.risk.stop_loss).toBeNull()
})

test("M1 imported order summary reflects JSON rather than stale defaults", async ({ page }) => {
  await page.goto("/")
  await page.locator("summary").filter({ hasText: "전략 JSON 편집·가져오기" }).click()
  const editor = page.getByLabel("고급 전략 JSON")
  const definition = JSON.parse(await editor.inputValue())
  definition.order = { order_type: "stop_limit", time_in_force: "gtc", stop_offset_bps: "50", limit_offset_bps: "100" }
  await editor.fill(JSON.stringify(definition))
  await page.locator("summary").filter({ hasText: "주문·세션·spread" }).click()
  await expect(page.getByLabel("현재 JSON 주문 설정")).toContainText("stop_limit")
  await expect(page.getByLabel("현재 JSON 주문 설정")).toContainText("gtc")
  await expect(page.getByLabel("현재 JSON 주문 설정")).toContainText("50")
  await expect(page.getByLabel("주문 종류", { exact: true })).toHaveCount(0)
  await editor.fill("{")
  await expect(page.getByLabel("현재 JSON 주문 설정")).toContainText("확인할 수 없습니다")
})
