import {test,expect} from '@playwright/test';
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import dgram from 'node:dgram';import {execFileSync} from 'node:child_process';
async function udpPort():Promise<number>{return new Promise(resolve=>{const s=dgram.createSocket('udp4');s.bind(0,'127.0.0.1',()=>{const p=s.address().port;s.close();resolve(p)})})}
test('20-file video upload, ordered queue, concurrent real streaming and browser preview',async({page,request})=>{
 test.setTimeout(120000);page.setDefaultTimeout(15000);const token=fs.readFileSync('../run/access.token','utf8').trim();const headers={Authorization:'Bearer '+token};
 const availability=await request.get('/api/video/status',{headers});expect(availability.ok()).toBe(true);const status=await availability.json();test.skip(!status.ffmpeg||!status.ffprobe,'FFmpeg/ffprobe not installed');
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'lance-video-browser-'));const source=path.join(temp,'source.mp4');
 execFileSync('.venv/bin/python',['-c',"from backend.app.services.video_tools import tool_path,tool_env;import subprocess,sys;subprocess.run([tool_path('ffmpeg'),'-v','error','-f','lavfi','-i','testsrc2=size=160x120:rate=15','-t','5','-c:v','libx264','-preset','ultrafast','-g','15',sys.argv[1]],env=tool_env(),check=True)",source],{cwd:'..'});
 const second=await page.context().newPage();second.setDefaultTimeout(15000);let experimentId:number|undefined;const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));second.on('pageerror',e=>errors.push(e.message));
 async function login(p:typeof page){await p.goto('/');if(await p.getByLabel('Access token').isVisible()){await p.getByLabel('Access token').fill(token);await p.getByRole('button',{name:'Connect',exact:true}).click();}await p.getByRole('button',{name:'Video Streaming',exact:true}).click()}
 try{
  await login(page);await page.getByLabel('Role',{exact:true}).selectOption('receiver');let port=await udpPort();if(port>65532)port=5000;
  await page.getByLabel('Receiver Base Port',{exact:true}).fill(String(port));await page.getByLabel('Concurrent receiver streams',{exact:true}).fill('2');await page.getByRole('button',{name:'START VIDEO RECEIVER',exact:true}).click();await expect(page.getByText('WAITING_FOR_STREAM',{exact:true})).toBeVisible();
   await login(second);await second.getByLabel('Role',{exact:true}).selectOption('sender');const prefix='Browser video validation '+Date.now();const buffer=fs.readFileSync(source);const files=Array.from({length:20},(_,i)=>({name:`${prefix}_${String(i+1).padStart(2,'0')}.mp4`,mimeType:'video/mp4',buffer}));
  await second.getByLabel('SELECT VIDEOS',{exact:true}).setInputFiles(files);
  await expect(second.getByText('20 vídeos selecionados',{exact:true})).toBeVisible({timeout:60000});await expect(second.locator('[aria-label="Uploading Videos"]')).toContainText('Overall: 100%');
  await expect(second.getByLabel(`Selecionar vídeo ${files[0].name}`,{exact:true})).toBeChecked();await expect(second.getByLabel(`Executar ${files[19].name}`,{exact:true})).toBeChecked();
  await second.getByRole('button',{name:'Deselect All',exact:true}).click();for(const f of files.slice(0,2))await second.getByLabel(`Selecionar vídeo ${f.name}`,{exact:true}).check();
  await second.getByLabel('Destination IP / Hostname',{exact:true}).fill('127.0.0.1');await second.getByLabel('Base Port',{exact:true}).fill(String(port));await second.getByLabel('Execution Mode',{exact:true}).selectOption('concurrent');
  await second.getByRole('button',{name:'Run Selected Videos / START EXPERIMENT',exact:true}).click();await expect(second.getByRole('status',{name:'Acompanhamento do vídeo'})).toBeVisible();
  const list=await request.get('/api/experiments',{headers});experimentId=(await list.json()).find((e:any)=>e.config.experiment_type==='video'&&e.config.role==='sender'&&e.status==='RUNNING').id;
  await expect(page.getByAltText(`Vídeo recebido na porta ${port}`,{exact:true})).toBeVisible({timeout:15000});expect(await page.getByAltText(`Vídeo recebido na porta ${port}`,{exact:true}).evaluate((img:HTMLImageElement)=>img.naturalWidth>0)).toBe(true);
  await page.screenshot({path:'../docs/video-receiver.png',fullPage:true});await expect(second.locator('.section-top .badge')).toHaveText('COMPLETED',{timeout:20000});
  await expect(second.getByRole('heading',{name:'Resultados por vídeo',exact:true})).toBeVisible();const csv=second.waitForEvent('download');await second.getByRole('button',{name:'All Metrics CSV',exact:true}).click();expect((await csv).suggestedFilename()).toMatch(/\.csv$/);
  await expect(second.locator('.js-plotly-plot').first()).toBeVisible();await second.screenshot({path:'../docs/video-results.png',fullPage:true});expect(errors).toEqual([]);
 }finally{
  if(experimentId)await request.post(`/api/video/experiments/${experimentId}/stop`,{headers,data:{}});
  await request.post('/api/video/receiver/stop',{headers,data:{}}).catch(()=>{});await second.close();fs.rmSync(temp,{recursive:true,force:true});
 }
});
