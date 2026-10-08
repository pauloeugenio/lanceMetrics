"""Video API integrated into the existing authenticated FastAPI application."""
import asyncio,json,secrets,shutil
from uuid import UUID
from fastapi import APIRouter,HTTPException,Request,WebSocket,WebSocketDisconnect
from fastapi.responses import Response,FileResponse
from pydantic import BaseModel,Field
from .video_schemas import VideoConfig,ReceiverConfig,AnalysisConfig,IncomingSession
from .services.video_library import upload,analyze,delete_videos,LIBRARY_LOCK,MAX_UPLOAD_BYTES,MAX_LIBRARY_BYTES
from .services.video_store import library,csv_rows
from .services.export_service import experiment_data
from .core import ROOT

from .services.video_tools import tool_path

class DeleteVideosRequest(BaseModel):
    ids:list[UUID]=Field(min_length=1,max_length=100)

class FinishRequest(BaseModel):
    experiment_uuid:UUID
    session_uuid:UUID
    aborted:bool=False
class CompleteRequest(BaseModel):
    experiment_uuid:UUID
    aborted:bool=False

def video_router(generator,receiver,token,auth_enabled=True):
    router=APIRouter()
    def record(id):
        e=experiment_data(id)
        if not e or e['config'].get('experiment_type')!='video':raise HTTPException(404,'Video experiment not found')
        return e
    async def checked(fn,*args):
        try:return await fn(*args)
        except ValueError as ex:raise HTTPException(409,str(ex))
    @router.get('/api/video/status')
    def status():return {'ffmpeg':tool_path('ffmpeg') is not None,'ffprobe':tool_path('ffprobe') is not None,'receiver':receiver.snapshot(),
                        'active_experiments':[id for id,t in generator.tasks.items() if not t.done()],
                        'max_upload_bytes':MAX_UPLOAD_BYTES,'max_library_bytes':MAX_LIBRARY_BYTES}
    @router.get('/api/video/library')
    def assets():return library()
    @router.post('/api/video/library/delete')
    async def delete_selected(c:DeleteVideosRequest):
        async with LIBRARY_LOCK:return delete_videos([str(id) for id in c.ids])
    @router.delete('/api/video/library/{id}')
    async def delete_single(id:UUID):
        async with LIBRARY_LOCK:return delete_videos([str(id)])
    @router.post('/api/video/library/upload')
    async def upload_video(request:Request,filename:str):return await checked(upload,request,filename)
    @router.post('/api/video/library/{id}/analyze')
    async def analysis(id:UUID,c:AnalysisConfig):return await checked(analyze,str(id),c.window_seconds)
    @router.post('/api/video/experiments/start')
    async def start(c:VideoConfig):
        async with LIBRARY_LOCK:return await checked(generator.start,c)
    @router.post('/api/video/experiments/{id}/stop')
    async def stop(id:int):
        e=record(id)
        if e['config'].get('role')=='receiver':await receiver.stop_experiment(id)
        else:await generator.stop(id)
        return record(id)
    @router.post('/api/video/receiver/start')
    async def start_receiver(c:ReceiverConfig):return await checked(receiver.start,c)
    @router.post('/api/video/receiver/stop')
    async def stop_receiver():return await receiver.stop()
    @router.get('/api/video/peer/ready')
    def ready():return receiver.snapshot()
    @router.post('/api/video/peer/prepare')
    async def prepare(c:IncomingSession):return await checked(receiver.prepare,c)
    @router.post('/api/video/peer/finish')
    async def finish(c:FinishRequest):return await checked(receiver.peer_finish,str(c.experiment_uuid),str(c.session_uuid),c.aborted)
    @router.post('/api/video/peer/complete')
    async def complete(c:CompleteRequest):return await checked(receiver.peer_complete,str(c.experiment_uuid),c.aborted)
    @router.get('/api/video/experiments/{id}/export/{kind}')
    def export(id:int,kind:str,session_id:UUID|None=None):
        e=record(id);rows=e['measurements']
        if session_id:rows=[r for r in rows if r.get('session_id')==str(session_id)]
        if kind=='json':content=json.dumps(e,indent=2);ext='json'
        elif kind=='manifest':
            p=ROOT/'data/experiments'/e['uuid']/'video_manifest.json'
            content=p.read_text() if p.exists() else json.dumps({'experiment_uuid':e['uuid'],'videos':e['sessions']},indent=2);ext='json'
        elif kind=='sessions':content=csv_rows(e['sessions']);ext='csv'
        elif kind in ('metrics','sender','receiver'):
            if kind=='sender':rows=[r for r in rows if r.get('sender_bps') is not None]
            if kind=='receiver':rows=[r for r in rows if r.get('receiver_bps') is not None]
            if not rows:raise HTTPException(409,'No measured data available for this export')
            content=csv_rows(rows);ext='csv'
        elif kind=='source':
            sessions=[s for s in e['sessions'] if not session_id or s['session_uuid']==str(session_id)]
            rows=[]
            for s in sessions:
                p=ROOT/'data/experiments'/e['uuid']/'sessions'/s['session_uuid']/'source_bitrate.csv'
                if p.exists():
                    import csv,io
                    rows.extend({'session_uuid':s['session_uuid'],**row} for row in csv.DictReader(io.StringIO(p.read_text())))
            if not rows:raise HTTPException(409,'Analyze Temporal Bitrate before the experiment to export source windows')
            content=csv_rows(rows);ext='csv'
        elif kind=='combined':raise HTTPException(409,'Combined clock-aligned metrics require validated clock synchronization; export sender and receiver separately')
        else:raise HTTPException(422,'Unknown video export')
        return Response(content,media_type='application/json' if ext=='json' else 'text/csv',headers={'Content-Disposition':f'attachment; filename="LANCE_video_{id}_{kind}.{ext}"'})
    @router.get('/api/video/experiments/{id}/source-data')
    def source_data(id:int):
        import csv,io
        from datetime import datetime
        e=record(id);rows=[]
        for s in e['sessions']:
            p=ROOT/'data/experiments'/e['uuid']/'sessions'/s['session_uuid']/'source_bitrate.csv'
            if p.exists():
                offset=(datetime.fromisoformat(s['started_at'])-datetime.fromisoformat(e['started_at'])).total_seconds() if s.get('started_at') else 0
                for r in csv.DictReader(io.StringIO(p.read_text())):
                    rows.append({**r,'elapsed_time':float(r['elapsed_time']),'source_bps':float(r['source_bps']),'experiment_offset':offset,'session_id':s['session_uuid']})
        return rows
    @router.get('/api/video/experiments/{id}/sessions/{sid}/log/{role}')
    def log(id:int,sid:UUID,role:str):
        e=record(id)
        if role not in ('sender','receiver'):raise HTTPException(422,'Invalid role')
        if not any(s['session_uuid']==str(sid) for s in e['sessions']):raise HTTPException(404,'Session not found')
        p=ROOT/'data/experiments'/e['uuid']/'sessions'/str(sid)/('ffmpeg_'+role+'.log')
        if not p.is_file():raise HTTPException(404,'Log not available')
        return FileResponse(p,media_type='text/plain',filename=p.name)
    @router.websocket('/ws/video/preview/{port}')
    async def preview(ws:WebSocket,port:int):
        await ws.accept()
        try:
            if auth_enabled:
                auth=await asyncio.wait_for(ws.receive_json(),10)
                if not secrets.compare_digest(str(auth.get('token','')),token):await ws.close(1008);return
            previous=None
            while receiver.sockets and port in receiver.sockets:
                stream=receiver.live.get(port)
                frame=receiver.preview.frames.get(stream['key']) if stream else None
                if frame and frame is not previous:await ws.send_bytes(frame);previous=frame
                await asyncio.sleep(.1)
            await ws.close()
        except (WebSocketDisconnect,RuntimeError,asyncio.TimeoutError):pass
    return router
