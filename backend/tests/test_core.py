import asyncio,json,shutil,socket,time
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from backend.app.schemas import TestConfig as Config,Profile,ServerConfig
from backend.app.services.iperf_runner import IperfCommandBuilder
from backend.app.services.iperf_parser import IperfParser
from backend.app.services.process_manager import ProcessManager
from backend.app.main import app,TOKEN
from backend.app.core import ROOT
from backend.app.database import Session,Experiment

@pytest.mark.parametrize('target',['127.0.0.1','::1','lab.example.org','localhost'])
def test_host(target):assert Config(target=target).target==target
@pytest.mark.parametrize('target',[';touch /tmp/bad','-x','999.12.3.4','a b','$(whoami)','foo..bar'])
def test_invalid_host(target):
    with pytest.raises(ValidationError):Config(target=target)
@pytest.mark.parametrize('field,value',[('port',0),('port',65536),('duration',0),('bandwidth_mbps',0),('report_interval',0),('parallel_streams',33),('bandwidth_mbps',float('nan'))])
def test_invalid_config(field,value):
    with pytest.raises(ValidationError):Config(target='localhost',**{field:value})
def test_profile():
    p=Profile(name='Variable',intervals=[{'duration':10,'bandwidth_mbps':10}]);assert p.intervals[0].duration==10
    for invalid in [{'name':'a','intervals':[]},{'name':'a','protocol':'icmp','intervals':[{'duration':10,'bandwidth_mbps':10}]},{'name':'a','intervals':[{'duration':0,'bandwidth_mbps':-1}]}]:
        with pytest.raises(ValidationError):Profile(**invalid)
def test_command():
    c=Config(target='localhost',reverse_mode=True,parallel_streams=2,datagram_length=1200)
    args=IperfCommandBuilder.client(c,'session');assert '-R' in args and '-u' in args and args[args.index('-b')+1]=='10000000';assert '-J' in args
    assert '--json-stream' in IperfCommandBuilder.client(c,'id',True)
def test_parser_provenance():
    sender={'bits_per_second':100,'bytes':20,'packets':10,'jitter_ms':999,'lost_packets':999}
    s=IperfParser.row(sender,True,'udp');assert s['jitter_ms'] is None and s['packets_sent']==10 and s['receiver_bps'] is None
    receiver={**sender,'packets':10,'lost_packets':2,'jitter_ms':.3,'lost_percent':20}
    r=IperfParser.row(receiver,False,'udp');assert r['packets_received']==8 and r['packets_lost']==2 and r['sender_bps'] is None
    result=IperfParser.summary({'end':{'sum_sent':sender,'sum_received':receiver}},'udp');assert result['sender_bps']==100 and result['jitter_ms']==.3
    local=IperfParser.summary({'end':{'sum_sent':sender,'sum_received':receiver}},'udp','receiver')
    assert local['sender_bps'] is None and local['packets_sent'] is None and local['receiver_bps']==100
    assert all(v is None for v in IperfParser.summary({},'tcp').values())
def test_ambiguous_old_udp():
    r=IperfParser.summary({'end':{'sum':{'bits_per_second':10,'jitter_ms':2,'packets':3,'lost_packets':1}}},'udp')
    assert r['sender_bps'] is None and r['receiver_bps'] is None and r['jitter_ms']==2

def test_api():
    with TestClient(app) as client:
        headers={'Authorization':'Bearer '+TOKEN}
        assert client.get('/api/status').status_code==401
        assert client.get('/health').status_code==200
        assert client.get('/api/system',headers=headers).status_code==200
        assert client.post('/api/tests/start',headers=headers,json={'target':'bad;cmd'}).status_code==422
        assert client.get('/api/experiments/9999',headers=headers).status_code==404
        assert client.post('/api/server/start',headers={**headers,'Origin':'https://evil.example'},json={}).status_code==403
        p=client.post('/api/profiles',headers=headers,json={'name':'Saved','protocol':'udp','intervals':[{'duration':1,'bandwidth_mbps':1}]}).json()
        assert client.get('/api/profiles/'+str(p['id']),headers=headers).json()['name']=='Saved'
        assert client.post('/api/profiles/upload',headers=headers,files={'file':('bad.json',b'{}','application/json')}).status_code==422

def test_process_manager():
    async def check():
        import sys
        m=ProcessManager();p=await m.spawn('test_child',[sys.executable,'-c','import time;time.sleep(60)'])
        assert (ROOT/'run/test_child.json').exists();await m.stop('test_child');assert p.returncode is not None and not (ROOT/'run/test_child.json').exists()
    asyncio.run(check())

@pytest.mark.skipif(not shutil.which('iperf3'),reason='iperf3 not installed')
@pytest.mark.parametrize('protocol,reverse',[('tcp',False),('udp',False),('udp',True)])
def test_real_iperf(protocol,reverse):
    s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
    headers={'Authorization':'Bearer '+TOKEN}
    with TestClient(app) as client:
        response=client.post('/api/server/start',headers=headers,json={'address':'127.0.0.1','port':port});assert response.status_code==200,response.text
        config={'target':'127.0.0.1','port':port,'protocol':protocol,'duration':1,'bandwidth_mbps':1,'reverse_mode':reverse}
        e=client.post('/api/tests/start',headers=headers,json=config);assert e.status_code==200,e.text
        id=e.json()['id']
        for _ in range(100):
            result=client.get(f'/api/experiments/{id}',headers=headers).json()
            if result['status']!='RUNNING':break
            time.sleep(.1)
        assert result['status']=='COMPLETED',result
        assert result['summary']['sender_bps']>0 and result['summary']['receiver_bps']>0
        assert result['measurements']
        if protocol=='udp':assert result['summary']['jitter_ms'] is not None and result['summary']['packets_received']>0
        assert client.get(f'/api/experiments/{id}/export/csv',headers=headers).text.startswith('experiment_uuid,')
        assert client.get(f'/api/experiments/{id}/export/json',headers=headers).json()['uuid']==result['uuid']
        assert client.get(f'/api/experiments/{id}/raw',headers=headers).json()
        assert client.post('/api/server/stop',headers=headers,json={}).json()['status']=='STOPPED'
        observed=client.get('/api/experiments',headers=headers).json()
        assert any(e['config'].get('mode')=='server' for e in observed)

@pytest.mark.skipif(not shutil.which('iperf3'),reason='iperf3 not installed')
def test_real_profile_and_stop():
    s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close();headers={'Authorization':'Bearer '+TOKEN}
    with TestClient(app) as c:
        assert c.post('/api/server/start',headers=headers,json={'address':'127.0.0.1','port':port}).status_code==200
        p=c.post('/api/profiles',headers=headers,json={'name':'Two stages','protocol':'udp','intervals':[{'duration':1,'bandwidth_mbps':1},{'duration':1,'bandwidth_mbps':2}]}).json()
        e=c.post('/api/tests/start',headers=headers,json={'target':'127.0.0.1','port':port,'profile_id':p['id']}).json()
        with c.websocket_connect('/ws/experiments/'+str(e['id'])) as ws:
            ws.send_json({'token':TOKEN});assert ws.receive_json()['type']=='snapshot'
        for _ in range(100):
            result=c.get('/api/experiments/'+str(e['id']),headers=headers).json()
            if result['status']!='RUNNING':break
            time.sleep(.1)
        assert result['status']=='COMPLETED',result
        assert len(result['sessions'])==2
        assert {r['stage_id'] for r in result['measurements']}=={0,1}
        e=c.post('/api/tests/start',headers=headers,json={'target':'127.0.0.1','port':port,'duration':30}).json()
        time.sleep(.2)
        result=c.post(f'/api/tests/{e["id"]}/stop',headers=headers,json={}).json();assert result['status']=='STOPPED'
        c.post('/api/server/stop',headers=headers,json={})
        assert not list((ROOT/'run').glob('iperf_*.json'))

@pytest.mark.skipif(not shutil.which('iperf3'),reason='iperf3 not installed')
def test_connection_refused_preserves_raw():
    s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close();headers={'Authorization':'Bearer '+TOKEN}
    with TestClient(app) as c:
        e=c.post('/api/tests/start',headers=headers,json={'target':'127.0.0.1','port':port,'duration':1}).json()
        for _ in range(70):
            result=c.get('/api/experiments/'+str(e['id']),headers=headers).json()
            if result['status']!='RUNNING':break
            time.sleep(.1)
        assert result['status']=='ERROR' and result['error']
        raw=c.get(f'/api/experiments/{e["id"]}/raw',headers=headers).json();assert 'stage_0.stdout' in raw
        assert not list((ROOT/'run').glob('iperf_client_*.json'))

@pytest.mark.skipif(not shutil.which('iperf3'),reason='iperf3 not installed')
def test_occupied_port_and_duplicate_server():
    s=socket.socket();s.bind(('127.0.0.1',0));s.listen();port=s.getsockname()[1];headers={'Authorization':'Bearer '+TOKEN}
    with TestClient(app) as c:
        response=c.post('/api/server/start',headers=headers,json={'address':'127.0.0.1','port':port})
        assert response.status_code==409
        s.close()
        assert c.post('/api/server/start',headers=headers,json={'address':'127.0.0.1','port':port}).status_code==200
        assert c.post('/api/server/start',headers=headers,json={'address':'127.0.0.1','port':port}).status_code==409
        c.post('/api/server/stop',headers=headers,json={})
