from .video_tools import tool_path,tool_env
"""UDP/RTP ingress, persistent sessions and independent browser decoder relay."""
import asyncio,json,shutil,socket,time,uuid
from datetime import datetime
from ..core import ROOT
from ..database import Session,Experiment
from .video_store import create_experiment,save_session,persist_sample,finish_experiment,now,csv_rows
from .video_network import VideoNetworkMonitor
from .video_preview import VideoPreviewService
from .system_service import system_info

class FFmpegVideoReceiver:
    def __init__(self,manager,publish):
        self.manager=manager;self.publish=publish;self.preview=VideoPreviewService(manager)
        self.config=None;self.sockets={};self.tasks={};self.live={};self.prepared={};self.experiments={};self.manual_id=None
        self.status='STOPPED';self.error=None;self.stop_task=None;self.reserved=set()

    def snapshot(self):
        return {'status':self.status,'config':self.config.model_dump() if self.config else None,'error':self.error,
                'streams':[{'port':port,'sender_ip':v.get('sender_ip'),'session':v['values'],'preview':self.preview.stats.get(v['key'],{}),'preview_key':v['key']} for port,v in self.live.items()]}

    async def start(self,c):
        if self.sockets:raise ValueError('Video receiver already listening; stop it before changing ports')
        if not tool_path('ffmpeg'):raise ValueError('FFmpeg is missing. Install FFmpeg and run Diagnostics.')
        opened={}
        try:
            for i in range(c.streams):
                port=c.base_port+2*i
                s=socket.socket(socket.AF_INET6 if ':' in c.address else socket.AF_INET,socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4*1024*1024);s.bind((c.address,port));s.setblocking(False);opened[port]=s
        except OSError as ex:
            for s in opened.values():s.close()
            raise ValueError(f'Cannot reserve receiver port: {ex}')
        self.config=c;self.sockets=opened;self.status='WAITING_FOR_STREAM';self.error=None;self.manual_id=None
        self.tasks={port:asyncio.create_task(self.listen(port,s)) for port,s in opened.items()}
        return self.snapshot()

    async def prepare(self,incoming):
        if not self.config or incoming.port not in self.sockets or incoming.transport!=self.config.transport:
            raise ValueError('Start the video receiver with matching ports and transport first')
        if incoming.port in self.live or incoming.port in self.prepared or incoming.port in self.reserved:raise ValueError('Receiver port already assigned to a session')
        uid=str(incoming.experiment_uuid)
        if uid not in self.experiments:
            # Local sender and receiver use distinct record UUIDs with an explicit shared correlation UUID.
            with Session() as db:exists=db.query(Experiment).filter_by(uuid=uid).first() is not None
            id,folder=create_experiment(incoming.name,{'role':'receiver','transport':incoming.transport,'execution_mode':incoming.execution_mode,'encoding_mode':incoming.encoding_mode,'correlation_uuid':uid,'receiver':self.config.address},system_info(),None if exists else uid)
            self.experiments[uid]=(id,folder)
        self.prepared[incoming.port]=incoming;self.reserved.add(incoming.port)
        try:await self.open_session(incoming.port,None)
        except BaseException:
            self.prepared.pop(incoming.port,None)
            finish_experiment(self.experiments[uid][0],'ERROR','Receiver decoder preparation failed')
            raise
        finally:self.reserved.discard(incoming.port)
        return {'status':'READY','session_uuid':str(incoming.session_uuid),'port':incoming.port}

    async def open_session(self,port,sender_ip):
        incoming=self.prepared.pop(port,None)
        if incoming:
            id,root=self.experiments[str(incoming.experiment_uuid)]
            values={'session_uuid':str(incoming.session_uuid),'experiment_uuid':str(incoming.experiment_uuid),
                    'video_id':str(incoming.video_id),'original_filename':incoming.original_filename,'stream_id':str(incoming.stream_id),
                    'source_bitrate':incoming.metadata.get('source_bps'),'target_bitrate':incoming.target_bps,'source_metadata':incoming.metadata}
        else:
            if self.manual_id is None:
                self.manual_id=create_experiment('Incoming video experiment',{'role':'receiver','transport':self.config.transport,'execution_mode':'manual','receiver':self.config.address,'base_port':self.config.base_port},system_info())
            id,root=self.manual_id
            values={'session_uuid':str(uuid.uuid4()),'video_id':None,'original_filename':'Unannounced stream','stream_id':str(uuid.uuid4()),'source_bitrate':None,'target_bitrate':None,'source_metadata':{}}
        values.update(port=port,transport=self.config.transport,status='WAITING_FOR_STREAM',started_at=now(),finished_at=None,role='receiver')
        folder=root/'sessions'/values['session_uuid'];folder.mkdir(parents=True,exist_ok=True)
        key='ffmpeg_receiver_'+str(id)+'_'+values['session_uuid']
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as reserve:
            reserve.bind(('127.0.0.1',0));local_port=reserve.getsockname()[1]
        process,tasks=await self.preview.start(key,local_port,folder)
        v={'id':id,'root':root,'folder':folder,'key':key,'values':values,'monitor':VideoNetworkMonitor('receiver',self.config.transport),
           'sender_ip':sender_ip,'last_recv':None,'last_sample':time.monotonic(),'rows':[],'tasks':tasks,'process':process,'local_port':local_port,'first':True}
        self.live[port]=v;save_session(id,values)
        await asyncio.sleep(.25)
        if process.returncode is not None:
            await self.finish_session(port,'ERROR')
            raise ValueError('FFmpeg preview decoder failed; inspect receiver log')
        return v

    async def listen(self,port,sock):
        loop=asyncio.get_running_loop();relay=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);relay.setblocking(False)
        try:
            while True:
                try:data,address=await asyncio.wait_for(loop.sock_recvfrom(sock,65535),.2)
                except asyncio.TimeoutError:
                    v=self.live.get(port)
                    if v:
                        if v['process'].returncode is not None:
                            self.error='Preview decoder exited; inspect ffmpeg_receiver.log';await self.finish_session(port,'ERROR');continue
                        if v['last_recv'] and time.monotonic()-v['last_recv']>self.config.idle_seconds:
                            await self.finish_session(port,'COMPLETED');continue
                        if v['last_recv'] and time.monotonic()-v['last_sample']>=.5:await self.sample(v)
                    continue
                v=self.live.get(port)
                if not v:v=await self.open_session(port,address[0])
                if v['sender_ip'] and v['sender_ip']!=address[0]:continue
                v['sender_ip']=address[0]
                if v['first']:
                    v['monitor'].started=v['monitor'].last=time.monotonic();v['first']=False
                    v['values'].update(status='RECEIVING',sender_ip=address[0],started_at=now());save_session(v['id'],v['values'])
                self.status='RECEIVING';v['last_recv']=time.monotonic()
                payload=v['monitor'].observe(data,v['last_recv'])
                if payload:await loop.sock_sendto(relay,payload,('127.0.0.1',v['local_port']))
                if time.monotonic()-v['last_sample']>=.5:await self.sample(v)
        except asyncio.CancelledError:raise
        except Exception as ex:
            self.error=str(ex)
            await self.finish_session(port,'ERROR')
            self.status='ERROR'
        finally:relay.close()

    async def sample(self,v):
        with Session() as db:experiment=db.get(Experiment,v['id']);offset=max(0,(datetime.fromisoformat(v['values']['started_at'])-datetime.fromisoformat(experiment.started_at)).total_seconds())
        row=v['monitor'].sample(v['values']['session_uuid'],offset);row.update(source_bps=v['values'].get('source_bitrate'),target_bps=v['values'].get('target_bitrate'))
        v['rows'].append(row);persist_sample(v['id'],row);v['last_sample']=time.monotonic()
        v['values'].update(v['monitor'].summary());save_session(v['id'],v['values'])
        await self.publish(v['id'],{'type':'measurement','measurement':row})

    async def finish_session(self,port,status='COMPLETED'):
        v=self.live.pop(port,None)
        if not v:return None
        if not v['first']:await self.sample(v)
        frozen_summary=v['monitor'].summary() if not v['first'] else {}
        await self.preview.stop(v['key'],v['tasks'])
        values=v['values'];values.update(frozen_summary)
        values.update(status=status,finished_at=now(),preview_frames=self.preview.stats.get(v['key'],{}).get('frames',0))
        save_session(v['id'],values)
        if status=='ERROR':finish_experiment(v['id'],'ERROR',self.error or 'Receiver decoder failed')
        (v['folder']/'metrics_receiver.csv').write_text(csv_rows(v['rows']))
        self.status='RECEIVING' if self.live else 'WAITING_FOR_STREAM'
        await self.publish(v['id'],{'type':'session','session':values})
        return values

    async def peer_finish(self,uid,sid,aborted=False):
        if uid not in self.experiments:raise ValueError('Unknown incoming experiment')
        for port,v in list(self.live.items()):
            if v['id']==self.experiments[uid][0] and v['values']['session_uuid']==sid:
                if not aborted:await asyncio.sleep(.4)
                result=await self.finish_session(port,'ABORTED' if aborted else 'COMPLETED')
                return self.session_result(self.experiments[uid][0],result)
        id,_=self.experiments[uid]
        with Session() as db:
            e=db.get(Experiment,id)
            result=next((s for s in e.sessions or [] if s['session_uuid']==sid),None)
        return self.session_result(id,result)

    async def peer_complete(self,uid,aborted=False):
        if uid not in self.experiments:raise ValueError('Unknown incoming experiment')
        id,folder=self.experiments[uid]
        for port,v in list(self.live.items()):
            if v['id']==id:await self.finish_session(port,'ABORTED' if aborted else 'COMPLETED')
        finish_experiment(id,'ABORTED' if aborted else 'COMPLETED')
        from .export_service import experiment_data
        data=experiment_data(id);(folder/'video_manifest.json').write_text(json.dumps({'experiment_uuid':uid,'videos':data['sessions']},indent=2))
        return data

    async def stop(self):
        if self.stop_task is None or self.stop_task.done():self.stop_task=asyncio.create_task(self._stop())
        return await asyncio.shield(self.stop_task)

    async def _stop(self):
        ongoing_ids={v['id'] for v in self.live.values()}
        tasks=list(self.tasks.values())
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        for port in list(self.live):await self.finish_session(port,'ABORTED')
        for s in self.sockets.values():s.close()
        for id,folder in list(self.experiments.values())+([self.manual_id] if self.manual_id else []):
            with Session() as db:e=db.get(Experiment,id);running=e and e.status=='RUNNING'
            if running:finish_experiment(id,'ABORTED' if id in ongoing_ids else 'COMPLETED')
        self.reserved.clear()
        self.tasks={};self.sockets={};self.prepared={};self.experiments={};self.live={};self.manual_id=None;self.status='STOPPED'
        return self.snapshot()

    async def stop_experiment(self,id):
        for port,v in list(self.live.items()):
            if v['id']==id:await self.finish_session(port,'ABORTED')
        finish_experiment(id,'ABORTED')

    def session_result(self,id,values):
        if not values:return None
        from .export_service import experiment_data
        e=experiment_data(id)
        return {**values,'measurements':[r for r in e['measurements'] if r.get('session_id')==values['session_uuid']]}

    def forget(self,id):
        self.experiments={uid:value for uid,value in self.experiments.items() if value[0]!=id}
        if self.manual_id and self.manual_id[0]==id:self.manual_id=None
        for key in list(self.preview.stats):
            if key.startswith('ffmpeg_receiver_'+str(id)+'_'):
                self.preview.stats.pop(key,None);self.preview.frames.pop(key,None);self.preview.events.pop(key,None)
