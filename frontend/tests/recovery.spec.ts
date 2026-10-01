import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import net from 'node:net';
async function freePort():Promise<number>{return await new Promise(resolve=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const p=(s.address() as net.AddressInfo).port;s.close(()=>resolve(p))})})}
test.afterEach(async({request})=>{await request.post('/api/server/stop',{headers:{Authorization:'Bearer '+fs.readFileSync('../run/access.token','utf8').trim()},data:{}})});
test('dashboard completion and stop recover without experiment WebSocket',async({page})=>{
 await page.routeWebSocket(/\/ws\/experiments\//,ws=>ws.close());
 await page.goto('/');await page.getByLabel('Access token').fill(fs.readFileSync('../run/access.token','utf8').trim());await page.getByRole('button',{name:'Connect',exact:true}).click();
 await page.getByRole('button',{name:'Server',exact:true}).click();const port=await freePort();await page.getByLabel('Listen address').fill('127.0.0.1');await page.getByLabel('Port',{exact:true}).fill(String(port));await page.getByRole('button',{name:'START SERVER',exact:true}).click();await expect(page.locator('.section-top .badge')).toHaveText('RUNNING');
 const name='Dashboard completion regression '+Date.now();
 await page.getByRole('button',{name:'New Experiment',exact:true}).click();await page.getByLabel('Experiment name').fill(name);await page.getByLabel('Target IP / hostname').fill('127.0.0.1');await page.getByLabel('Port',{exact:true}).fill(String(port));await page.getByLabel('Duration (s)',{exact:true}).fill('2');await page.getByRole('button',{name:'START TEST',exact:true}).click();
 await page.getByRole('button',{name:'Dashboard',exact:true}).click();await expect(page.locator('tbody tr').filter({hasText:name}).locator('.badge')).toHaveText('COMPLETED',{timeout:15000});
 await page.getByRole('button',{name:'New Experiment',exact:true}).click();await page.getByLabel('Experiment name').fill('Immediate stop regression');await page.getByLabel('Duration (s)',{exact:true}).fill('30');await page.getByRole('button',{name:'START TEST',exact:true}).click();await page.getByRole('button',{name:'STOP TEST',exact:true}).click();await expect(page.locator('.section-top .badge')).toHaveText('STOPPED',{timeout:15000});
 expect(fs.readdirSync('../run').filter(f=>f.startsWith('iperf_client_'))).toEqual([]);
 await page.getByRole('button',{name:'Server',exact:true}).click();await page.getByRole('button',{name:'STOP SERVER',exact:true}).click();await expect(page.locator('.section-top .badge')).toHaveText('STOPPED');
});
