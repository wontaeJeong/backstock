import { expect, test } from "@playwright/test"

test("I2 한국어 수량·금액·ATR 및 위험 폼이 실제 실행과 import에 반영된다",async({page},info)=>{
  await page.goto("/")
  await page.getByLabel("데이터 출처").selectOption("demo")
  await page.locator("summary").filter({hasText:"03 · 손절·익절·보유 기간"}).click()
  for(const title of ["손절","익절","추적 손절"]){await page.getByLabel(`${title} 방식`,{exact:true}).selectOption("atr_multiple");await page.getByLabel(`${title} ATR 배수`,{exact:true}).fill(title==="익절" ? "4.5" : "2.000000000001");await page.getByLabel(`${title} ATR 기간 (bar)`,{exact:true}).fill(title==="익절" ? "4" : "3")}
  let last:Record<string,unknown>={}
  for(const method of ["fixed_quantity","fixed_notional","atr_risk","percent_equity"]){
    await page.getByLabel("매수 수량 방식",{exact:true}).selectOption(method)
    if(method==="fixed_quantity")await page.getByLabel("고정 매수 수량 (주)").fill("2")
    if(method==="fixed_notional")await page.getByLabel("고정 투자 금액 (USD)",{exact:true}).fill("500.00000001")
    if(method==="atr_risk"){await page.getByLabel("거래당 위험 예산 (%)").fill("1.25");await page.getByLabel("수량 계산 ATR 기간 (bar)").fill("3");await page.getByLabel("수량 계산 ATR 배수").fill("2.123456789012")}
    if(method==="percent_equity")await page.getByLabel("매수 시 자산 사용 비중 (%)").fill("33.33333333")
    const response=page.waitForResponse(r=>r.url().endsWith("/api/research/simulations") && r.status()===201)
    await page.getByRole("button",{name:"시뮬레이션 실행",exact:true}).click()
    const result=await(await response).json();last=result.request.strategy
    expect(last.position_sizing).toMatchObject({method})
    if(method==="fixed_quantity")expect(last.position_sizing).toMatchObject({quantity:2})
    if(method==="fixed_notional")expect(last.position_sizing).toMatchObject({notional:"500.00000001"})
    if(method==="atr_risk")expect(last.position_sizing).toMatchObject({risk_percent:"0.0125",atr_period:3,atr_multiple:"2.123456789012"})
    if(method==="percent_equity")expect(last.position_sizing).toMatchObject({percent:"0.3333333333"})
    expect(last.risk).toMatchObject({stop_loss:{mode:"atr_multiple",value:"2.000000000001",atr_period:3},take_profit:{mode:"atr_multiple",value:"4.5",atr_period:4},trailing_stop:{mode:"atr_multiple",value:"2.000000000001",atr_period:3}})
  }
  await page.locator("summary").filter({hasText:"전략 JSON 편집·가져오기"}).click()
  await page.getByLabel("전략 JSON 가져오기").setInputFiles({name:"roundtrip.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(last))})
  await expect(page.getByText("JSON 가져오기 완료 · 전체 조건 보존",{exact:true})).toBeVisible()
  await expect(page.getByLabel("매수 수량 방식",{exact:true})).toHaveValue("percent_equity")
  await expect(page.getByLabel("매수 시 자산 사용 비중 (%)")).toBeEnabled()
  await page.getByLabel("매수 수량 방식",{exact:true}).selectOption("fixed_notional")
  await page.getByLabel("고정 투자 금액 (USD)",{exact:true}).fill("600.00000001")
  const edited=JSON.parse(await page.getByLabel("고급 전략 JSON").inputValue())
  expect(edited.entry).toEqual(last.entry);expect(edited.risk).toEqual(last.risk)
  expect(edited.position_sizing).toEqual({method:"fixed_notional",notional:"600.00000001"})
  const layout=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,mainHeight:document.querySelector("main")?.scrollHeight,formFonts:[...document.querySelectorAll('#strategy-editor input:not([type="checkbox"]):not([type="file"]),#strategy-editor select')].filter(e=>e.getBoundingClientRect().width>0).map(e=>parseFloat(getComputedStyle(e).fontSize))}))
  expect(layout.scrollWidth).toBeLessThanOrEqual(layout.width);expect(layout.formFonts.every(n=>n>=14)).toBe(true)
  console.log("REVIEW_FORM_LAYOUT",JSON.stringify(layout));await info.attach("review-form-layout",{body:JSON.stringify(layout),contentType:"application/json"})
  await page.screenshot({path:info.outputPath("sizing-risk-controls.png"),fullPage:true})
})

test("M1 명시적 Enter 검색 중에도 타이핑이 보존되고 글자별 GET은 없다",async({page})=>{
  const queries:string[]=[]
  let release:()=>void=()=>{}
  await page.route("**/api/research/research/library/strategies?**",async route=>{
    const q=new URL(route.request().url()).searchParams.get("q")??"";queries.push(q)
    const response=await route.fetch()
    if(q==="Tesla")await new Promise<void>(resolve=>{release=resolve})
    await route.fulfill({response})
  })
  await page.goto("/")
  await page.getByRole("button",{name:"보관함",exact:true}).click()
  await expect(page.getByRole("button",{name:"현재 전략 저장",exact:true})).toBeEnabled()
  await page.getByLabel("보관함 검색").pressSequentially("Tesla",{delay:30})
  expect(queries).toEqual([""])
  await page.getByLabel("보관함 검색").press("Enter")
  await expect.poll(()=>queries).toEqual(["","Tesla"])
  await expect(page.getByLabel("보관함 검색")).toBeEnabled()
  await page.getByLabel("보관함 검색").pressSequentially("X",{delay:30})
  await expect(page.getByLabel("보관함 검색")).toHaveValue("TeslaX")
  release()
  await expect(page.getByRole("button",{name:"현재 전략 저장",exact:true})).toBeEnabled()
  expect(queries).toEqual(["","Tesla"])
  await page.getByRole("button",{name:"검색",exact:true}).click()
  await expect.poll(()=>queries).toEqual(["","Tesla","TeslaX"])
})

test("I3 실제 26번째 이전 후보를 kill 상태에서 취소하고 현재 GET으로 확인한다",async({page},info)=>{
  const root="/api/research/paper/accounts"
  const created=await page.request.post(root,{data:{name:"26개 후보 회귀",initial_cash:"1000"}})
  expect(created.status()).toBe(201)
  const account=await created.json();let oldest=""
  for(let i=0;i<26;i++){const response=await page.request.post(`${root}/${account.account_id}/proposals`,{data:{symbol:"AAPL",side:"buy",quantity:1,reference_price:"100",quote_at:"2024-01-02T15:00:00Z",idempotency_key:`candidate-${i}`}});expect(response.status()).toBe(200);if(i===0)oldest=(await response.json()).orders[0].order_id}
  expect((await page.request.post(`${root}/${account.account_id}/kill-switch`,{data:{enabled:true,idempotency_key:"kill-on"}})).status()).toBe(200)
  await page.addInitScript(id=>localStorage.setItem("research-paper",id),account.account_id)
  await page.goto("/")
  await page.getByRole("button",{name:"Paper 연습",exact:true}).click()
  await expect(page.getByText("Kill switch: ON",{exact:true})).toBeVisible()
  await page.getByLabel("주문 후보 검색",{exact:false}).fill("pending_approval")
  const list=page.getByRole("list",{name:"작업 가능한 주문 후보"})
  await expect(list.locator("li")).toHaveCount(25)
  await page.getByRole("button",{name:"후보 다음 25개",exact:true}).click()
  const row=list.locator(`[data-order-id="${oldest}"]`)
  await expect(row).toBeVisible()
  const calls:string[]=[]
  page.on("request",r=>{if(r.url().includes(account.account_id))calls.push(r.method()+" "+new URL(r.url()).pathname)})
  await row.getByRole("button",{name:"취소",exact:true}).click()
  await expect(page.getByRole("button",{name:"후보 다음 25개",exact:true})).toBeDisabled()
  await expect(list.locator("li")).toHaveCount(25)
  expect(calls[0]).toContain(`/orders/${oldest}/cancel`);expect(calls[1]).toBe(`GET ${root}/${account.account_id}`)
  const current=await(await page.request.get(`${root}/${account.account_id}`)).json()
  expect(current.orders.find((o:{order_id:string})=>o.order_id===oldest).state).toBe("cancelled")
  expect(current.cash).toBe("1000")
  const layout=await list.evaluate(el=>({visibleActionRows:el.children.length,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,rowHeight:el.children[0]?.getBoundingClientRect().height}))
  expect(layout.visibleActionRows).toBeLessThanOrEqual(25);expect(layout.scrollWidth).toBeLessThanOrEqual(layout.width)
  console.log("REVIEW_PENDING_LAYOUT",JSON.stringify(layout));await info.attach("review-pending-layout",{body:JSON.stringify(layout),contentType:"application/json"})
  await page.screenshot({path:info.outputPath("pending-pages-kill.png"),fullPage:true})
})

for(const failedPart of ["analysis","bars"])test(`I1 실제 실행 전환의 ${failedPart} 실패는 이전 근거·CSV를 숨긴다`,async({page})=>{
  await page.goto("/")
  const run=async()=>{const response=page.waitForResponse(r=>r.url().endsWith("/api/research/simulations") && r.status()===201);await page.getByRole("button",{name:"합성 데모로 실행",exact:true}).click();return(await response).json()}
  const a=await run();await page.getByLabel("수수료 (bps / 매수·매도 각각)").fill("10");const b=await run()
  await page.route("**/api/research/research/library/runs?**",route=>route.fulfill({json:{items:[a,b],total:2,page:1,page_size:25}}))
  await page.getByRole("button",{name:"상세 분석",exact:true}).click()
  await page.locator("summary").filter({hasText:"실행 비교·QQQ 설정"}).click()
  await page.getByRole("button",{name:"분석할 실행 선택",exact:true}).nth(0).click()
  await expect(page.getByRole("link",{name:"체결 CSV",exact:true})).toHaveAttribute("href",new RegExp(a.run_id))
  const path=failedPart==="analysis" ? `**/api/research/research/runs/${b.run_id}/analysis` : `**/api/research/research/datasets/${b.manifest.snapshot_id}/bars?**`
  await page.route(path,route=>route.fulfill({status:409,json:{message:"무결성 검사 실패",code:"HTTP_ERROR"}}))
  await page.locator("summary").filter({hasText:"실행 비교·QQQ 설정"}).click()
  await page.getByRole("button",{name:"분석할 실행 선택",exact:true}).nth(1).click()
  await expect(page.getByRole("alert").filter({hasText:"요청하지 못했습니다."})).toBeFocused()
  await expect(page.getByRole("link",{name:"체결 CSV",exact:true})).toHaveCount(0)
  await expect(page.getByRole("img",{name:"검증된 snapshot 가격 · USD",exact:true})).toHaveCount(0)
  await expect(page.getByText("핵심 결과 · 서버 계산",{exact:true})).toHaveCount(0)
})

test("I1 실제 브라우저에서 늦은 이전 분석 응답이 새 실행을 덮지 않는다",async({page})=>{
  await page.goto("/")
  const run=async()=>{const response=page.waitForResponse(r=>r.url().endsWith("/api/research/simulations") && r.status()===201);await page.getByRole("button",{name:"합성 데모로 실행",exact:true}).click();return(await response).json()}
  const a=await run();await page.getByLabel("수수료 (bps / 매수·매도 각각)").fill("11");const b=await run()
  await page.route("**/api/research/research/library/runs?**",route=>route.fulfill({json:{items:[a,b],total:2,page:1,page_size:25}}))
  await page.getByRole("button",{name:"상세 분석",exact:true}).click()
  await expect(page.getByRole("link",{name:"체결 CSV",exact:true})).toHaveAttribute("href",new RegExp(b.run_id))
  let release:()=>void=()=>{},waiting=false
  await page.route(`**/api/research/research/runs/${a.run_id}/analysis`,async route=>{const response=await route.fetch();waiting=true;await new Promise<void>(r=>{release=r});await route.fulfill({response})})
  await page.locator("summary").filter({hasText:"실행 비교·QQQ 설정"}).click()
  await page.getByRole("button",{name:"분석할 실행 선택",exact:true}).nth(0).click()
  await expect.poll(()=>waiting).toBe(true)
  await page.locator("summary").filter({hasText:"실행 비교·QQQ 설정"}).click()
  await page.getByRole("button",{name:"분석할 실행 선택",exact:true}).nth(1).click()
  await expect(page.getByRole("link",{name:"체결 CSV",exact:true})).toHaveAttribute("href",new RegExp(b.run_id))
  const late=page.waitForResponse(r=>r.url().includes(`${a.run_id}/analysis`));release();await late
  await expect(page.getByRole("link",{name:"체결 CSV",exact:true})).toHaveAttribute("href",new RegExp(b.run_id))
})
