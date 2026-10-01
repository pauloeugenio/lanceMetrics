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
