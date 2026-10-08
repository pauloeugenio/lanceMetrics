import json
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app import main
from backend.app.video_api import video_router
from backend.app.video_schemas import VideoConfig
from backend.app.services.video_peer import VideoPeer


def test_auth_config_and_protected_mode():
    with TestClient(main.app) as client:
        assert client.get('/api/auth/config').json()=={'auth_enabled':True}
        assert client.get('/api/status').status_code==401
        assert client.get('/api/status',headers={'Authorization':'Bearer wrong'}).status_code==401


def test_no_auth_api_and_server_websocket(monkeypatch):
    monkeypatch.setattr(main,'AUTH_ENABLED',False)
    with TestClient(main.app) as client:
        assert client.get('/api/auth/config').json()=={'auth_enabled':False}
        assert client.get('/api/status').status_code==200
        # No initial token message is required.
        with client.websocket_connect('/ws/server') as ws:
            assert 'status' in ws.receive_json()
        # Same-origin protections remain effective when authentication is disabled.
        assert client.post('/api/video/receiver/stop',json={},headers={'Origin':'http://unrelated.example'}).status_code==403


def test_no_auth_preview_websocket():
    app=FastAPI()
    receiver=SimpleNamespace(sockets={5000:object()},live={5000:{'key':'test'}},preview=SimpleNamespace(frames={'test':b'frame'}))
    app.include_router(video_router(None,receiver,'unused',False))
    with TestClient(app) as client:
        with client.websocket_connect('/ws/video/preview/5000') as ws:
            assert ws.receive_bytes()==b'frame'


def test_peer_accepts_no_token_and_omits_authorization(monkeypatch):
    import asyncio,uuid
    from io import BytesIO
    config=VideoConfig(target='localhost',video_ids=[uuid.uuid4()],peer_url='http://localhost:8080')
    seen=[]
    class Opener:
        def open(self,request,timeout):
            seen.append(request)
            return BytesIO(json.dumps({'status':'WAITING_FOR_STREAM'}).encode())
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    result=asyncio.run(VideoPeer(config.peer_url,config.peer_token).call('ready'))
    assert result['status']=='WAITING_FOR_STREAM'
    assert not seen[0].has_header('Authorization')
