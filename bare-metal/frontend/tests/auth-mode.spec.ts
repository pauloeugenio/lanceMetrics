import {test,expect} from '@playwright/test';
import {dismissInitialTour} from './onboarding-helper';
test.beforeEach(async({context})=>{await dismissInitialTour(context)});

for(const enabled of [false,true])test(`authentication ${enabled?'enabled':'disabled'} controls initial page`,async({page})=>{
 await page.routeWebSocket('**/ws/**',()=>{});
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  const json=path==='/api/auth/config'?{auth_enabled:enabled}:['/api/experiments','/api/profiles','/api/video/library'].includes(path)?[]:path==='/api/video/status'?{ffmpeg:true,ffprobe:true,receiver:{status:'STOPPED',streams:[]}}:{};
  await route.fulfill({json});
 });
 await page.goto('/');
 if(enabled){await expect(page.getByLabel('Access token',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Video Streaming',exact:true})).toHaveCount(0)}
 else{
  await expect(page.getByRole('button',{name:'Video Streaming',exact:true})).toBeVisible();
  await expect(page.getByLabel('Access token',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Disconnect',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Video Streaming',exact:true}).click();
  await expect(page.getByLabel('Role',{exact:true})).toBeVisible();
 }
});
