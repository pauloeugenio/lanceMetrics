"""Validated video configuration, independent from synthetic traffic settings."""
import ipaddress
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from .schemas import host

class VideoConfig(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(default='Video streaming experiment',min_length=1,max_length=100)
    target:str
    base_port:int=Field(default=5000,ge=1024,le=65535)
    transport:Literal['udp','rtp']='udp'
    playback:Literal['realtime','maximum']='realtime'
    execution_mode:Literal['sequential','concurrent']='sequential'
    encoding_mode:Literal['preserve','controlled']='preserve'
    codec:Literal['h264']='h264'
    preset:Literal['ultrafast','superfast','veryfast']='ultrafast'
    low_latency:bool=True
    target_mbps:float=Field(default=10,gt=0,le=100000,allow_inf_nan=False)
    resolution:Literal['source','640x360','1280x720','1920x1080']='source'
    output_fps:int|None=Field(default=None,ge=1,le=120)
    keyframe_frames:int|None=Field(default=None,ge=1,le=600)
    include_audio:bool=True
    video_ids:list[UUID]=Field(min_length=1,max_length=100)
    peer_url:str|None=None
    peer_token:str|None=Field(default=None,max_length=256,exclude=True)
    _host=field_validator('target')(host)
    @field_validator('peer_url')
    @classmethod
    def peer(cls,v):
        if v:
            from urllib.parse import urlsplit
            p=urlsplit(v)
            if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.path not in ('','/') or p.query or p.fragment:
                raise ValueError('Peer URL must be http(s)://host:port without credentials or path')
            host(p.hostname)
            if p.port is not None and not 1<=p.port<=65535:raise ValueError('Invalid peer port')
            return v.rstrip('/')
        return None
    @model_validator(mode='after')
    def queue(self):
        if len(set(self.video_ids))!=len(self.video_ids):raise ValueError('Duplicate video IDs in queue')
        if self.execution_mode=='concurrent' and self.base_port+2*(len(self.video_ids)-1)>65535:raise ValueError('Port allocation exceeds 65535')
        if self.encoding_mode=='preserve' and (self.resolution!='source' or self.output_fps is not None or self.keyframe_frames is not None):
            raise ValueError('Resolution, FPS and keyframe settings require Controlled Bitrate encoding')
        return self

class ReceiverConfig(BaseModel):
    model_config=ConfigDict(extra='forbid')
    address:str='0.0.0.0'
    base_port:int=Field(default=5000,ge=1024,le=65535)
    streams:int=Field(default=1,ge=1,le=100)
    transport:Literal['udp','rtp']='udp'
    idle_seconds:float=Field(default=2,ge=1,le=30,allow_inf_nan=False)
    @field_validator('address')
    @classmethod
    def address_valid(cls,v):return str(ipaddress.ip_address(v))
    @model_validator(mode='after')
    def ports(self):
        if self.base_port+2*(self.streams-1)>65535:raise ValueError('Port allocation exceeds 65535')
        return self

class AnalysisConfig(BaseModel):
    window_seconds:float=Field(default=1,ge=.1,le=60,allow_inf_nan=False)

class IncomingSession(BaseModel):
    model_config=ConfigDict(extra='forbid')
    experiment_uuid:UUID
    session_uuid:UUID
    stream_id:UUID
    video_id:UUID
    name:str=Field(max_length=100)
    original_filename:str=Field(min_length=1,max_length=255)
    port:int=Field(ge=1024,le=65535)
    transport:Literal['udp','rtp']
    metadata:dict=Field(default_factory=dict)
    target_bps:float|None=Field(default=None,gt=0,allow_inf_nan=False)
    encoding_mode:Literal['preserve','controlled']='preserve'
    execution_mode:Literal['sequential','concurrent']='sequential'
