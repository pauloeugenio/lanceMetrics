import {test,expect} from '@playwright/test';

test('local sender and receiver open received video with pause and play',async({page})=>{
 const id='11111111-1111-4111-8111-111111111111',sid='22222222-2222-4222-8222-222222222222';
 let receiverStarted=false,experiment:any=null;
 const calls:string[]=[];
 await page.addInitScript(()=>sessionStorage.setItem('lanceToken','test-token'));
 await page.routeWebSocket('**/ws/**',ws=>{
  if(ws.url().includes('/preview/'))ws.onMessage(()=>ws.send(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')));
 });
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;let data:any={};
  if(path==='/api/video/library')data=[{id,original_filename:'sample.mp4',duration:10,width:160,height:120,fps:15,status:'READY'}];
  else if(path==='/api/video/status')data={ffmpeg:true,ffprobe:true,receiver:{status:receiverStarted?'WAITING_FOR_STREAM':'STOPPED',streams:experiment?[{port:5000,session:experiment.sessions[0]}]:[]}};
  else if(path==='/api/video/receiver/start'){receiverStarted=true;calls.push('receiver')}
  else if(path==='/api/video/experiments/start'){
   calls.push('sender');const config=route.request().postDataJSON();expect(receiverStarted).toBe(true);expect(config.target).toBe('127.0.0.1');expect(config.playback).toBe('realtime');expect(config.peer_token).toBe('test-token');
   experiment={id:1,uuid:id,name:'Local video',status:'RUNNING',started_at:new Date().toISOString(),config:{...config,experiment_type:'video',role:'sender'},sessions:[{session_uuid:sid,original_filename:'sample.mp4',port:5000,status:'RUNNING'}],measurements:[],summary:{}};data=experiment;
  }else if(path==='/api/experiments/1')data=experiment;
  else if(path==='/api/experiments'||path==='/api/profiles'||path.endsWith('/source-data'))data=[];
  await route.fulfill({json:data});
 });
 await page.goto('/');await page.getByRole('button',{name:'Video Streaming',exact:true}).click();
 await expect(page.getByLabel('Role',{exact:true})).toHaveValue('sender');await page.getByLabel('Role',{exact:true}).selectOption('both');
 await page.getByLabel('Selecionar vídeo sample.mp4',{exact:true}).check();
 await page.getByRole('button',{name:'Run Selected Videos / START EXPERIMENT',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Player do cliente'})).toBeVisible();
 const image=page.getByAltText('Vídeo recebido na porta 5000',{exact:true});await expect(image).toBeVisible();
 await expect.poll(()=>image.evaluate((img:HTMLImageElement)=>img.naturalWidth)).toBeGreaterThan(0);
 await page.getByRole('button',{name:'Pausar vídeo porta 5000',exact:true}).click();
 await expect(page.locator('.video-preview .badge')).toHaveText('PAUSED');
 await page.getByRole('button',{name:'Play vídeo porta 5000',exact:true}).click();
 await expect(page.locator('.video-preview .badge')).toHaveText('LIVE');
 expect(calls).toEqual(['receiver','sender']);
});
