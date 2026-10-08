import {test,expect,type Page} from '@playwright/test';
const popover=(page:Page)=>page.locator('.driver-popover');
async function mockApp(page:Page,auth=false){
 await page.routeWebSocket('**/ws/**',()=>{});
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  const json=path==='/api/auth/config'?{auth_enabled:auth}:path==='/api/status'?{version:'0.1.0',server:{status:'STOPPED'},iperf:{version:'3.16'}}:path==='/api/system'?{hostname:'tour-test',interfaces:[]}:['/api/experiments','/api/profiles','/api/video/library'].includes(path)?[]:path==='/api/video/status'?{ffmpeg:true,ffprobe:true,receiver:{status:'STOPPED',streams:[]}}:{};
  await route.fulfill({json});
 });
}
async function help(page:Page,overview=false){
 await page.getByRole('button',{name:'Ajuda e tutoriais',exact:true}).click();
 await page.getByRole('menuitem',{name:overview?'Visão geral da aplicação':'Tutorial desta página',exact:true}).click();
 await expect(popover(page)).toBeVisible();
}
async function skip(page:Page){await popover(page).getByRole('button',{name:'Pular tutorial',exact:true}).click();await expect(popover(page)).toHaveCount(0)}
async function finish(page:Page){
 for(let i=0;i<30;i++){
  const done=popover(page).getByRole('button',{name:'Concluir tutorial',exact:true});
  if(await done.count()){await done.click();await expect(popover(page)).toHaveCount(0);return}
  await popover(page).getByRole('button',{name:'Próximo',exact:true}).click();await page.waitForTimeout(280);
 }
 throw Error('Tour did not finish within 30 steps');
}
async function stored(page:Page){return page.evaluate(()=>Object.entries(localStorage).filter(([key])=>key.startsWith('lance.metrics.tour.v1')).map(([key,value])=>({key,...JSON.parse(value)})))}

test('first visit: next, previous, skip, persistence and manual restart',async({page})=>{
 await mockApp(page);await page.goto('/');
 await expect(popover(page)).toContainText('Bem-vindo ao LANCE Metrics');
 await expect(popover(page)).toContainText('Etapa 1 de 10');await page.waitForTimeout(300);await page.screenshot({path:'/tmp/lance-tour-desktop.png'});
 await expect(page.locator('.driver-overlay')).toBeVisible();
 await popover(page).getByRole('button',{name:'Próximo',exact:true}).click();await expect(popover(page)).toContainText('Dashboard: seu ponto de partida');
 await popover(page).getByRole('button',{name:'Anterior',exact:true}).click();await expect(popover(page)).toContainText('Bem-vindo ao LANCE Metrics');
 await skip(page);expect((await stored(page))[0].status).toBe('skipped');
 await page.reload();await expect(page.getByRole('heading',{name:'Dashboard',exact:true})).toBeVisible();await page.waitForTimeout(1000);await expect(popover(page)).toHaveCount(0);
 await help(page,true);await expect(popover(page)).toContainText('Bem-vindo ao LANCE Metrics');await finish(page);
 expect((await stored(page)).find(s=>s.key.endsWith(':overview')).status).toBe('completed');
 await expect(page.getByRole('button',{name:'Ajuda e tutoriais',exact:true})).toBeFocused();
 await page.reload();await page.waitForTimeout(1000);await expect(popover(page)).toHaveCount(0);
});

test('page tours follow navigation and omit unavailable video controls',async({page})=>{
 const mutations:string[]=[];page.on('request',r=>{if(r.url().includes('/api/')&&r.method()==='POST')mutations.push(r.url())});
 await mockApp(page);await page.goto('/');await expect(popover(page)).toBeVisible();await skip(page);
 await page.getByRole('button',{name:'Video Streaming',exact:true}).click();await help(page);
 await expect(popover(page)).toContainText('Escolha servidor ou cliente');await expect(popover(page)).toContainText('Etapa 1 de 7');
 await finish(page);expect(mutations).toEqual([]);
 await page.getByLabel('Role',{exact:true}).selectOption('receiver');await help(page);
 await expect(popover(page)).toContainText('Etapa 1 de 3');await popover(page).getByRole('button',{name:'Próximo',exact:true}).click();await expect(popover(page)).toContainText('Prepare a recepção');
 await page.keyboard.press('Escape');await expect(popover(page)).toHaveCount(0);await expect(page.getByRole('button',{name:'Ajuda e tutoriais',exact:true})).toBeFocused();
 await page.getByRole('button',{name:'System',exact:true}).click();await help(page);await expect(popover(page)).toContainText('Controle o serviço pelo terminal');await finish(page);
 expect(mutations).toEqual([]);
});

test('responsive tour, reduced motion, keyboard and unavailable target recovery',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:'reduce'});await mockApp(page);await page.goto('/');await expect(popover(page)).toBeVisible();
 await expect(page.locator('body')).not.toHaveClass(/driver-fade/);await page.screenshot({path:'/tmp/lance-tour-mobile.png'});
 const box=await popover(page).boundingBox();expect(box!.x).toBeGreaterThanOrEqual(0);expect(box!.x+box!.width).toBeLessThanOrEqual(390);
 await page.keyboard.press('ArrowRight');await expect(popover(page)).toContainText('Dashboard: seu ponto de partida');
 await page.evaluate(()=>document.querySelector('[data-tour="nav-dashboard"]')?.remove());
 await expect(popover(page)).toContainText('Crie um experimento');
 await page.keyboard.press('Tab');expect(await page.evaluate(()=>!!document.activeElement?.closest('.driver-popover'))).toBe(true);
 await page.keyboard.press('Escape');await expect(popover(page)).toHaveCount(0);
 await help(page);await expect(popover(page)).toContainText('Comece pelo Dashboard');await finish(page);
});

test('authenticated identities have separate persistence, including HTTP without Web Crypto',async({page})=>{
 await page.addInitScript(()=>Object.defineProperty(window.crypto,'subtle',{value:undefined}));await mockApp(page,true);
 async function login(token:string){await page.getByLabel('Access token',{exact:true}).fill(token);await page.getByRole('button',{name:'Connect',exact:true}).click();await expect(popover(page)).toBeVisible();await skip(page)}
 await page.goto('/');await login('identity-a');await page.getByRole('button',{name:'Disconnect',exact:true}).click();await login('identity-b');
 const entries=await stored(page);expect(entries).toHaveLength(2);expect(entries[0].key).not.toBe(entries[1].key);expect(JSON.stringify(entries)).not.toContain('identity-');
});

test('storage unavailable still permits closing and manually restarting',async({page})=>{
 await page.addInitScript(()=>{const originalGet=Storage.prototype.getItem,originalSet=Storage.prototype.setItem;Storage.prototype.getItem=function(key){if(this===localStorage)throw Error('disabled');return originalGet.call(this,key)};Storage.prototype.setItem=function(key,value){if(this===localStorage)throw Error('disabled');return originalSet.call(this,key,value)}});
 await mockApp(page);await page.goto('/');await expect(popover(page)).toBeVisible();await skip(page);await help(page,true);await page.keyboard.press('Escape');await expect(popover(page)).toHaveCount(0);
});

for(const [module,title] of [['New Experiment','Escolha o tipo de teste'],['Server','Configure o servidor iperf3'],['Traffic Profiles','Crie ou importe um perfil'],['Experiments','Encontre um experimento'],['Reports','Localize o resultado'],['System','Controle o serviço pelo terminal']])test(`module tour: ${module}`,async({page})=>{
 await mockApp(page);await page.goto('/');await expect(popover(page)).toBeVisible();await skip(page);await page.getByRole('button',{name:module,exact:true}).click();await help(page);await expect(popover(page)).toContainText(title);await finish(page);
});

test('page changes tear down overlay without restarting onboarding',async({page})=>{
 await mockApp(page);await page.goto('/');await expect(popover(page)).toBeVisible();await skip(page);await help(page);
 await page.evaluate(()=>document.querySelector<HTMLButtonElement>('[data-tour="nav-system"]')?.click());
 await expect(page.getByRole('heading',{name:'System',exact:true})).toBeVisible();await expect(popover(page)).toHaveCount(0);await page.waitForTimeout(900);await expect(page.locator('.driver-overlay')).toHaveCount(0);
});
