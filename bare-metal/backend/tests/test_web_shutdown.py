import asyncio,json,os,shutil,socket,sqlite3,subprocess,sys,time,signal
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app import main

def test_shutdown_auth_and_idempotency(monkeypatch):
    calls=[]
    async def fake_shutdown():calls.append(True)
    monkeypatch.setattr(main,'shutdown_application',fake_shutdown)
    with TestClient(main.app) as client:
        assert client.post('/api/system/stop',json={}).status_code==401
        headers={'Authorization':'Bearer '+main.TOKEN}
        assert client.post('/api/system/stop',headers={**headers,'Origin':'https://other.example'},json={}).status_code==403
        first=client.post('/api/system/stop',headers=headers,json={})
        assert first.status_code==202 and first.json()['status']=='STOPPING'
        assert client.post('/api/system/stop',headers=headers,json={}).status_code==202
        assert calls==[True]
        assert client.post('/api/tests/start',headers=headers,json={'target':'localhost'}).status_code==503

def free_port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]
@pytest.mark.skipif(not shutil.which('iperf3'),reason='iperf3 unavailable')
def test_shutdown_real_uvicorn_and_children(tmp_path):
    import httpx,psutil
    from websockets.sync.client import connect
    port=free_port();iperfport=free_port();env={**os.environ,'LANCE_ROOT':str(tmp_path)}
    with (tmp_path/'backend.log').open('wb') as log:
        p=subprocess.Popen([sys.executable,'-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port',str(port),'--ws','websockets'],env=env,stdout=log,stderr=log)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=15) as c:
            for _ in range(100):
                try:
                    if c.get('/health').status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:pytest.fail('uvicorn startup failed: '+(tmp_path/'backend.log').read_text())
            c.headers['Authorization']='Bearer '+(tmp_path/'run/access.token').read_text().strip()
            s=c.post('/api/server/start',json={'address':'127.0.0.1','port':iperfport});assert s.status_code==200,s.text
            server_pid=s.json()['pid']
            e=c.post('/api/tests/start',json={'target':'127.0.0.1','port':iperfport,'duration':30}).json()
            time.sleep(.2)
            with connect(f'ws://127.0.0.1:{port}/ws/experiments/{e["id"]}') as ws:
                ws.send(json.dumps({'token':(tmp_path/'run/access.token').read_text().strip()}))
                assert json.loads(ws.recv())['type']=='snapshot'
                result=c.post('/api/system/stop',json={});assert result.status_code==202,result.text
                assert p.wait(timeout=10) in (0,-signal.SIGTERM)
        assert 'Application shutdown complete.' in (tmp_path/'backend.log').read_text()
        assert not psutil.pid_exists(server_pid)
        assert not list((tmp_path/'run').glob('iperf_*.json'))
        with sqlite3.connect(tmp_path/'data/lanceMetrics.sqlite') as db:
            assert db.execute('select status from experiments where id=?',(e['id'],)).fetchone()[0]=='STOPPED'
    finally:
        if p.poll() is None:p.terminate();p.wait(timeout=20)
