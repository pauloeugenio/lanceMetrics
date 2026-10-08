"""Video validation plus optional real FFmpeg UDP/RTP/preview integration."""
import asyncio,json,os,shutil,socket,struct,subprocess,sys,time,uuid
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from backend.app import main
from backend.app.core import ROOT
from backend.app.database import Session,Experiment,init_db
from backend.app.video_schemas import VideoConfig,ReceiverConfig
from backend.app.services.video_command import FFmpegCommandBuilder
from backend.app.services.video_probe import VideoProbeService
from backend.app.services.video_network import VideoNetworkMonitor
from backend.app.services.video_store import VideoAsset,VideoSession,aggregate,now,path_for
from backend.app.services.video_tools import tool_path,tool_env
HEADERS={'Authorization':'Bearer '+main.TOKEN}

def free_port():
    with socket.socket(type=socket.SOCK_DGRAM) as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

def test_probe_parser_nullable_and_fps():
    p=VideoProbeService.parse({'format':{'duration':'4.5','size':'300','bit_rate':'800'},'streams':[{'codec_type':'video','codec_name':'h264','width':640,'height':360,'avg_frame_rate':'30000/1001'}]})
    assert p['duration']==4.5 and p['fps']==pytest.approx(29.97002997) and p['stream_bps'] is None and p['audio_codec'] is None
    with pytest.raises(ValueError):VideoProbeService.parse({'streams':[]})

@pytest.mark.parametrize('changes',[{'target':'x;touch /tmp/x'},{'base_port':0},{'target_mbps':float('nan')},{'target_mbps':0},{'preset':'$(id)'},{'codec':'x'},{'peer_url':'http://evil/x'},{'peer_url':'file:///etc/passwd'},{'execution_mode':'concurrent','base_port':65535,'video_ids':[str(uuid.uuid4()),str(uuid.uuid4())]}])
def test_invalid_video_configuration(changes):
    with pytest.raises(ValidationError):VideoConfig(**{'target':'localhost','video_ids':[str(uuid.uuid4())],**changes})

def test_commands_preserve_and_controlled():
    c=VideoConfig(target='localhost',video_ids=[uuid.uuid4()])
    args=FFmpegCommandBuilder.sender(c,'/tmp/video file.mp4',1234)
    assert '-re' in args and args[args.index('-c')+1]=='copy' and '-b:v' not in args and '/tmp/video file.mp4' in args
    args=FFmpegCommandBuilder.sender(c.model_copy(update={'encoding_mode':'controlled','target_mbps':12.345,'transport':'rtp','playback':'maximum'}),'/tmp/v',1234)
    assert '-re' not in args and args[args.index('-b:v')+1]=='12345000' and 'rtp_mpegts' in args and 'zerolatency' in args

@pytest.mark.parametrize('changes',[
    {'encoding_mode':'preserve','resolution':'1280x720'},
    {'encoding_mode':'preserve','output_fps':30},
    {'encoding_mode':'controlled','output_fps':0},
    {'encoding_mode':'controlled','output_fps':121},
    {'encoding_mode':'controlled','resolution':'720;touch /tmp/x'},
    {'encoding_mode':'controlled','keyframe_frames':601},
])
def test_invalid_output_configuration(changes):
    with pytest.raises(ValidationError):VideoConfig(target='localhost',video_ids=[uuid.uuid4()],**changes)

def test_controlled_output_size_fps_keyframes_and_audio():
    c=VideoConfig(target='localhost',video_ids=[uuid.uuid4()],encoding_mode='controlled',
                  resolution='640x360',output_fps=25,keyframe_frames=25,include_audio=False)
    args=FFmpegCommandBuilder.sender(c,'/tmp/video.mp4',1234)
    assert '-an' in args and '0:a?' not in args
    assert args[args.index('-r')+1]=='25' and args[args.index('-g')+1]=='25'
    assert 'scale=640:360:' in args[args.index('-vf')+1] and 'pad=640:360:' in args[args.index('-vf')+1]

@pytest.mark.skipif(not tool_path('ffmpeg') or not tool_path('ffprobe'),reason='FFmpeg/ffprobe not installed')
def test_preserve_avi_with_missing_presentation_timestamps(tmp_path):
    source=tmp_path/'missing_pts.avi';output=tmp_path/'remuxed.ts'
    subprocess.run([tool_path('ffmpeg'),'-v','error','-f','lavfi','-i','testsrc2=size=160x120:rate=30',
                    '-t','2','-c:v','mpeg4','-bf','2',str(source)],check=True,timeout=30,env=tool_env())
    probe=subprocess.run([tool_path('ffprobe'),'-v','error','-select_streams','v:0','-show_packets',
                          '-read_intervals','%+#1','-show_entries','packet=pts,dts','-of','json',str(source)],
                         capture_output=True,text=True,check=True,timeout=15,env=tool_env('ffprobe'))
    packet=json.loads(probe.stdout)['packets'][0]
    assert 'dts' in packet and 'pts' not in packet
    config=VideoConfig(target='localhost',video_ids=[uuid.uuid4()],playback='maximum')
    args=FFmpegCommandBuilder.sender(config,source,1234)
    args[-1]=str(output)
    remux=subprocess.run(args,capture_output=True,timeout=30,env=tool_env())
    assert remux.returncode==0,remux.stderr.decode()
    decoded=subprocess.run([tool_path('ffmpeg'),'-v','error','-i',str(output),'-vf','fps=8',
                            '-frames:v','1','-c:v','mjpeg','-threads','1','-f','image2pipe','pipe:1'],
                           capture_output=True,timeout=30,env=tool_env())
    assert decoded.returncode==0,decoded.stderr.decode()
    assert decoded.stdout.startswith(b'\xff\xd8') and decoded.stdout.endswith(b'\xff\xd9')

def rtp(seq,stamp=0,payload=b'\x47'*188):return struct.pack('!BBHII',128,33,seq,stamp,7)+payload

def test_udp_observability_never_fakes_loss():
    m=VideoNetworkMonitor('receiver','udp');assert m.observe(b'abc')==b'abc'
    s=m.summary();assert s['bytes_received']==3 and s['packets_received']==1 and s['packets_lost'] is None and s['jitter'] is None

def test_rtp_gap_reorder_duplicates_wrap_and_jitter():
    m=VideoNetworkMonitor('receiver','rtp')
    for seq,t in [(65534,0),(0,9000),(65535,4500),(0,9000)]:assert m.observe(rtp(seq,t),100+t/90000)
    assert m.loss()==(3,0,0) and m.duplicates==1
    m.observe(rtp(2,18000),100.2);assert m.loss()[1]==1
    assert m.summary()['jitter'] is not None
    assert m.observe(b'bad') is None and m.loss()==(None,None,None)

def test_aggregate_loss_and_concurrent_wall_time():
    result=aggregate([{'bytes_sent':100,'bytes_received':80,'packets_lost':2,'packets_expected':10},{'bytes_sent':200,'bytes_received':190,'packets_lost':1,'packets_expected':100}],2)
    assert result['sender_bps']==1200 and result['loss_percent']==pytest.approx(300/110)
    assert aggregate([{}],1)['bytes_sent'] is None

def test_receiver_conflict_and_peer_requires_armed_receiver(monkeypatch):
    monkeypatch.setattr('backend.app.services.video_receiver.shutil.which',lambda _: '/usr/bin/ffmpeg')
    with socket.socket(type=socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        with TestClient(main.app) as c:
            assert c.post('/api/video/receiver/start',headers=HEADERS,json={'address':'127.0.0.1','base_port':port}).status_code==409
            incoming={'experiment_uuid':str(uuid.uuid4()),'session_uuid':str(uuid.uuid4()),'stream_id':str(uuid.uuid4()),'video_id':str(uuid.uuid4()),'name':'test','original_filename':'a.mp4','port':port,'transport':'udp'}
            assert c.post('/api/video/peer/prepare',headers=HEADERS,json=incoming).status_code==409
            assert c.get('/api/video/peer/ready').status_code==401

def test_streaming_upload_validation_and_multi_file_library(monkeypatch):
    async def probe(self,path):return {'duration':3,'video_codec':'h264','size':path.stat().st_size,'source_bps':123}
    monkeypatch.setattr(VideoProbeService,'probe',probe)
    with TestClient(main.app) as c:
        for name in ['../a.mp4','a\\b.avi','a.exe']:
            assert c.post('/api/video/library/upload',params={'filename':name},headers={**HEADERS,'Content-Type':'video/mp4'},content=b'abc').status_code==422
        assert c.post('/api/video/library/upload?filename=a.mp4',headers={**HEADERS,'Content-Type':'text/html'},content=b'abc').status_code==415
        assets=[]
        for name in ['a.mp4','b.avi','c.mkv']:
            r=c.post('/api/video/library/upload',params={'filename':name},headers={**HEADERS,'Content-Type':'video/mp4'},content=b'abc');assert r.status_code==200,r.text;assets.append(r.json())
        assert len({a['id'] for a in assets})==3
        with Session() as db:
            for a in assets:assert path_for(db.get(VideoAsset,a['id'])).read_bytes()==b'abc'


def test_upload_limit_cleans_partial_file(monkeypatch):
    from backend.app.services import video_library
    monkeypatch.setattr(video_library,'MAX_UPLOAD_BYTES',2)
    with TestClient(main.app) as c:
        before=list((ROOT/'data/videos').glob('*'))
        assert c.post('/api/video/library/upload?filename=a.mp4',headers={**HEADERS,'Content-Type':'video/mp4'},content=b'abc').status_code==413
        assert list((ROOT/'data/videos').glob('*'))==before


def test_stop_partial_video_and_export_without_ffmpeg(monkeypatch):
    from backend.app.services.video_sender import VideoTrafficGenerator
    monkeypatch.setattr('backend.app.services.video_sender.shutil.which',lambda _:sys.executable)
    monkeypatch.setattr(FFmpegCommandBuilder,'sender',staticmethod(lambda *args:[sys.executable,'-c','import time;time.sleep(60)']))
    with TestClient(main.app) as c:
        assets=[]
        with Session() as db:
            for i in range(2):
                uid=str(uuid.uuid4());folder=ROOT/'data/videos';folder.mkdir(parents=True,exist_ok=True);(folder/(uid+'.mp4')).write_bytes(b'fixture')
                db.add(VideoAsset(id=uid,original_filename=f'stop_{i}.mp4',internal_filename=uid+'.mp4',created_at=now(),metadata_json={'duration':60,'video_codec':'h264'},analysis=[]));assets.append({'id':uid})
            db.commit()
        e=c.post('/api/video/experiments/start',headers=HEADERS,json={'target':'127.0.0.1','base_port':free_port(),'video_ids':[a['id'] for a in assets[:2]]})
        assert e.status_code==200,e.text;id=e.json()['id'];time.sleep(.1)
        assert c.delete('/api/experiments/'+str(id),headers=HEADERS).status_code==409
        e=c.post(f'/api/video/experiments/{id}/stop',headers=HEADERS,json={}).json();assert e['status']=='ABORTED'
        assert all(s['status']=='ABORTED' for s in e['sessions'])
        assert c.get(f'/api/video/experiments/{id}/export/json',headers=HEADERS).json()['sessions']
        assert c.get(f'/api/video/experiments/{id}/export/combined',headers=HEADERS).status_code==409
        assert not list((ROOT/'run').glob('ffmpeg_sender_*.json')) and not main.video.allocations
        with Session() as db:assert db.query(VideoSession).filter_by(experiment_id=id).count()==len(e['sessions'])
        assert c.delete('/api/experiments/'+str(id),headers=HEADERS).status_code==200
        with Session() as db:assert db.query(VideoSession).filter_by(experiment_id=id).count()==0

@pytest.mark.skipif(not tool_path('ffmpeg') or not tool_path('ffprobe'),reason='FFmpeg/ffprobe not installed')
@pytest.mark.parametrize('transport,mode',[('udp','sequential'),('rtp','sequential'),('udp','concurrent')])
def test_real_video_flow_and_preview(tmp_path,transport,mode):
    video=tmp_path/'source.mp4'
    subprocess.run([tool_path('ffmpeg'),'-v','error','-f','lavfi','-i','testsrc2=size=160x120:rate=15','-t','4','-c:v','libx264','-preset','ultrafast','-g','15','-pix_fmt','yuv420p',str(video)],check=True,timeout=30,env=tool_env())
    port=free_port()
    if mode=='concurrent':
        # Reserve and release both ports before starting the receiver.
        with socket.socket(type=socket.SOCK_DGRAM) as s:s.bind(('127.0.0.1',port+2))
    with TestClient(main.app) as c:
        assets=[]
        for i in range(2):
            r=c.post('/api/video/library/upload',params={'filename':f'video_{i}.mp4'},headers={**HEADERS,'Content-Type':'video/mp4'},content=video.read_bytes());assert r.status_code==200,r.text;assets.append(r.json())
        assert assets[0]['fps']==15 and assets[0]['duration']>0
        analysis=c.post('/api/video/library/'+assets[0]['id']+'/analyze',headers=HEADERS,json={'window_seconds':1});assert analysis.status_code==200 and analysis.json()
        r=c.post('/api/video/receiver/start',headers=HEADERS,json={'address':'127.0.0.1','base_port':port,'streams':2 if mode=='concurrent' else 1,'transport':transport});assert r.status_code==200,r.text
        e=c.post('/api/video/experiments/start',headers=HEADERS,json={'name':'Real video integration','target':'127.0.0.1','base_port':port,'transport':transport,'execution_mode':mode,'video_ids':[a['id'] for a in assets]}).json();id=e['id']
        assert c.get(f'/api/video/experiments/{id}/source-data',headers=HEADERS).json()
        seen_preview=False
        for _ in range(200):
            state=c.get('/api/video/status',headers=HEADERS).json()
            seen_preview|=any(s['preview'].get('frames',0)>0 for s in state['receiver']['streams'])
            result=c.get('/api/experiments/'+str(id),headers=HEADERS).json()
            if result['status']!='RUNNING':break
            time.sleep(.1)
        assert result['status']=='COMPLETED',result
        assert len(result['sessions'])==2 and all(s['bytes_sent']>0 for s in result['sessions'])
        if mode=='sequential':assert result['sessions'][1]['started_at']>=result['sessions'][0]['finished_at']
        else:
            assert {s['port'] for s in result['sessions']}=={port,port+2}
            assert max(s['started_at'] for s in result['sessions'])<min(s['finished_at'] for s in result['sessions'])
        assert seen_preview,'Receiver never decoded a preview frame'
        time.sleep(2.5)
        records=c.get('/api/experiments',headers=HEADERS).json()
        incoming=next(e for e in records if e['config'].get('role')=='receiver' and e['config'].get('experiment_type')=='video')
        incoming=c.get('/api/experiments/'+str(incoming['id']),headers=HEADERS).json()
        assert len(incoming['sessions'])==2 and all(s.get('bytes_received',0)>0 for s in incoming['sessions'])
        assert all(s.get('preview_frames',0)>0 for s in incoming['sessions'])
        if transport=='rtp':assert all(s['packets_lost'] is not None and s['jitter'] is not None for s in incoming['sessions'])
        else:assert all(s['packets_lost'] is None and s['jitter'] is None for s in incoming['sessions'])
        assert c.get(f'/api/video/experiments/{id}/export/metrics',headers=HEADERS).status_code==200
        assert c.get(f'/api/video/experiments/{id}/export/source',headers=HEADERS).status_code==200
        c.post('/api/video/receiver/stop',headers=HEADERS,json={})
        assert not list((ROOT/'run').glob('ffmpeg_*.json'))

@pytest.mark.skipif(not tool_path('ffmpeg') or not tool_path('ffprobe'),reason='FFmpeg/ffprobe not installed')
@pytest.mark.parametrize('auth_enabled',[True,False])
def test_two_instances_peer_preparation_controlled_and_stop(tmp_path,auth_enabled):
    import httpx
    source=tmp_path/'peer_source.mp4'
    subprocess.run([tool_path('ffmpeg'),'-v','error','-f','lavfi','-i','testsrc2=size=160x120:rate=15','-t','3','-c:v','libx264','-g','15','-preset','ultrafast',str(source)],check=True,timeout=30,env=tool_env())
    def tcp_port():
        with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
    processes=[];clients=[];roots=[]
    try:
        for name in ('sender','receiver'):
            root=tmp_path/name;root.mkdir();port=tcp_port();roots.append(root)
            log=(root/'backend.log').open('wb')
            p=subprocess.Popen([sys.executable,'-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port',str(port)],env={**os.environ,'LANCE_ROOT':str(root),'LANCE_AUTH_ENABLED':str(auth_enabled).lower()},stdout=log,stderr=log);log.close();processes.append(p)
            client=httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=20);clients.append(client)
            for _ in range(100):
                try:
                    if client.get('/health').status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:pytest.fail((root/'backend.log').read_text())
            if auth_enabled:client.headers['Authorization']='Bearer '+(root/'run/access.token').read_text().strip()
        sender,receiver=clients;port=free_port()
        assert receiver.post('/api/video/receiver/start',json={'address':'127.0.0.1','base_port':port}).status_code==200
        assets=[]
        for name in ('first.mp4','second.mp4'):
            response=sender.post('/api/video/library/upload',params={'filename':name},headers={'Content-Type':'video/mp4'},content=source.read_bytes());assert response.status_code==200,response.text;assets.append(response.json())
        config={'target':'127.0.0.1','base_port':port,'video_ids':[a['id'] for a in assets],'encoding_mode':'controlled','target_mbps':1,'peer_url':str(receiver.base_url).rstrip('/'),'peer_token':(roots[1]/'run/access.token').read_text().strip()}
        if not auth_enabled:config.pop('peer_token')
        response=sender.post('/api/video/experiments/start',json=config);assert response.status_code==200,response.text;id=response.json()['id']
        assert 'peer_token' not in response.text
        for _ in range(200):
            result=sender.get('/api/experiments/'+str(id)).json()
            if result['status']!='RUNNING':break
            time.sleep(.1)
        assert result['status']=='COMPLETED',result
        assert len(result['sessions'])==2
        assert all(s['bytes_sent']>0 and s['bytes_received']>0 and s['preview_frames']>0 for s in result['sessions'])
        assert sender.get(f'/api/video/experiments/{id}/export/receiver').status_code==200
        assert all(s['loss_percent'] is None for s in result['sessions'])
        assert not list(roots[0].rglob('ffmpeg_sender_*.json')) and not list(roots[1].rglob('ffmpeg_receiver_*.json'))
        # A second run is interrupted while active, including its corresponding remote receiver session.
        e=sender.post('/api/video/experiments/start',json=config).json();time.sleep(.5)
        stopped=sender.post('/api/video/experiments/'+str(e['id'])+'/stop',json={});assert stopped.status_code==200,stopped.text;assert stopped.json()['status']=='ABORTED'
        incoming=receiver.get('/api/experiments').json();assert any(v['status']=='ABORTED' for v in incoming)
        assert not list(roots[0].rglob('ffmpeg_sender_*.json')) and not list(roots[1].rglob('ffmpeg_receiver_*.json'))
    finally:
        for c in clients:c.close()
        for p in processes:
            if p.poll() is None:p.terminate();p.wait(timeout=15)


def test_rtp_timestamp_wrap_does_not_create_false_jitter():
    m=VideoNetworkMonitor('receiver','rtp')
    m.observe(rtp(1,4294967290),100)
    m.observe(rtp(2,894),100.01)
    assert m.summary()['jitter']==pytest.approx(0,abs=.001)


def test_deleted_receiver_record_drops_stale_process_cache():
    from backend.app.services.video_store import create_experiment,finish_experiment
    with TestClient(main.app) as client:
        id,folder=create_experiment('Finished receiver',{'role':'receiver'}, {})
        finish_experiment(id,'COMPLETED')
        uid=str(uuid.uuid4());main.video_receiver.experiments[uid]=(id,folder)
        assert client.delete('/api/experiments/'+str(id),headers=HEADERS).status_code==200
        assert uid not in main.video_receiver.experiments


def test_video_setup_failure_is_terminal(monkeypatch):
    from pathlib import Path
    from backend.app.services.video_store import create_experiment
    original=Path.write_text
    def fail_config(path,*args,**kwargs):
        if path.name=='config.json':raise OSError('simulated read-only experiment directory')
        return original(path,*args,**kwargs)
    with TestClient(main.app):
        monkeypatch.setattr(Path,'write_text',fail_config)
        with pytest.raises(ValueError,match='Experiment setup failed'):
            create_experiment('Failed video setup',{'role':'sender'}, {})
        with Session() as db:
            e=db.query(Experiment).filter_by(name='Failed video setup').order_by(Experiment.id.desc()).first()
            assert e.status=='ERROR' and e.finished_at and 'read-only' in e.error
