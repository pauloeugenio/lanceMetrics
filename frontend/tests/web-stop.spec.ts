import {test,expect} from '@playwright/test';
import fs from 'node:fs';
test('web stop asks confirmation and displays restart instructions',async({page})=>{
 let calls=0;await page.route('**/api/system/stop',async route=>{calls++;await route.fulfill({status:202,contentType:'application/json',body:JSON.stringify({status:'STOPPING'})})});
 await page.goto('/');await page.getByLabel('Access token').fill(fs.readFileSync('../run/access.token','utf8').trim());await page.getByRole('button',{name:'Connect',exact:true}).click();await page.getByRole('button',{name:'System',exact:true}).click();
 page.once('dialog',dialog=>dialog.dismiss());await page.getByRole('button',{name:'Parar aplicação web'}).click();expect(calls).toBe(0);
 page.once('dialog',dialog=>dialog.accept());await page.getByRole('button',{name:'Parar aplicação web'}).click();await expect(page.getByRole('heading',{name:'Aplicação web encerrando'})).toBeVisible();expect(calls).toBe(1);
 await expect(page.getByText('./start.sh',{exact:true})).toBeVisible();
});
