"""Single-copy UUID library. Raw request streaming prevents multipart spool exhaustion."""
import asyncio,os,uuid
from pathlib import PurePath
from fastapi import HTTPException
from ..core import ROOT
from ..database import Session
from .video_store import VideoAsset,asset_data,path_for,now
from .video_probe import VideoProbeService
EXTENSIONS={'.mp4','.avi','.mkv','.mov','.mpg','.mpeg'}
MAX_UPLOAD_BYTES=int(os.environ.get('LANCE_VIDEO_MAX_BYTES',str(2*1024**3)))
MAX_LIBRARY_BYTES=int(os.environ.get('LANCE_VIDEO_LIBRARY_BYTES',str(50*1024**3)))
UPLOAD_SLOTS=asyncio.Semaphore(2)
analysis_locks={}
LIBRARY_LOCK=asyncio.Lock()

async def upload(request,filename):
    if not filename or len(filename)>255 or '/' in filename or '\\' in filename or any(ord(c)<32 for c in filename) or filename in ('.','..'):
        raise HTTPException(422,'Invalid original filename')
    ext=PurePath(filename).suffix.lower()
    if ext not in EXTENSIONS:raise HTTPException(422,'Supported extensions: '+', '.join(sorted(EXTENSIONS)))
    mime=request.headers.get('content-type','').split(';')[0]
    if not (mime.startswith('video/') or mime in ('application/octet-stream','application/x-matroska')):raise HTTPException(415,'Expected video content type')
    length=request.headers.get('content-length')
    if length and int(length)>MAX_UPLOAD_BYTES:raise HTTPException(413,'Video exceeds upload limit')
    uid=str(uuid.uuid4());folder=ROOT/'data/videos';folder.mkdir(parents=True,exist_ok=True);path=folder/(uid+ext)
    async with UPLOAD_SLOTS:
        quota=sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
        size=0
        try:
            with path.open('xb') as stream:
                async for chunk in request.stream():
                    size+=len(chunk)
                    if size>MAX_UPLOAD_BYTES or sum(p.stat().st_size for p in folder.iterdir() if p.is_file())+len(chunk)>MAX_LIBRARY_BYTES:raise HTTPException(413,'Video/library size limit exceeded')
                    stream.write(chunk)
            metadata=await VideoProbeService().probe(path)
            metadata['size']=size
            with Session() as db:
                asset=VideoAsset(id=uid,original_filename=filename,internal_filename=path.name,created_at=now(),metadata_json=metadata,analysis=[])
                db.add(asset);db.commit();return asset_data(asset)
        except BaseException:
            path.unlink(missing_ok=True);raise

async def analyze(id,window):
    async with analysis_locks.setdefault(id,asyncio.Lock()):
        with Session() as db:
            asset=db.get(VideoAsset,id)
            if not asset:raise HTTPException(404,'Video not found')
            path=path_for(asset);duration=asset.metadata_json.get('duration')
        rows=await VideoProbeService().temporal(path,window,duration)
        with Session() as db:
            asset=db.get(VideoAsset,id);asset.analysis=rows;db.commit()
        return rows


def delete_videos(ids):
    """Validate the entire batch before removing files; retain historical sessions."""
    from ..database import Experiment
    ids=list(dict.fromkeys(ids))
    with Session() as db:
        assets=[db.get(VideoAsset,id) for id in ids]
        if any(asset is None for asset in assets):raise HTTPException(404,'Video not found; no videos deleted')
        active=db.query(Experiment).filter(Experiment.status.in_(['RUNNING','STARTING','STOPPING'])).all()
        protected=set()
        for experiment in active:
            protected.update(str(id) for id in experiment.config.get('video_ids',[]))
            protected.update(s.get('video_id') for s in experiment.sessions or [])
        if protected.intersection(ids):raise HTTPException(409,'Vídeo utilizado por um experimento em execução; nenhum vídeo excluído')
        if any(analysis_locks.get(id) and analysis_locks[id].locked() for id in ids):raise HTTPException(409,'Análise em execução; aguarde antes de excluir')
        paths=[path_for(asset) for asset in assets]
        moved=[]
        try:
            for path in paths:
                if path.exists():
                    temporary=path.with_name('.deleted-'+str(uuid.uuid4()))
                    path.rename(temporary);moved.append((path,temporary))
            for asset in assets:db.delete(asset)
            db.commit()
        except BaseException:
            db.rollback()
            for path,temporary in reversed(moved):temporary.rename(path)
            raise
        for path,temporary in moved:temporary.unlink(missing_ok=True)
    for id in ids:analysis_locks.pop(id,None)
    return {'deleted_ids':ids}
