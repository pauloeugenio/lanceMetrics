import asyncio,json,logging,os,secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException,UploadFile,File,WebSocket,WebSocketDisconnect,Request
from fastapi.responses import Response,FileResponse
from fastapi.staticfiles import StaticFiles
from .core import ROOT,VERSION
from .database import init_db,Session,Experiment,StoredProfile,serialize
from .schemas import TestConfig,ServerConfig,Profile
from .services.system_service import system_info,iperf_info
from .services.process_manager import ProcessManager
from .services.iperf_runner import IperfRunner,now
from .services.export_service import experiment_data,csv_export,filename
manager=ProcessManager(); runner=IperfRunner(manager)
log=logging.getLogger(__name__)
tokenfile=ROOT/'run/access.token'
if not tokenfile.exists():
    tokenfile.write_text(secrets.token_urlsafe(32)); tokenfile.chmod(0o600)
TOKEN=tokenfile.read_text().strip()
@asynccontextmanager
async def lifespan(app):
    init_db()
    with Session() as db:
        for e in db.query(Experiment).filter_by(status='RUNNING'): e.status='INTERRUPTED'; e.finished_at=now()
        db.commit()
    log.info('application start version=%s',VERSION)
    yield
    await runner.shutdown(); log.info('application stop')
app=FastAPI(title='LANCE Metrics',version=VERSION,lifespan=lifespan)
@app.middleware('http')
async def access(request:Request,call_next):
    if request.url.path.startswith('/api/') and request.headers.get('Authorization')!='Bearer '+TOKEN:
        return Response('Access token required',status_code=401)
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
            return Response('Cross-origin mutation refused',status_code=403)
    return await call_next(request)
@app.get('/health')
def health(): return {'status':'ok','version':VERSION}
@app.get('/api/status')
def status():
    return {'version':VERSION,'iperf':iperf_info(),'server':runner.server,'active_experiments':[id for id,t in runner.tasks.items() if not t.done()]}
@app.get('/api/system')
def system(): return system_info()
@app.post('/api/server/start')
async def server_start(c:ServerConfig):
    try: return await runner.start_server(c)
    except ValueError as ex: raise HTTPException(409,str(ex))
@app.post('/api/server/stop')
async def server_stop(): await runner.stop_server(); return runner.server
@app.post('/api/tests/start')
async def test_start(c:TestConfig):
    profile=None
    if c.profile_id:
        with Session() as db:
            p=db.get(StoredProfile,c.profile_id)
            if not p: raise HTTPException(404,'Profile not found')
            profile=p.definition
            c=c.model_copy(update={'protocol':profile['protocol']})
    try: return await runner.start(c,profile)
    except ValueError as ex: raise HTTPException(409,str(ex))
@app.post('/api/tests/{id}/stop')
async def test_stop(id:int):
    if not experiment_data(id): raise HTTPException(404,'Experiment not found')
    await runner.stop(id); return experiment_data(id)
@app.get('/api/experiments')
def experiments():
    with Session() as db: return [serialize(e) for e in db.query(Experiment).order_by(Experiment.id.desc())]
@app.get('/api/experiments/{id}')
def experiment(id:int):
    result=experiment_data(id)
    if result is None: raise HTTPException(404,'Experiment not found')
    return result
@app.get('/api/experiments/{id}/metrics')
def metrics(id:int): return experiment(id)['measurements']
@app.get('/api/experiments/{id}/raw')
def raw(id:int):
    e=experiment(id); folder=ROOT/'data/experiments'/e['uuid']
    return {p.name:p.read_text(errors='replace') for p in sorted(folder.glob('*')) if p.suffix in ('.stdout','.stderr') or p.name=='server.json'}
@app.get('/api/experiments/{id}/export/{format}')
def export(id:int,format:str):
    e=experiment(id)
    if format not in ('json','csv'): raise HTTPException(400,'Supported formats: csv, json')
    log.info('export experiment=%s format=%s',id,format)
    return Response(json.dumps(e,indent=2) if format=='json' else csv_export(e),media_type='application/json' if format=='json' else 'text/csv',headers={'Content-Disposition':f'attachment; filename="{filename(e,format)}"'})
@app.get('/api/profiles')
def profiles():
    with Session() as db: return [{'id':p.id,**p.definition} for p in db.query(StoredProfile)]
@app.get('/api/profiles/{id}')
def profile(id:int):
    with Session() as db:
        p=db.get(StoredProfile,id)
        if not p: raise HTTPException(404,'Profile not found')
        return {'id':id,**p.definition}
def save_profile(p):
    with Session() as db:
        s=StoredProfile(definition=p.model_dump()); db.add(s); db.commit(); id=s.id
    (ROOT/'data/profiles'/f'{id}.json').write_text(p.model_dump_json(indent=2))
    return {'id':id,**p.model_dump()}
@app.post('/api/profiles')
def create_profile(p:Profile): return save_profile(p)
@app.post('/api/profiles/upload')
async def upload_profile(file:UploadFile=File(...)):
    data=await file.read(1024*1024+1)
    if len(data)>1024*1024: raise HTTPException(413,'Profile exceeds 1 MB')
    try: return save_profile(Profile.model_validate_json(data))
    except ValueError as ex: raise HTTPException(422,str(ex))
@app.websocket('/ws/experiments/{id}')
async def websocket(ws:WebSocket,id:int):
    await ws.accept()
    # First message authenticates: avoids putting credentials in URLs/logs.
    try:
        auth=await asyncio.wait_for(ws.receive_json(),10)
        if not secrets.compare_digest(str(auth.get('token','')),TOKEN): await ws.close(1008); return
        if not experiment_data(id): await ws.close(1008); return
        queue=asyncio.Queue(maxsize=100); runner.listeners.setdefault(id,set()).add(queue)
        await ws.send_json({'type':'snapshot','experiment':experiment_data(id)})
        while True:
            try: event=await asyncio.wait_for(queue.get(),20)
            except asyncio.TimeoutError: event={'type':'heartbeat'}
            await ws.send_json(event)
    except (WebSocketDisconnect,RuntimeError,asyncio.TimeoutError): pass
    finally:
        if 'queue' in locals(): runner.listeners.get(id,set()).discard(queue)
@app.websocket('/ws/server')
async def server_ws(ws:WebSocket):
    await ws.accept()
    try:
        auth=await asyncio.wait_for(ws.receive_json(),10)
        if not secrets.compare_digest(str(auth.get('token','')),TOKEN): await ws.close(1008); return
        previous=None
        while True:
            current=json.dumps(runner.server)
            if current!=previous: await ws.send_json(runner.server); previous=current
            else: await ws.send_json({'heartbeat':True})
            await asyncio.sleep(2)
    except (WebSocketDisconnect,RuntimeError,asyncio.TimeoutError): pass
build=ROOT/'frontend/dist'
if build.exists():
    app.mount('/assets',StaticFiles(directory=build/'assets'),name='assets')
    @app.get('/{path:path}')
    def frontend(path:str): return FileResponse(build/'index.html')
