from .video_tools import tool_path,tool_env
"""Queue execution and measured FFmpeg video traffic; no iperf dependency."""
import asyncio,json,shutil,socket,time,uuid
from datetime import datetime
from ..database import Session,Experiment
from .video_store import VideoAsset,asset_data,path_for,create_experiment,save_session,persist_sample,finish_experiment,csv_rows,now
from .video_command import FFmpegCommandBuilder
from .video_network import VideoNetworkMonitor
from .video_peer import VideoPeer
from .system_service import system_info

class VideoTrafficGenerator:
    def __init__(self,manager,publish):self.manager=manager;self.publish=publish;self.tasks={};self.stop_tasks={};self.allocations=set();self.reservations={}
    async def start(self,c,profile=None):
        if not tool_path('ffmpeg'):raise ValueError('FFmpeg is missing. Install FFmpeg and run Diagnostics.')
        assets=[]
        with Session() as db:
            for uid in c.video_ids:
                asset=db.get(VideoAsset,str(uid))
                if not asset or not path_for(asset).is_file():raise ValueError('Video not found: '+str(uid))
                if c.encoding_mode=='preserve' and asset.metadata_json.get('video_codec') not in ('h264','hevc','mpeg2video','mpeg1video','mpeg4'):
                    raise ValueError('Source codec is not supported by MPEG-TS remux. Choose Controlled Bitrate.')
                assets.append(asset)
        ports=[c.base_port+2*i if c.execution_mode=='concurrent' else c.base_port for i in range(len(assets))]
        allocations={(c.target,p) for p in ports}
        if self.allocations & allocations:raise ValueError('Destination stream ports are already assigned to an active experiment')
        # Resolve before creating a RUNNING record; error leaves no orphan task.
        addresses=await asyncio.get_running_loop().getaddrinfo(c.target,c.base_port,type=socket.SOCK_DGRAM)
        family,_,_,_,remote=addresses[0]
        peer=VideoPeer(c.peer_url,c.peer_token) if c.peer_url else None
        if peer:
            ready=await peer.call('ready')
            if ready.get('status') not in ('WAITING_FOR_STREAM','RECEIVING'):raise ValueError('Start Video Receiver on destination first')
            rc=ready.get('config') or {}
            available={rc.get('base_port',0)+2*i for i in range(rc.get('streams',0))}
            if not set(ports)<=available or rc.get('transport')!=c.transport:raise ValueError('Receiver ports/transport do not match the queue')
        config=c.model_dump(mode='json');config.update(role='sender',protocol=c.transport,port=c.base_port,receiver=c.target,sender=socket.gethostname())
        allocations={(family,remote[0],p) for p in ports}
        if self.allocations & allocations:raise ValueError('Destination stream ports are already assigned to an active experiment')
        if c.encoding_mode=='preserve':config['target_mbps']=None
        id,folder=create_experiment(c.name,config,system_info());self.allocations.update(allocations);self.reservations[id]=allocations
        sessions=[]
        with Session() as db:uid=db.get(Experiment,id).uuid
        for index,(asset,port) in enumerate(zip(assets,ports)):
            sessions.append({'session_uuid':str(uuid.uuid4()),'experiment_uuid':uid,'video_id':asset.id,'video_index':index,
                'original_filename':asset.original_filename,'stream_id':str(uuid.uuid4()),'port':port,'transport':c.transport,
                'source_bitrate':asset.metadata_json.get('source_bps'),'target_bitrate':c.target_mbps*1e6 if c.encoding_mode=='controlled' else None,
                'source_metadata':asset.metadata_json,'status':'QUEUED','started_at':None,'finished_at':None,'role':'sender'})
        try:
            for asset,values in zip(assets,sessions):
                save_session(id,values)
                (folder/'sessions'/values['session_uuid']/'source_bitrate.csv').write_text(csv_rows(asset.analysis or []))
        except Exception as ex:
            self.allocations.difference_update(allocations);self.reservations.pop(id,None)
            finish_experiment(id,'ERROR','Session setup failed: '+str(ex))
            raise ValueError('Session setup failed: '+str(ex)) from ex
        self.tasks[id]=asyncio.create_task(self.run(id,folder,c,assets,sessions,peer,family,remote,allocations))
        from .export_service import experiment_data
        return experiment_data(id)

    async def run(self,id,folder,c,assets,sessions,peer,family,remote,allocations):
        status='COMPLETED';error=None
        try:
            (folder/'video_manifest.json').write_text(json.dumps({'experiment_id':id,'videos':[asset_data(a) for a in assets]},indent=2))
            if c.execution_mode=='sequential':
                for asset,values in zip(assets,sessions):
                    await self.transmit(id,folder,c,asset,values,peer,family,remote)
                    if not peer and values is not sessions[-1]:await asyncio.sleep(2.5) # lets an unpaired receiver finalize idle boundaries
            else:
                tasks=[asyncio.create_task(self.transmit(id,folder,c,a,v,peer,family,remote)) for a,v in zip(assets,sessions)]
                try:await asyncio.gather(*tasks)
                finally:
                    for task in tasks:
                        if not task.done():task.cancel()
                    await asyncio.gather(*tasks,return_exceptions=True)
        except asyncio.CancelledError:status='ABORTED'
        except Exception as ex:status='ERROR';error=str(ex)
        finally:
            for values in sessions:
                if values['status']=='QUEUED':values.update(status='ABORTED' if status=='ABORTED' else 'SKIPPED',finished_at=now());save_session(id,values)
            if peer:
                try:await peer.call('complete',{'experiment_uuid':sessions[0]['experiment_uuid'],'aborted':status!='COMPLETED'})
                except Exception as ex:
                    error=(error+'; ' if error else '')+'Receiver finalization failed: '+str(ex)
                    if status=='COMPLETED':status='ERROR'
            finish_experiment(id,status,error);self.allocations.difference_update(allocations);self.reservations.pop(id,None)
            await self.publish(id,{'type':'completed','status':status})

    async def transmit(self,id,root,c,asset,values,peer,family,remote):
        key='ffmpeg_sender_'+values['session_uuid'];folder=root/'sessions'/values['session_uuid'];folder.mkdir(parents=True,exist_ok=True)
        bridge=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);bridge.bind(('127.0.0.1',0));bridge.setblocking(False)
        rtcp_sink=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);rtcp_sink.bind(('127.0.0.1',0))
        tx=socket.socket(family,socket.SOCK_DGRAM);tx.setblocking(False)
        remote=(remote[0],values['port'],*remote[2:]);monitor=VideoNetworkMonitor('sender',c.transport);rows=[];tasks=[];peer_prepared=False
        loop=asyncio.get_running_loop();process=None;status='COMPLETED';error=None
        with Session() as db:experiment_start=db.get(Experiment,id).started_at
        try:
            if peer:
                preparation=asyncio.create_task(peer.call('prepare',{'experiment_uuid':values['experiment_uuid'],'session_uuid':values['session_uuid'],'stream_id':values['stream_id'],'video_id':asset.id,
                    'name':c.name,'original_filename':asset.original_filename,'port':values['port'],'transport':c.transport,'metadata':asset.metadata_json,
                    'target_bps':values['target_bitrate'],'encoding_mode':c.encoding_mode,'execution_mode':c.execution_mode}))
                try:
                    await asyncio.shield(preparation);peer_prepared=True
                except asyncio.CancelledError:
                    # Resolve in-flight preparation before finalization can stop its remote decoder.
                    await asyncio.gather(preparation,return_exceptions=True)
                    peer_prepared=not preparation.cancelled() and preparation.exception() is None
                    raise
            values.update(started_at=now(),status='RUNNING');save_session(id,values)
            monitor.started=monitor.last=time.monotonic()
            offset=(datetime.fromisoformat(values['started_at'])-datetime.fromisoformat(experiment_start)).total_seconds()
            async def relay():
                while True:
                    data,_=await loop.sock_recvfrom(bridge,65535)
                    await loop.sock_sendto(tx,data,remote)
                    monitor.observe(data)
            async def sample():
                while True:
                    await asyncio.sleep(.5);row=monitor.sample(values['session_uuid'],offset)
                    row.update(source_bps=values['source_bitrate'],target_bps=values['target_bitrate'],playback_time=values.get('playback_time'))
                    rows.append(row);persist_sample(id,row);values.update(monitor.summary());save_session(id,values)
                    await self.publish(id,{'type':'measurement','measurement':row})
            args=FFmpegCommandBuilder.sender(c,path_for(asset),bridge.getsockname()[1],rtcp_sink.getsockname()[1]);values['command']=args
            process=await self.manager.spawn(key,args,{'type':'video_sender','experiment_id':id,'session_uuid':values['session_uuid']},env=tool_env())
            values['pid']=process.pid;save_session(id,values)
            async def stderr():
                with (folder/'ffmpeg_sender.log').open('ab') as log:
                    while chunk:=await process.stderr.read(8192):log.write(chunk)
            async def progress():
                while line:=await process.stdout.readline():
                    key,value=line.decode(errors='replace').strip().partition('=')[::2]
                    if key=='out_time_us':
                        try:values['playback_time']=max(0,int(value)/1e6)
                        except ValueError:pass
                    elif key=='progress':values['ffmpeg_status']=value
            tasks=[asyncio.create_task(relay()),asyncio.create_task(sample()),asyncio.create_task(stderr()),asyncio.create_task(progress())]
            duration=asset.metadata_json.get('duration') or 3600
            waiter=asyncio.create_task(process.wait())
            try:
                done,_=await asyncio.wait([waiter,tasks[0],tasks[1]],timeout=max(60,duration*2+30),return_when=asyncio.FIRST_COMPLETED)
                if not done:raise TimeoutError('FFmpeg transmission timeout')
                for task in done:
                    if task is not waiter:task.result();raise RuntimeError('Video monitor ended unexpectedly')
                await waiter
                if process.returncode:raise RuntimeError('FFmpeg failed. See session ffmpeg_sender.log.')
                await asyncio.sleep(.3)
                if not monitor.packets:raise RuntimeError('FFmpeg produced no UDP datagrams')
            finally:
                if not waiter.done():waiter.cancel()
                await asyncio.gather(waiter,return_exceptions=True)
        except asyncio.CancelledError:status='ABORTED';raise
        except Exception as ex:status='ERROR';error=str(ex);raise
        finally:
            await self.manager.stop(key,grace_seconds=.5)
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            bridge.close();rtcp_sink.close();tx.close()
            if values['started_at']:
                row=monitor.sample(values['session_uuid'],offset);row.update(source_bps=values['source_bitrate'],target_bps=values['target_bitrate']);rows.append(row);persist_sample(id,row)
                values.update(monitor.summary())
            if peer and peer_prepared:
                try:
                    received=await peer.call('finish',{'experiment_uuid':values['experiment_uuid'],'session_uuid':values['session_uuid'],'aborted':status!='COMPLETED'})
                    if received:
                        for name in ('average_rx_bitrate','bytes_received','packets_received','packets_expected','packets_lost','loss_percent','jitter','preview_frames'):values[name]=received.get(name)
                        remote_rows=received.pop('measurements',[])
                        values['receiver_result']=received
                        # Plot relative to nominal session start, explicitly NOT cross-host clock sync.
                        if remote_rows:
                            start=min(r.get('interval_start',r['elapsed_time']) for r in remote_rows)
                            copied=[{**r,'receiver_elapsed_time':r['elapsed_time']-start,'elapsed_time':offset+r['elapsed_time']-start,
                                     'clock_alignment':'nominal_session_start; no clock synchronization'} for r in remote_rows]
                            for row in copied:persist_sample(id,row)
                            (folder/'metrics_receiver.csv').write_text(csv_rows(copied))
                except Exception as ex:
                    values['receiver_error']=str(ex)
                    if status=='COMPLETED':status='ERROR';error='Receiver results unavailable: '+str(ex)
            values.update(status=status,finished_at=now(),error=error);save_session(id,values)
            (folder/'metrics_sender.csv').write_text(csv_rows(rows));(folder/'source_bitrate.csv').write_text(csv_rows(asset.analysis or []))
            if peer and peer_prepared and values.get('receiver_result'):
                (folder/'receiver_result.json').write_text(json.dumps(values['receiver_result'],indent=2))
            await self.publish(id,{'type':'session','session':values})
            if status=='ERROR' and error:raise RuntimeError(error)

    async def stop(self,id):
        pending=self.stop_tasks.get(id)
        if pending is None or pending.done():
            pending=asyncio.create_task(self._stop(id));self.stop_tasks[id]=pending
        await asyncio.shield(pending)

    async def _stop(self,id):
        task=self.tasks.get(id)
        if task and not task.done():task.cancel();await asyncio.gather(task,return_exceptions=True)
        self.allocations.difference_update(self.reservations.pop(id,set()))
        with Session() as db:
            e=db.get(Experiment,id)
            if e and e.status=='RUNNING':
                for v in e.sessions or []:
                    if v['status'] in ('QUEUED','RUNNING'):v.update(status='ABORTED',finished_at=now());save_session(id,v)
                finish_experiment(id,'ABORTED')
    async def shutdown(self):
        for id in list(self.tasks):await self.stop(id)
