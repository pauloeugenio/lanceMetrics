import uuid
from fastapi.testclient import TestClient
from backend.app import main
from backend.app.database import Session,Experiment
from backend.app.services.video_store import VideoAsset,now,path_for
from backend.app.core import ROOT

HEADERS={'Authorization':'Bearer '+main.TOKEN}

def asset():
    uid=str(uuid.uuid4())
    folder=ROOT/'data/videos';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(uid+'.mp4');path.write_bytes(b'video')
    with Session() as db:
        db.add(VideoAsset(id=uid,original_filename='delete-test.mp4',internal_filename=path.name,created_at=now(),metadata_json={'duration':1},analysis=[]));db.commit()
    return uid,path

def test_delete_single_and_batch_preserve_history():
    with TestClient(main.app) as client:
        a,pa=asset();b,pb=asset();c,pc=asset()
        with Session() as db:
            e=Experiment(uuid=str(uuid.uuid4()),name='Historical video',status='COMPLETED',created_at=now(),config={'experiment_type':'video','video_ids':[a]},sessions=[{'video_id':a}],summary={'bytes_sent':10})
            db.add(e);db.commit();eid=e.id
        assert client.delete('/api/video/library/'+a).status_code==401
        assert client.delete('/api/video/library/'+a,headers=HEADERS).json()=={'deleted_ids':[a]}
        assert not pa.exists()
        response=client.post('/api/video/library/delete',headers=HEADERS,json={'ids':[b,c,b]})
        assert response.status_code==200 and response.json()['deleted_ids']==[b,c]
        assert not pb.exists() and not pc.exists()
        with Session() as db:
            assert db.get(VideoAsset,a) is None and db.get(VideoAsset,b) is None
            assert db.get(Experiment,eid).summary=={'bytes_sent':10}

def test_batch_missing_or_active_video_removes_nothing():
    with TestClient(main.app) as client:
        a,pa=asset();b,pb=asset()
        assert client.post('/api/video/library/delete',headers=HEADERS,json={'ids':[a,str(uuid.uuid4())]}).status_code==404
        assert pa.exists()
        with Session() as db:
            e=Experiment(uuid=str(uuid.uuid4()),name='Active video',status='RUNNING',created_at=now(),config={'experiment_type':'video','video_ids':[b]},sessions=[],summary={})
            db.add(e);db.commit();eid=e.id
        assert client.post('/api/video/library/delete',headers=HEADERS,json={'ids':[a,b]}).status_code==409
        assert pa.exists() and pb.exists()
        assert client.delete('/api/video/library/'+b,headers=HEADERS).status_code==409
        with Session() as db:
            db.get(Experiment,eid).status='ABORTED';db.commit()
        assert client.post('/api/video/library/delete',headers=HEADERS,json={'ids':[]}).status_code==422
        assert client.delete('/api/video/library/not-a-uuid',headers=HEADERS).status_code==422
