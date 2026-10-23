import {expect,test,type Page} from '@playwright/test';
import fs from 'node:fs/promises';

async function day(page:Page,trigger:()=>Promise<unknown>){
  const response=page.waitForResponse(r=>r.url().endsWith('/api/carpark/day')&&r.request().method()==='POST'&&r.status()===200);
  await trigger();return (await response).json();
}

test('replay a held-out day, respond to changes, compare strategies and check the record',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  const first=await day(page,()=>page.goto('/'));
  await expect(page.getByText(/Recomputed live/)).toBeVisible();
  // Tiles show the same computation the API returned.
  await expect(page.getByText('Requests met in full').locator('..').locator('..')).toContainText(`${first.metrics.served}of ${first.metrics.sessions}`);
  expect(first.metrics.cap_exceeded_slots).toBe(0);
  await expect(page.getByText('Never exceeded')).toBeVisible();
  await page.screenshot({path:'../docs/assets/carpark-desktop.png',fullPage:true});

  // Controller's view: only cars that had plugged in by 09:30 are shown.
  await page.getByRole('button',{name:'Go to 09:30, the busiest hour'}).click();
  await expect(page.getByText(/Controller's view at 09:30 UTC/)).toBeVisible();
  const arrived=first.cars.filter((c:{arrival_h:number})=>c.arrival_h<=9.5).length;
  await expect(page.locator('[role=table][aria-label=Drivers] [role=row][aria-label]')).toHaveCount(arrived);
  await expect(page.getByText(/Charging order now/)).toBeVisible();

  // A grid request issued at 09:30 changes only the future.
  const limited=await day(page,()=>page.getByRole('button',{name:'Apply grid request'}).click());
  expect(limited.events).toHaveLength(1);
  for(const [i,car] of limited.cars.entries())for(let t=0;t<19;t++)expect(car.executed_kwh[t]).toBeCloseTo(first.cars[i].executed_kwh[t],9);
  for(let t=19;t<23;t++)expect(limited.slots[t].envelope_kw).toBeLessThanOrEqual(70+1e-6);
  await expect(page.getByText(/Effect of a 70 kW limit/)).toBeVisible();
  await page.screenshot({path:'../docs/assets/carpark-event.png',fullPage:true});

  // Driver declares an early departure; the declared car leaves at that time.
  const leaving=await day(page,()=>page.getByRole('button',{name:'Tell the controller'}).click());
  expect(leaving.events).toHaveLength(2);
  const declared=leaving.cars.find((c:{declared:boolean})=>c.declared);
  expect(declared.effective_departure_h).toBe(leaving.events[1].departure_h);
  await page.getByRole('button',{name:'Remove this change'}).first().click();
  await page.getByRole('button',{name:'Remove this change'}).first().click();

  // Strategy switch is a real recomputation, compared on the same day.
  const equal=await day(page,()=>page.getByRole('button',{name:'Equal share',exact:true}).click());
  expect(equal.mode).toBe('equal_share');expect(equal.events).toHaveLength(0);
  expect(equal.compare.priority.served).toBeGreaterThanOrEqual(equal.metrics.served);
  await page.getByRole('button',{name:'GridProof priority',exact:true}).click();
  await expect(page.getByText(/Recomputed live/)).toBeVisible();

  // Held-out results tab reads the frozen evaluation.
  const results=await (await page.request.get('/api/carpark/results')).json();
  await page.getByRole('tab',{name:/held-out days/}).click();
  const f=results.followup;
  await expect(page.getByText(`To meet 90% of requests in full, GridProof needs a ${f.capacity_needed_kw.decision_time.edf_lightgbm_original_choice['>=90%']} kW connection.`,{exact:false})).toBeVisible();
  await expect(page.getByText(/physical ceiling at 11 kW/)).toBeVisible();
  await expect(page.getByRole('heading',{name:'The value is personal history, not LightGBM'})).toBeVisible();
  await page.getByRole('button',{name:'Pre-registered inputs'}).click();
  await expect(page.getByText(`To meet 95% of requests in full, GridProof needs a ${f.capacity_needed_kw.original.edf_lightgbm_original_choice['>=95%']} kW connection.`,{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Decision-time inputs'}).click();
  await page.getByRole('button',{name:'Show as table'}).click();
  await expect(page.getByRole('cell',{name:'120 kW'})).toBeVisible();
  await page.screenshot({path:'../docs/assets/carpark-heldout.png',fullPage:true});

  // Record: verify, export the same run, and reject both forgeries.
  await page.getByRole('tab',{name:'Record & verify'}).click();
  const verify=page.waitForResponse(r=>r.url().endsWith('/api/carpark/verify'));
  await page.getByRole('button',{name:/Build & verify this record/}).click();
  const check=await (await verify).json();
  expect(check.verified).toBe(true);
  for(const level of ['integrity','physical_service','decision_replay','source_lineage'])expect(check.levels[level].status).toBe('VERIFIED');
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Record JSON'}).click();
  const record=JSON.parse(await fs.readFile((await(await download).path())!,'utf8'));
  const current=await page.evaluate(()=>document.body.innerText.match(/carpark-[0-9a-f]{20}/)?.[0]);
  expect(record.evidence.reproduction.run_id).toBe(current);
  for(const button of await page.getByRole('button',{name:'Forge + re-hash'}).all())await button.click();
  await expect(page.getByText('Forgery rejected')).toHaveCount(3);
  await expect(page.getByText('Forgery accepted (unexpected)')).toHaveCount(0);
  await page.screenshot({path:'../docs/assets/carpark-record.png',fullPage:true});

  for(const width of [390,320]){
    await page.setViewportSize({width,height:844});
    await page.getByRole('tab',{name:'Replay the day'}).click();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
    await page.screenshot({path:`../docs/assets/carpark-${width}px.png`,fullPage:true});
  }
  expect(errors).toEqual([]);
});

test('invalid change requests and non-held-out days are refused with a reason',async({page})=>{
  await day(page,()=>page.goto('/'));
  const bad=await page.request.post('/api/carpark/day',{data:{date:'2024-01-17',connection_kw:120,mode:'priority',events:[{type:'cap',at_slot:20,from_slot:10,to_slot:24,kw:60}]}});
  expect(bad.status()).toBe(422);
  expect(JSON.stringify(await bad.json())).toContain('issued before it starts');
  const past=await page.request.post('/api/carpark/day',{data:{date:'2023-07-03',connection_kw:120,mode:'priority',events:[]}});
  expect(past.status()).toBe(422);
  expect(JSON.stringify(await past.json())).toContain('held-out');
});
