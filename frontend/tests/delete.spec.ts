import {test,expect} from '@playwright/test';import fs from 'node:fs';import net from 'node:net';
async function port():Promise<number>{return new Promise(resolve=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const p=(s.address() as net.AddressInfo).port;s.close(()=>resolve(p))})})}
test('checkbox selection, confirmation, individual and bulk experiment deletion',async({page,request})=>{
 const auth={Authorization:'Bearer '+fs.readFileSync('../run/access.token','utf8').trim()};const ids:number[]=[];const name='Delete UI validation '+Date.now();
 try{
  // Use a guaranteed unused destination to produce genuine completed error records.
  for(let i=0;i<3;i++){
   const response=await request.post('/api/tests/start',{headers:auth,data:{name:name+' '+i,target:'127.0.0.1',port:await port(),duration:1}});expect(response.ok()).toBe(true);const e=await response.json();ids.push(e.id);
   await expect.poll(async()=>{const r=await request.get('/api/experiments/'+e.id,{headers:auth});return(await r.json()).status}).toBe('ERROR');
  }
  await page.goto('/');await page.getByLabel('Access token').fill(auth.Authorization.slice(7));await page.getByRole('button',{name:'Connect',exact:true}).click();await page.getByRole('button',{name:'Experiments',exact:true}).click();await page.getByLabel('Search experiments').fill(name);
  page.once('dialog',d=>d.dismiss());await page.getByRole('button',{name:`Excluir experimento ${ids[0]}`,exact:true}).click();await expect(page.getByLabel(`Selecionar experimento ${ids[0]}`,{exact:true})).toBeVisible();
  page.once('dialog',d=>d.accept());await page.getByRole('button',{name:`Excluir experimento ${ids[0]}`,exact:true}).click();await expect(page.getByLabel(`Selecionar experimento ${ids[0]}`,{exact:true})).toHaveCount(0);
  await page.getByLabel('Selecionar experimentos visíveis',{exact:true}).check();await expect(page.getByLabel(`Selecionar experimento ${ids[1]}`,{exact:true})).toBeChecked();await expect(page.getByLabel(`Selecionar experimento ${ids[2]}`,{exact:true})).toBeChecked();await expect(page.getByRole('heading',{name:'Experiments',exact:true})).toBeVisible();
  page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'Excluir selecionados'}).click();await expect(page.locator('tbody tr')).toHaveCount(0);await expect(page.getByRole('button',{name:'Excluir selecionados'})).toBeDisabled();
  for(const id of ids)expect((await request.get('/api/experiments/'+id,{headers:auth})).status()).toBe(404);
 }finally{for(const id of ids)await request.delete('/api/experiments/'+id,{headers:auth})}
});
