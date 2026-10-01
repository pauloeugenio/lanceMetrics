"""Video records share Experiment/Measurement and their existing exports/history."""
import csv,io,json,uuid
from datetime import datetime,timezone
from sqlalchemy import Column,Integer,String,JSON,ForeignKey
from ..database import Base,Session,Experiment,Measurement
from ..core import ROOT

class VideoAsset(Base):
    __tablename__='video_assets'
    id=Column(String,primary_key=True)
    original_filename=Column(String,nullable=False)
    internal_filename=Column(String,nullable=False)
    created_at=Column(String,nullable=False)
    metadata_json=Column(JSON,nullable=False)
    analysis=Column(JSON,default=list)

class VideoSession(Base):
    __tablename__='video_sessions'
    id=Column(String,primary_key=True)
    experiment_id=Column(Integer,ForeignKey('experiments.id',ondelete='CASCADE'),index=True,nullable=False)
    video_id=Column(String)
    values=Column(JSON,nullable=False)

def now():return datetime.now(timezone.utc).isoformat()
def asset_data(asset):return {'id':asset.id,'original_filename':asset.original_filename,'created_at':asset.created_at,**asset.metadata_json,'analysis':asset.analysis or [],'status':'Ready'}
def library():
    with Session() as db:return [asset_data(a) for a in db.query(VideoAsset).order_by(VideoAsset.created_at)]
def path_for(asset):
    path=ROOT/'data/videos'/asset.internal_filename
    if path.parent.resolve()!=(ROOT/'data/videos').resolve() or path.is_symlink():raise ValueError('Invalid library path')
    return path

def create_experiment(name,config,environment,experiment_uuid=None):
    with Session() as db:
        e=Experiment(uuid=experiment_uuid or str(uuid.uuid4()),name=name,status='RUNNING',created_at=now(),started_at=now(),config={'experiment_type':'video',**config},environment=environment,summary={},sessions=[])
        db.add(e);db.commit();id=e.id;uid=e.uuid
    folder=ROOT/'data/experiments'/uid
    try:
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'config.json').write_text(json.dumps(config,indent=2))
        role=config.get('role','sender');(folder/f'environment_{role}.json').write_text(json.dumps(environment,indent=2))
    except Exception as ex:
        finish_experiment(id,'ERROR','Experiment setup failed: '+str(ex))
        raise ValueError('Experiment setup failed: '+str(ex)) from ex
    return id,folder

def save_session(experiment_id,values):
    with Session() as db:
        e=db.get(Experiment,experiment_id)
        if not e:return
        # A sender and receiver localhost may share UUID: database identity remains role-specific.
        row_id=values['session_uuid']+'-'+str(experiment_id)
        row=db.get(VideoSession,row_id)
        if row:row.values=dict(values)
        else:db.add(VideoSession(id=row_id,experiment_id=experiment_id,video_id=values.get('video_id'),values=dict(values)))
        sessions=list(e.sessions or [])
        index=next((i for i,s in enumerate(sessions) if s['session_uuid']==values['session_uuid']),None)
        if index is None:sessions.append(dict(values))
        else:sessions[index]=dict(values)
        e.sessions=sessions;db.commit();folder=ROOT/'data/experiments'/e.uuid/'sessions'/values['session_uuid']
    folder.mkdir(parents=True,exist_ok=True);(folder/'metadata.json').write_text(json.dumps(values,indent=2))

def persist_sample(experiment_id,row):
    with Session() as db:db.add(Measurement(experiment_id=experiment_id,values=dict(row)));db.commit()

def aggregate(sessions,wall_duration):
    def summed(key):
        values=[s.get(key) for s in sessions]
        return sum(values) if values and all(v is not None for v in values) else None
    result={'videos_tested':len([s for s in sessions if s.get('started_at')]),'total_duration':wall_duration,
            'bytes_sent':summed('bytes_sent'),'bytes_received':summed('bytes_received'),
            'packets_sent':summed('packets_sent'),'packets_received':summed('packets_received'),
            'packets_lost':summed('packets_lost'),'packets_expected':summed('packets_expected'),'jitter_ms':None}
    for role,key in [('sender','bytes_sent'),('receiver','bytes_received')]:
        result[role+'_bps']=result[key]*8/wall_duration if result[key] is not None and wall_duration>0 else None
    # Aggregate over wall time counts concurrent streams once, includes queue transition gaps.
    result['loss_percent']=100*result['packets_lost']/result['packets_expected'] if result['packets_expected'] else None
    weights=[s for s in sessions if s.get('jitter') is not None and s.get('packets_received')]
    if len(weights)==len(sessions) and weights:
        result['jitter_ms']=sum(s['jitter']*s['packets_received'] for s in weights)/sum(s['packets_received'] for s in weights)
    return result

def finish_experiment(id,status,error=None):
    with Session() as db:
        e=db.get(Experiment,id)
        if not e:return
        e.status=status;e.finished_at=now();e.error=error
        seconds=max(.000001,(datetime.fromisoformat(e.finished_at)-datetime.fromisoformat(e.started_at)).total_seconds())
        e.summary=aggregate(e.sessions or [],seconds);db.commit()

def csv_rows(rows):
    out=io.StringIO();fields=list(dict.fromkeys(k for row in rows for k in row)) or ['elapsed_time','seconds','source_bps']
    writer=csv.DictWriter(out,fields);writer.writeheader();writer.writerows(rows);return out.getvalue()
