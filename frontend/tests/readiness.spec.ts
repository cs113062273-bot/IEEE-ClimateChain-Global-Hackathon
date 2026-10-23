import {expect,test} from '@playwright/test';
import fs from 'node:fs/promises';

test('service plan, executed-prefix replan, matching export and evidence, forgery and mobile',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  const initial=page.waitForResponse(r=>r.url().endsWith('/api/service/plan')&&r.status()===200);
  await page.goto('/readiness');const original=await(await initial).json();
  await expect(page.getByRole('heading',{name:'42 kWh ready for departure'})).toBeVisible();
  await page.screenshot({path:'../docs/assets/readiness-desktop.png',fullPage:true});
  const exported=page.waitForEvent('download');await page.getByRole('button',{name:'Plan JSON',exact:true}).click();
  const exportPath=await(await exported).path();const json=JSON.parse(await fs.readFile(exportPath!,'utf8'));
  expect(json.run_id).toBe(original.run_id);expect(json.plans.peak_aware.dispatch).toHaveLength(48);
  await page.getByRole('button',{name:'Respond to a change',exact:true}).click();
  const replanned=page.waitForResponse(r=>r.url().endsWith('/api/service/update'));
  await page.getByRole('button',{name:'Replan remaining hours'}).click();
  const revised=await(await replanned).json();expect(revised.status).toBe('ready');
  await expect(page.getByRole('heading',{name:'46 kWh ready for departure'})).toBeVisible();
  for(let t=0;t<17;t++)for(const key of ['ev_by_job_kwh','battery_charge_kwh','battery_discharge_kwh','soc_end_kwh']){
    const a=revised.plans.peak_aware.dispatch[t][key],b=original.plans.peak_aware.dispatch[t][key];
    if(Array.isArray(a))a.forEach((v:number,j:number)=>expect(v).toBeCloseTo(b[j],7));else expect(a).toBeCloseTo(b,7);
  }
  await page.screenshot({path:'../docs/assets/readiness-event.png',fullPage:true});
  await page.getByRole('button',{name:'Check the evidence',exact:true}).click();
  const checked=page.waitForResponse(r=>r.url().endsWith('/api/verify'));
  await page.getByRole('button',{name:'Build & verify this plan'}).click();
  expect((await(await checked).json()).verified).toBe(true);
  const evidence=page.waitForEvent('download');await page.getByRole('button',{name:'Evidence JSON'}).click();
  const proof=JSON.parse(await fs.readFile((await(await evidence).path())!,'utf8'));
  expect(proof.evidence.reproduction.run_id).toBe(revised.run_id);
  expect(proof.evidence.operational_context.events).toHaveLength(1);
  await page.getByRole('button',{name:'Forge carbon + rehash'}).click();
  await expect(page.getByText('Forgery rejected',{exact:true})).toBeVisible();
  await expect(page.getByText(/Integrity: VERIFIED/)).toBeVisible();
  await page.screenshot({path:'../docs/assets/readiness-evidence.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('button',{name:'Build & verify this plan'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
  await page.getByRole('button',{name:'Charging plan',exact:true}).click();
  await page.screenshot({path:'../docs/assets/readiness-mobile.png',fullPage:true});
  expect(errors).toEqual([]);
});

test('physical impossibility, stale exports, departure shortfall and request recovery',async({page})=>{
  await page.goto('/readiness');await expect(page.getByRole('heading',{name:'42 kWh ready for departure'})).toBeVisible();
  await page.getByLabel('Earliest departure after arrival').selectOption('4');
  await expect(page.getByRole('button',{name:'Plan JSON',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Compute protected plan'}).click();
  await expect(page.getByText('This request cannot be promised')).toBeVisible();
  await expect(page.getByText(/fleet-a: at least 2.00 kWh short/)).toBeVisible();
  await page.screenshot({path:'../docs/assets/readiness-infeasible.png',fullPage:true});
  await page.getByLabel('Earliest departure after arrival').selectOption('6');
  await page.getByRole('button',{name:'Compute protected plan'}).click();
  await expect(page.getByRole('button',{name:'Plan JSON',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'Respond to a change',exact:true}).click();
  await page.getByRole('slider',{name:'Simulated time'}).fill('16');
  await page.getByRole('button',{name:'Assess departure now'}).click();
  await expect(page.getByText('13.00 kWh unserved',{exact:true})).toBeVisible();
  await page.getByLabel('New total energy (kWh)').fill('100');
  await page.getByRole('button',{name:'Replan remaining hours'}).click();
  await expect(page.getByText('This request cannot be promised')).toBeVisible();
  await expect(page.getByRole('heading',{name:'42 kWh ready for departure'})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
  await page.getByRole('button',{name:/for the next replan/}).click();
  await page.getByRole('button',{name:'Replan remaining hours'}).click();
  await expect(page.getByRole('heading',{name:'118 kWh ready for departure'})).toBeVisible();
  await page.screenshot({path:'../docs/assets/readiness-recovery-mobile.png',fullPage:true});
});
