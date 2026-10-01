from sqlalchemy import create_engine, Column, Integer, String, JSON, ForeignKey, event
from sqlalchemy.orm import declarative_base, sessionmaker
from .core import ROOT
engine=create_engine('sqlite:///'+str(ROOT/'data/lanceMetrics.sqlite'),connect_args={'check_same_thread':False,'timeout':30})
@event.listens_for(engine,'connect')
def pragmas(db,record):
    db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA foreign_keys=ON')
Base=declarative_base()
class Experiment(Base):
    __tablename__='experiments'
    id=Column(Integer,primary_key=True)
    uuid=Column(String,unique=True,nullable=False)
    name=Column(String,nullable=False)
    status=Column(String,nullable=False)
    created_at=Column(String)
    started_at=Column(String)
    finished_at=Column(String)
    config=Column(JSON)
    environment=Column(JSON)
    summary=Column(JSON)
    sessions=Column(JSON,default=list)
    error=Column(String)
class Measurement(Base):
    __tablename__='measurements'
    id=Column(Integer,primary_key=True)
    experiment_id=Column(Integer,ForeignKey('experiments.id'),index=True)
    values=Column(JSON)
class StoredProfile(Base):
    __tablename__='profiles'
    id=Column(Integer,primary_key=True)
    definition=Column(JSON)
Session=sessionmaker(engine,expire_on_commit=False)
def init_db():
    from .services.video_store import VideoAsset,VideoSession
    Base.metadata.create_all(engine)
def serialize(e):
    return {c.name:getattr(e,c.name) for c in e.__table__.columns}
