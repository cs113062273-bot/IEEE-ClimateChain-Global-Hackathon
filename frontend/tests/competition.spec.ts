import {expect,test} from "@playwright/test";

test("trained AI, carbon-cost-peak comparison, source lineage and rehashed attack",async({page})=>{
  await page.goto("/dispatch");
  await expect(page.getByTestId("forecast-model")).toHaveText("lightgbm-past-only-v1");
  await expect(page.getByRole("table",{name:"Carbon cost peak comparison"})).toBeVisible();
  await expect(page.getByText("Peak-aware hybrid",{exact:true})).toBeVisible();
  await page.getByRole("link",{name:"Trust audit",exact:true}).click();
  await page.getByRole("button",{name:"Generate evidence",exact:true}).click();
  await expect(page.getByRole("button",{name:"Verify all local layers"})).toBeVisible();
  await page.getByRole("button",{name:"Verify all local layers"}).click();
  await expect(page.getByTestId("full-verification")).toContainText("VERIFIED");
  await page.getByRole("button",{name:"Tamper with copy"}).click();
  await expect(page.getByTestId("full-verification")).toHaveCount(0);
  await page.getByRole("button",{name:"Verify all local layers"}).click();
  await expect(page.getByTestId("full-verification")).toContainText("HASH_MISMATCH");
  await page.getByRole("button",{name:"Restore original"}).click();
  await page.getByRole("button",{name:"Forge CI + rehash"}).click();
  await expect(page.getByTestId("lineage-attack")).toContainText("Source Lineage: MISMATCH");
  await expect(page.getByTestId("lineage-attack")).toContainText("Integrity: VERIFIED");
  await expect(page.getByTestId("lineage-attack")).toContainText("HASH_MISMATCH");
  await page.getByRole("button",{name:"Load recorded release proof"}).click();
  await page.getByRole("button",{name:"Verify all local layers"}).click();
  await expect(page.getByTestId("full-verification")).toContainText("VERIFIED");
});

test("judge pages remain readable on desktop and phone",async({page})=>{
  for(const [path,title,name] of [["/","Control room","control-room"],["/dispatch","Intelligent dispatch","dispatch"],["/replay","Digital twin & replay","replay"],["/audit","Trust audit","trust-audit"]]){
    await page.goto(path);
    await expect(page.getByRole("heading",{name:title,exact:true})).toBeVisible();
    await expect(page.getByRole("button",{name:"Run optimization"}).or(page.getByRole("button",{name:"Generate evidence"}))).toBeEnabled();
    await page.screenshot({path:"../docs/assets/"+name+".png",fullPage:true});
  }
  await page.goto("/");
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByText("Peak grid import",{exact:true}).first()).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)).toBe(false);
  await page.screenshot({path:"../docs/assets/control-phone.png",fullPage:true});
});

test("offline recorded demo works without API, network, runtime or wallet",async({page})=>{
  await page.goto("/offline/index.html");
  await page.context().setOffline(true);
  await page.getByRole("button",{name:"Verify recorded hash and pinned source inputs"}).click();
  await expect(page.locator("#verification")).toContainText("Integrity: PASS");
  await expect(page.locator("#verification")).toContainText("Source Lineage (CI / radiation / PV / load / tariff): PASS");
  await page.getByRole("button",{name:"Forge CI + rehash"}).click();
  await expect(page.locator("#verification")).toContainText("Integrity: PASS");
  await expect(page.locator("#verification")).toContainText("MISMATCH / INCOMPLETE");
  await page.locator("#day").selectOption("2025-10-13");
  await expect(page.locator("#model")).toContainText("lightgbm-past-only-v1");
  await expect(page.locator("#verification")).toContainText("On-chain Attestation: NOT CHECKED");
});
