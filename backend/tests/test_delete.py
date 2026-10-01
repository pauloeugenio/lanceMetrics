import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app,TOKEN
from backend.app.database import Session,Experiment,Measurement
from backend.app.core import ROOT
from backend.app.services.experiment_service import delete_experiments,DeletionError
H={'Authorization':'Bearer '+TOKEN}
def seed(status='COMPLETED'):
    with Session() as db:
        e=Experiment(uuid=str(uuid.uuid4()),name='Delete validation',status=status,config={},environment={},summary={},sessions=[])
        db.add(e);db.commit();db.add(Measurement(experiment_id=e.id,values={'sender_bps':123}));db.commit();id=e.id;uid=e.uuid
    folder=ROOT/'data/experiments'/uid;folder.mkdir();(folder/'stage_0.stdout').write_text('preserved raw')
    return id,folder

def test_delete_single_authenticated_with_raw_and_measurements():
    with TestClient(app) as c:
        id,folder=seed()
        assert c.delete(f'/api/experiments/{id}').status_code==401
        assert c.delete(f'/api/experiments/{id}',headers={**H,'Origin':'https://evil.example'}).status_code==403
        result=c.delete(f'/api/experiments/{id}',headers=H)
        assert result.status_code==200 and result.json()['deleted_ids']==[id]
        assert not folder.exists()
        assert c.get(f'/api/experiments/{id}',headers=H).status_code==404
        with Session() as db:assert db.query(Measurement).filter_by(experiment_id=id).count()==0

def test_bulk_deletion_is_atomic_for_running_or_missing():
    with TestClient(app) as c:
        a,fa=seed();b,fb=seed('RUNNING')
        assert c.post('/api/experiments/delete',headers=H,json={'ids':[a,b]}).status_code==409
        assert fa.exists() and fb.exists() and c.get(f'/api/experiments/{a}',headers=H).status_code==200
        assert c.post('/api/experiments/delete',headers=H,json={'ids':[a,999999999]}).status_code==404
        assert fa.exists()
        d,fd=seed()
        result=c.post('/api/experiments/delete',headers=H,json={'ids':[a,d,a]})
        assert result.status_code==200 and result.json()['count']==2
        assert not fa.exists() and not fd.exists() and fb.exists()
        for ids in ([],[-1]):assert c.post('/api/experiments/delete',headers=H,json={'ids':ids}).status_code==422

def test_finished_but_active_task_cannot_be_deleted():
    id,folder=seed()
    with pytest.raises(DeletionError):delete_experiments([id],{id})
    assert folder.exists()

def test_failed_database_commit_restores_raw_files(monkeypatch):
    id,folder=seed()
    def fail(*args,**kwargs):raise OSError('simulated database failure')
    with monkeypatch.context() as patch:
        patch.setattr(Session.class_,'commit',fail)
        with pytest.raises(OSError):delete_experiments([id],set())
    assert (folder/'stage_0.stdout').read_text()=='preserved raw'
    with Session() as db:assert db.get(Experiment,id) is not None

def test_symlink_cannot_delete_external_files(tmp_path):
    id,folder=seed();(folder/'stage_0.stdout').unlink();folder.rmdir()
    sentinel=tmp_path/'sentinel';sentinel.mkdir();(sentinel/'keep').write_text('keep')
    folder.symlink_to(sentinel,target_is_directory=True)
    with pytest.raises(DeletionError):delete_experiments([id],set())
    assert (sentinel/'keep').read_text()=='keep'
    folder.unlink()
