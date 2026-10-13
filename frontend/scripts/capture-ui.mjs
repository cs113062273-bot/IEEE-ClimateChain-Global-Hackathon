import {chromium} from '@playwright/test';
import {mkdir} from 'node:fs/promises';

const browser=await chromium.launch({channel:process.env.GRIDPROOF_BROWSER_CHANNEL??(process.platform==='win32'?'msedge':undefined),headless:true});
const page=await browser.newPage({viewport:{width:1920,height:1080}});
const failures=[];
page.on('pageerror',error=>{failures.push(error.message);process.stderr.write(error.stack+'\n');});
await mkdir('../docs/assets',{recursive:true});
try {
  await page.goto('http://127.0.0.1:3000');
  await page.getByText('All dispatch constraints satisfied').waitFor({timeout:60000});
  await page.screenshot({path:'../docs/assets/control-room.png',fullPage:true});
  await page.getByRole('link',{name:'Intelligent dispatch',exact:true}).click();
  await page.getByRole('heading',{name:'Demand & dispatch'}).waitFor();
  await page.screenshot({path:'../docs/assets/dispatch.png',fullPage:true});
  await page.getByRole('link',{name:'Digital twin & replay',exact:true}).click();
  await page.getByRole('heading',{name:'Interval ledger'}).waitFor();
  await page.screenshot({path:'../docs/assets/replay.png',fullPage:true});
  if(failures.length)throw new Error(failures.join('\n'));
  process.stdout.write('Captured computed Control Room, Dispatch and Replay at1920x1080.\n');
} catch(error) {
  await page.screenshot({path:'../docs/assets/qa-failure.png',fullPage:true});
  process.stderr.write((await page.locator('body').innerText())+'\n');
  throw error;
} finally {await browser.close();}
