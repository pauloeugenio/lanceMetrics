import {test,expect} from '@playwright/test';
import {dismissInitialTour} from './onboarding-helper';
test.beforeEach(async({context})=>{await dismissInitialTour(context)});
import {execFileSync} from 'node:child_process';

// Opt-in: two isolated containers started according to the validation setup.
test('two containers transmit RTP video, display received frames and export RX metrics',async({page,request})=>{
 test.skip(process.env.LANCE_VIDEO_NETWORK_TEST!=='1','Requires two isolated Docker validation containers');
 test.setTimeout(60000);
 const server=process.env.LANCE_VIDEO_SERVER_URL||'http://127.0.0.1:18081',client=process.env.LANCE_VIDEO_CLIENT_URL||'http://127.0.0.1:18082';
 const serverContainer=process.env.LANCE_VIDEO_SERVER_CONTAINER||'lance-video-test-server',clientContainer=process.env.LANCE_VIDEO_CLIENT_CONTAINER||'lance-video-test-client';
 const basePort=Number(process.env.LANCE_VIDEO_BASE_PORT||15000),target=process.env.LANCE_VIDEO_TARGET||'host.docker.internal',peerUrl=process.env.LANCE_VIDEO_PEER_URL||'http://lance-video-test-client:8080';
 const serverAuth=await (await request.get(server+'/api/auth/config')).json(),clientAuth=await (await request.get(client+'/api/auth/config')).json();
 const serverToken=serverAuth.auth_enabled?execFileSync('docker',['exec',serverContainer,'cat','/app/run/access.token'],{encoding:'utf8'}).trim():'';
 const clientToken=clientAuth.auth_enabled?execFileSync('docker',['exec',clientContainer,'cat','/app/run/access.token'],{encoding:'utf8'}).trim():'';
 const serverHeaders={Authorization:'Bearer '+serverToken},clientHeaders={Authorization:'Bearer '+clientToken};
 execFileSync('docker',['exec',serverContainer,'ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x240:rate=30','-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','10','-c:v','libx264','-preset','ultrafast','-g','30','-c:a','aac','/tmp/network-video.mp4']);
 const source=execFileSync('docker',['exec',serverContainer,'cat','/tmp/network-video.mp4'],{maxBuffer:10*1024*1024});
 let experimentId:number|undefined;
 try{
  await request.post(client+'/api/video/receiver/stop',{headers:clientHeaders,data:{}});
  await page.goto(client);if(clientAuth.auth_enabled){await page.getByLabel('Access token').fill(clientToken);await page.getByRole('button',{name:'Connect',exact:true}).click()}
  await page.getByRole('button',{name:'Video Streaming',exact:true}).click();
  await page.getByLabel('Role',{exact:true}).selectOption('receiver');
  await page.getByLabel('Receiver Base Port',{exact:true}).fill(String(basePort));await page.getByLabel('Receiver Transport',{exact:true}).selectOption('rtp');
  await page.getByRole('button',{name:'START VIDEO RECEIVER',exact:true}).click();
  await expect(page.getByText('WAITING_FOR_STREAM',{exact:true})).toBeVisible();
  const uploaded=await request.post(server+'/api/video/library/upload?filename=network-validation.mp4',{headers:{...serverHeaders,'Content-Type':'video/mp4'},data:source});expect(uploaded.ok()).toBe(true);
  const asset=await uploaded.json();
  const started=await request.post(server+'/api/video/experiments/start',{headers:serverHeaders,data:{name:'Two-container RTP validation',target,base_port:basePort,transport:'rtp',video_ids:[asset.id],encoding_mode:'controlled',target_mbps:2,resolution:'640x360',output_fps:25,keyframe_frames:25,include_audio:true,peer_url:peerUrl,peer_token:clientToken}});
  expect(started.ok(),await started.text()).toBe(true);experimentId=(await started.json()).id;
  const image=page.getByAltText(`Vídeo recebido na porta ${basePort}`,{exact:true});await expect(image).toBeVisible({timeout:20000});
  await expect.poll(()=>image.evaluate((img:HTMLImageElement)=>img.naturalWidth)).toBeGreaterThan(0);
  await expect(page.locator('.gtitle').filter({hasText:'Vazão recebida ao vivo'})).toBeVisible();
  await page.getByRole('button',{name:`Pausar vídeo porta ${basePort}`,exact:true}).click();await expect(page.locator('.video-preview .badge')).toHaveText('PAUSED');
  await page.getByRole('button',{name:`Play vídeo porta ${basePort}`,exact:true}).click();await expect(page.locator('.video-preview .badge')).toHaveText('LIVE');
  await expect.poll(async()=>{const response=await request.get(server+'/api/experiments/'+experimentId,{headers:serverHeaders});return (await response.json()).status},{timeout:30000}).toBe('COMPLETED');
  const result=await (await request.get(server+'/api/experiments/'+experimentId,{headers:serverHeaders})).json();
  const session=result.sessions[0];expect(session.bytes_sent).toBeGreaterThan(0);expect(session.bytes_received).toBeGreaterThan(0);expect(session.preview_frames).toBeGreaterThan(0);expect(session.loss_percent).not.toBeNull();expect(session.jitter).not.toBeNull();
  expect(result.config.resolution).toBe('640x360');expect(result.config.output_fps).toBe(25);expect(result.config.peer_token).toBeUndefined();
  expect(result.measurements.some((r:any)=>r.receiver_bps>0)).toBe(true);
  const csv=await request.get(server+`/api/video/experiments/${experimentId}/export/receiver`,{headers:serverHeaders});expect(csv.ok()).toBe(true);expect(await csv.text()).toContain('receiver_bps');
 }finally{
  if(experimentId)await request.post(server+`/api/video/experiments/${experimentId}/stop`,{headers:serverHeaders,data:{}});
  await request.post(client+'/api/video/receiver/stop',{headers:clientHeaders,data:{}});
 }
});
