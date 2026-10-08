import {test,expect} from '@playwright/test';
import {dismissInitialTour} from './onboarding-helper';
test.beforeEach(async({context})=>{await dismissInitialTour(context)});
import fs from 'node:fs';
test('System directs web service shutdown to the terminal script',async({page})=>{
 await page.goto('/');await page.getByLabel('Access token').fill(fs.readFileSync(process.env.LANCE_TEST_TOKEN_FILE||'../run/access.token','utf8').trim());await page.getByRole('button',{name:'Connect',exact:true}).click();await page.getByRole('button',{name:'System',exact:true}).click();await expect(page.getByRole('heading',{name:'Controle pelo terminal'})).toBeVisible();await expect(page.getByText('./lanceMetrics stop-web',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Parar aplicação web'})).toHaveCount(0);
});
