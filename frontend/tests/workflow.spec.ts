import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import net from 'node:net';
async function freePort():Promise<number>{return await new Promise(resolve=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const p=(s.address() as net.AddressInfo).port;s.close(()=>resolve(p))})})}
test('real laboratory workflow: login, server, UDP, chart, exports and profile preview',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await page.getByLabel('Access token').fill(fs.readFileSync('../run/access.token','utf8').trim());await page.getByRole('button',{name:'Connect',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Dashboard',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Server',exact:true}).click();const port=await freePort();await page.getByLabel('Listen address').fill('127.0.0.1');await page.getByLabel('Port',{exact:true}).fill(String(port));await page.getByRole('button',{name:'START SERVER',exact:true}).click();
 await expect(page.locator('.section-top .badge')).toHaveText('RUNNING');
 await page.getByRole('button',{name:'New Experiment',exact:true}).click();await page.getByLabel('Experiment name').fill('Browser validation UDP');await page.getByLabel('Target IP / hostname').fill('127.0.0.1');await page.getByLabel('Port',{exact:true}).fill(String(port));await page.getByLabel('Duration (s)',{exact:true}).fill('1');await page.getByLabel('Bandwidth value').fill('1');await page.getByRole('button',{name:'START TEST',exact:true}).click();
 await expect(page.locator('.section-top .badge')).toHaveText('COMPLETED',{timeout:15000});await expect(page.locator('.js-plotly-plot').first()).toBeVisible();
 const csvPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Download CSV'}).click();const csv=await csvPromise;expect(csv.suggestedFilename()).toMatch(/\.csv$/);
 const jsonPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Download JSON'}).click();expect((await jsonPromise).suggestedFilename()).toMatch(/\.json$/);
 const svgPromise=page.waitForEvent('download');await page.getByRole('button',{name:'SVG',exact:true}).first().click();expect((await svgPromise).suggestedFilename()).toMatch(/\.svg$/);
 await page.getByRole('button',{name:'Raw iperf output'}).click();await expect(page.getByText('stage_0.stdout',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Traffic Profiles',exact:true}).click();await page.getByRole('button',{name:'Add stage',exact:true}).click();await page.getByRole('button',{name:'Preview',exact:true}).click();await expect(page.getByText(/2 stages · 20 seconds/)).toBeVisible();
 await page.getByRole('button',{name:'Save profile',exact:true}).click();await expect(page.getByRole('button',{name:'RUN PROFILE · Configure destination'})).toBeEnabled();
 await page.getByRole('button',{name:'Server',exact:true}).click();await page.getByRole('button',{name:'STOP SERVER',exact:true}).click();await expect(page.locator('.section-top .badge')).toHaveText('STOPPED');
 await page.getByRole('button',{name:'Dashboard',exact:true}).click();await page.screenshot({path:'../docs/dashboard.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});await expect(page.getByRole('heading',{name:'Dashboard',exact:true})).toBeVisible();
 expect(errors).toEqual([]);
});
