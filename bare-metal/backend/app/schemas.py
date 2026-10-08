import ipaddress, re
from typing import Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict

def host(value):
    try: ipaddress.ip_address(value); return value
    except ValueError: pass
    if len(value)>253 or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', p) for p in value.rstrip('.').split('.')):
        raise ValueError('Invalid IP address or hostname')
    if re.fullmatch(r'[0-9.]+',value): raise ValueError('Invalid IP address')
    return value

class Stage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    duration: int = Field(ge=1,le=3600)
    bandwidth_mbps: float = Field(gt=0,le=100000,allow_inf_nan=False)
class Profile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1,max_length=100)
    protocol: Literal['udp','tcp'] = 'udp'
    intervals: list[Stage] = Field(min_length=1,max_length=100)
    @field_validator('intervals')
    @classmethod
    def total(cls,v):
        if sum(x.duration for x in v)>86400: raise ValueError('Profile exceeds 24 hours')
        return v
class TestConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(default='Network experiment',min_length=1,max_length=100)
    description: str = Field(default='',max_length=2000)
    target: str
    port: int = Field(default=5201,ge=1024,le=65535)
    protocol: Literal['tcp','udp'] = 'udp'
    duration: int = Field(default=10,ge=1,le=3600)
    report_interval: float = Field(default=1,ge=0.1,le=60,allow_inf_nan=False)
    bandwidth_mbps: float = Field(default=10,gt=0,le=100000,allow_inf_nan=False)
    parallel_streams: int = Field(default=1,ge=1,le=32)
    reverse_mode: bool = False
    datagram_length: int | None = Field(default=None,ge=16,le=65507)
    profile_id: int | None = None
    _host = field_validator('target')(host)
class ServerConfig(BaseModel):
    address: str = '0.0.0.0'
    port: int = Field(default=5201,ge=1024,le=65535)
    @field_validator('address')
    @classmethod
    def address_valid(cls,v): return str(ipaddress.ip_address(v))
