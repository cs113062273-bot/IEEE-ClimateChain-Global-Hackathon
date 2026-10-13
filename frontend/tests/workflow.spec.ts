import {expect,test} from "@playwright/test";

test("computed dispatch, deterministic replay, independent tamper check, and responsive audit",async({page})=>{
  const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading",{name:"Control room",exact:true})).toBeVisible();
  await expect(page.getByText("All dispatch constraints satisfied")).toBeVisible();
  await expect(page.getByText("Actual national intensity · scored after dispatch")).toBeVisible();
  await expect(page.locator("body")).not.toContainText("credits created");
  await page.getByRole("link",{name:"Intelligent dispatch",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Scenario controls"})).toBeVisible();
  const before=await page.locator(".metric-value").first().textContent();
  await page.getByRole("slider",{name:/Battery capacity/}).fill("60");
  const recomputed=page.waitForResponse(r=>r.url().endsWith("/api/compare")&&r.request().method()==="POST");
  await page.getByRole("button",{name:"Run optimization"}).click();
  const response=await recomputed;expect(response.ok()).toBeTruthy();
  const body=await response.json();expect(body.scenario.battery_capacity_kwh).toBe(60);
  expect(body.plans.hybrid.constraints.verified).toBe(true);
  await expect(page.getByText("Controls apply when you run optimization.",{exact:false})).toBeVisible();
  await page.getByRole("link",{name:"Digital twin & replay",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Interval ledger"})).toBeVisible();
  await page.getByRole("slider",{name:"Replay interval"}).fill("32");
  await expect(page.locator(".slot-clock")).toHaveText("16:00");
  const replayed=page.waitForResponse(r=>r.url().endsWith("/api/replay")&&r.request().method()==="POST");
  await page.getByRole("button",{name:"Reproduce day"}).click();
  const repeated=await (await replayed).json();
  expect(repeated.run_id).toBe(body.run_id);
  expect(repeated.runs[0].scenario.battery_capacity_kwh).toBe(60);
  expect(repeated.runs[0].plans.hybrid.metrics.emissions_kgco2).toBeCloseTo(body.plans.hybrid.metrics.emissions_kgco2,6);
  await expect(page.getByLabel("Replay result")).toContainText('"replay_id"');
  await page.getByRole("link",{name:"Trust audit",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Independent evidence fingerprint"})).toBeVisible();
  await page.getByRole("button",{name:"Generate evidence"}).click();
  await expect(page.getByRole("button",{name:"Recompute SHA256"})).toBeVisible();
  await page.getByRole("button",{name:"Recompute SHA256"}).click();
  await expect(page.getByRole("status")).toContainText("HASH MATCH");
  await page.getByRole("button",{name:"Tamper with copy"}).click();
  await page.getByRole("button",{name:"Recompute SHA256"}).click();
  await expect(page.getByRole("status")).toContainText("HASH MISMATCH");
  await page.getByRole("button",{name:"Restore original"}).click();
  await page.screenshot({path:"../docs/assets/trust-audit.png",fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole("heading",{name:"Trust audit",exact:true})).toBeVisible();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
  expect(overflow).toBe(false);expect(errors).toEqual([]);
  expect(before).toBeTruthy();
});

test("infeasible deadline retains the previous usable schedule and gives an explicit error",async({page})=>{
  await page.goto("/dispatch");
  await expect(page.getByRole("heading",{name:"Demand & dispatch"})).toBeVisible();
  await page.getByLabel("First EV deadline · UTC").selectOption("16");
  const rejected=page.waitForResponse(r=>r.url().endsWith("/api/compare")&&r.request().method()==="POST");
  await page.getByRole("button",{name:"Run optimization"}).click();
  expect((await rejected).status()).toBe(422);
  await expect(page.locator(".notice.error[role=alert]")).toBeVisible();
  await expect(page.getByRole("heading",{name:"Demand & dispatch"})).toBeVisible();
});

test("deliberate local-chain attestation verifies a real receipt and rejects duplicate scope",async({page})=>{
  await page.goto("/dispatch");
  await expect(page.getByRole("heading",{name:"Scenario controls"})).toBeVisible();
  await page.getByLabel("Historical day · UTC").selectOption("2025-01-15");
  const comparison=page.waitForResponse(r=>r.url().endsWith("/api/compare")&&r.request().method()==="POST");
  await page.getByRole("button",{name:"Run optimization"}).click();
  expect((await comparison).ok()).toBe(true);
  await page.getByRole("link",{name:"Trust audit",exact:true}).click();
  await page.getByRole("button",{name:"Generate evidence"}).click();
  await expect(page.getByRole("button",{name:"Recompute SHA256"})).toBeVisible();
  const attested=page.waitForResponse(r=>r.url().endsWith("/api/attest")&&r.request().method()==="POST");
  await page.getByRole("button",{name:"Attest on local chain"}).click();
  const receipt=await (await attested).json();
  if(receipt.status==="ATTESTED"||receipt.status==="VERIFIED"){
    expect(receipt.chain_id).toBe(31337);
    expect(receipt.transaction_hash).toMatch(/^0x[0-9a-f]{64}$/);
    const verified=page.waitForResponse(r=>r.url().includes("/api/verify/"));
    await page.getByRole("button",{name:"Verify registry"}).click();
    expect((await (await verified).json()).status).toBe("VERIFIED");
  }else{
    expect(receipt.status).toBe("REJECTED");
    expect(receipt.error.code).toBe("DUPLICATE_ACTIVE_CLAIM");
  }
  const duplicate=page.waitForResponse(r=>r.url().endsWith("/api/attest")&&r.request().method()==="POST");
  await page.getByRole("button",{name:"Attest on local chain"}).click();
  const rejected=await (await duplicate).json();
  expect(rejected.status).toBe("REJECTED");expect(rejected.error.code).toBe("DUPLICATE_ACTIVE_CLAIM");
  await expect(page.locator(".notice.error")).toContainText("DUPLICATE_ACTIVE_CLAIM");
});
