import asyncio,json,uuid,datetime,time,logging,shutil
from ..core import ROOT
from ..database import Session,Experiment,Measurement,serialize
from .iperf_parser import IperfParser
from .system_service import system_info,iperf_info
from .profile_runner import TrafficProfileRunner
log=logging.getLogger(__name__)
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
class IperfCommandBuilder:
    @staticmethod
    def client(c,session_id,stream=False,rate_limit=False):
        args=['iperf3','-c',c.target,'-p',str(c.port),'-t',str(c.duration),'-i',str(c.report_interval),'-P',str(c.parallel_streams),'--connect-timeout','5000','--get-server-output','--extra-data',session_id]
        args+=['--json-stream','--forceflush'] if stream else ['-J']
        if c.protocol=='udp': args+=['-u']
        if c.protocol=='udp' or rate_limit: args+=['-b',str(int(c.bandwidth_mbps*1e6))]
        if c.reverse_mode: args+=['-R']
        if c.datagram_length and c.protocol=='udp': args+=['-l',str(c.datagram_length)]
        return args
class IperfRunner:
    def __init__(self,manager):
        self.manager=manager; self.tasks={}; self.listeners={}; self.server={'status':'STOPPED','log':[]}; self.server_task=None
    async def publish(self,id,event):
        for q in list(self.listeners.get(id,set())):
            if q.full(): q.get_nowait()
            q.put_nowait(event)
    def update(self,id,**kw):
        with Session() as db:
            e=db.get(Experiment,id)
            for k,v in kw.items(): setattr(e,k,v)
            db.commit()
    def save_rows(self,id,rows,stage,sid,target,offset,started):
        with Session() as db:
            for r in rows:
                relative=r.get('elapsed_time') or 0
                timestamp=(datetime.datetime.fromisoformat(started)+datetime.timedelta(seconds=relative)).isoformat()
                r.update(stage_id=stage,session_id=sid,target_bps=target,timestamp=timestamp,timestamp_basis='local_session_start_plus_iperf_elapsed',elapsed_time=offset+relative)
                db.add(Measurement(experiment_id=id,values=r))
            db.commit()
    async def start(self,c,profile=None):
        if not shutil.which('iperf3'): raise ValueError('iperf3 is not installed')
        if any(not t.done() for t in self.tasks.values()): raise ValueError('An experiment is already running')
        env=system_info(); config=c.model_dump(); config['traffic_profile']=profile
        config.update(source_host=c.target if c.reverse_mode else env['hostname'],destination_host=env['hostname'] if c.reverse_mode else c.target,total_duration=sum(s['duration'] for s in profile['intervals']) if profile else c.duration)
        with Session() as db:
            e=Experiment(uuid=str(uuid.uuid4()),name=c.name,status='RUNNING',created_at=now(),started_at=now(),config=config,environment=env,summary={},sessions=[])
            db.add(e); db.commit(); result=serialize(e)
        log.info('experiment start uuid=%s target=%s protocol=%s',e.uuid,c.target,c.protocol)
        self.tasks[e.id]=asyncio.create_task(self.run(e.id,e.uuid,c,profile))
        return result
    async def run(self,id,euuid,c,profile):
        folder=ROOT/'data/experiments'/euuid; folder.mkdir(exist_ok=True)
        origin=time.monotonic(); sessions=[]; sums=[]
        (folder/'config.json').write_text(json.dumps({'configuration':c.model_dump(),'profile':profile,'environment':system_info()},indent=2))
        try:
            async for i,cfg in TrafficProfileRunner.stages(c,profile):
                sid=str(uuid.uuid4()); offset=time.monotonic()-origin; started=now()
                args=IperfCommandBuilder.client(cfg,sid,iperf_info()['json_stream'],bool(profile))
                record={'stage_id':i,'session_id':sid,'started_at':started,'offset_seconds':offset,'command':args,'target_bps':cfg.bandwidth_mbps*1e6*cfg.parallel_streams if cfg.protocol=='udp' or profile else None}
                log.info('profile stage experiment=%s stage=%s session=%s',euuid,i,sid)
                sessions.append(record); self.update(id,sessions=list(sessions))
                await self.publish(id,{'type':'stage','session':record})
                key=f'iperf_client_{id}'; p=await self.manager.spawn(key,args,{'experiment_uuid':euuid,'session_id':sid,'start_time':started})
                raw=folder/f'stage_{i}.stdout'; err=folder/f'stage_{i}.stderr'
                async def stderr():
                    with err.open('wb') as f:
                        while chunk:=await p.stderr.read(65536): f.write(chunk); f.flush()
                et=asyncio.create_task(stderr()); streamed=[]; final=None
                async def consume():
                    nonlocal final
                    with raw.open('wb') as f:
                        if '--json-stream' in args:
                            while line:=await p.stdout.readline():
                                f.write(line); f.flush()
                                try: event=json.loads(line)
                                except json.JSONDecodeError: continue
                                if event.get('event')=='interval':
                                    rows=IperfParser.intervals({'intervals':[event['data']]},cfg.protocol)
                                    self.save_rows(id,rows,i,sid,record['target_bps'],offset,started); streamed.extend(rows)
                                    await self.publish(id,{'type':'metrics','rows':rows})
                                elif event.get('event')=='end': final={'end':event['data']}
                                elif event.get('event')=='error': raise RuntimeError(str(event.get('data')))
                        else:
                            while chunk:=await p.stdout.read(65536): f.write(chunk); f.flush()
                    await p.wait()
                try: await asyncio.wait_for(consume(),cfg.duration+30)
                finally:
                    if p.returncode is None: await self.manager.stop(key)
                    await et
                    self.manager.forget(key)
                if final is None:
                    try: final=json.loads(raw.read_text())
                    except json.JSONDecodeError: raise RuntimeError('Invalid iperf JSON; raw output preserved')
                if p.returncode or final.get('error'): raise RuntimeError(final.get('error') or err.read_text() or 'iperf process failed')
                if not streamed:
                    rows=IperfParser.intervals(final,cfg.protocol)
                    self.save_rows(id,rows,i,sid,record['target_bps'],offset,started)
                    # Receiver intervals provided by --get-server-output are kept independently.
                    remote=final.get('server_output_json')
                    if remote:
                        rr=IperfParser.intervals(remote,cfg.protocol)
                        self.save_rows(id,rr,i,sid,record['target_bps'],offset,started)
                    await self.publish(id,{'type':'metrics'})
                summary=IperfParser.summary(final,cfg.protocol)
                end=final.get('end',{})
                weights={'sender':end.get('sum_sent',{}).get('seconds'),'receiver':end.get('sum_received',{}).get('seconds') or end.get('sum',{}).get('seconds')}
                sums.append((summary,weights))
                record.update(finished_at=now(),summary=summary,actual_seconds=time.monotonic()-origin-offset)
                self.update(id,sessions=list(sessions))
            summary={}
            for field in IperfParser.summary({},c.protocol):
                side='sender' if field.startswith('sender') else 'receiver'
                available=[(s[field],weights[side]) for s,weights in sums if s[field] is not None]
                if len(available)!=len(sums): summary[field]=None
                elif field in ('sender_bytes','receiver_bytes','packets_sent','packets_received','packets_lost','retransmissions'): summary[field]=sum(v for v,d in available)
                else:
                    weighted=[(v,d) for v,d in available if d is not None and d>0]
                    summary[field]=sum(v*d for v,d in weighted)/sum(d for v,d in weighted) if weighted else None
            if summary.get('packets_received') is not None and summary.get('packets_lost') is not None:
                total=summary['packets_received']+summary['packets_lost']; summary['loss_percent']=100*summary['packets_lost']/total if total else None
            self.update(id,status='COMPLETED',finished_at=now(),summary=summary)
            log.info('experiment completed uuid=%s',euuid)
        except asyncio.CancelledError:
            await self.manager.stop(f'iperf_client_{id}'); self.update(id,status='STOPPED',finished_at=now())
            log.info('experiment stopped uuid=%s',euuid)
        except Exception as ex:
            log.exception('experiment failed %s',euuid); self.update(id,status='ERROR',error=str(ex),finished_at=now())
        finally:
            await self.publish(id,{'type':'state'})
            with Session() as db:
                data=serialize(db.get(Experiment,id)); data['measurements']=[m.values for m in db.query(Measurement).filter_by(experiment_id=id)]
            (folder/'results.json').write_text(json.dumps(data,indent=2))
    async def stop(self,id):
        t=self.tasks.get(id)
        if t and not t.done(): t.cancel(); await t
    async def start_server(self,c):
        if not shutil.which('iperf3'): raise ValueError('iperf3 is not installed')
        if self.server_task and not self.server_task.done(): raise ValueError('Server already running')
        self.server={'status':'STARTING','address':c.address,'port':c.port,'started_at':now(),'log':[],'connected_client':None}
        self.server_task=asyncio.create_task(self.server_loop(c))
        await asyncio.sleep(.3)
        if self.server['status']=='ERROR': raise ValueError(self.server.get('error'))
        return self.server
    async def server_loop(self,c):
        # One-off structured sessions, automatically rearmed; each receiver result stays local.
        try:
            while True:
                p=await self.manager.spawn('iperf_server',['iperf3','-s','-1','-J','-B',c.address,'-p',str(c.port)],{'start_time':now()})
                self.server.update(status='RUNNING',pid=p.pid)
                started=now(); euuid=str(uuid.uuid4())
                folder=ROOT/'data/experiments'/euuid; folder.mkdir()
                (folder/'config.json').write_text(json.dumps({'mode':'server','listen':c.model_dump(),'started_at':started,'environment':system_info()},indent=2))
                async def capture(stream,path):
                    with path.open('wb') as f:
                        while chunk:=await stream.read(65536): f.write(chunk); f.flush()
                readers=[asyncio.create_task(capture(p.stdout,folder/'server.json')),asyncio.create_task(capture(p.stderr,folder/'server.stderr'))]
                try:
                    await p.wait()
                finally:
                    if p.returncode is None: await self.manager.stop('iperf_server')
                    await asyncio.gather(*readers)
                out=(folder/'server.json').read_bytes();err=(folder/'server.stderr').read_bytes(); self.manager.forget('iperf_server')
                with (ROOT/'logs/iperf.log').open('ab') as f: f.write(out+err)
                self.server['log']=(self.server['log']+[out.decode(errors='replace'),err.decode(errors='replace')])[-10:]
                if p.returncode: raise RuntimeError(err.decode() or out.decode())
                doc=json.loads(out); sid=str(uuid.uuid4())
                proto=doc.get('start',{}).get('test_start',{}).get('protocol','TCP').lower()
                connected=doc.get('start',{}).get('connected',[]); self.server['connected_client']=connected[0].get('remote_host') if connected else None
                with Session() as db:
                    e=Experiment(uuid=euuid,name='Server observation',status='COMPLETED',created_at=started,started_at=started,finished_at=now(),config={'mode':'server','protocol':proto,'port':c.port,'connections':connected,'peer_session_id':doc.get('start',{}).get('extra_data')},environment=system_info(),summary=IperfParser.summary(doc,proto,'sender' if doc.get('start',{}).get('test_start',{}).get('reverse') else 'receiver'),sessions=[{'session_id':sid,'stage_id':0}])
                    db.add(e); db.commit(); eid=e.id
                (folder/'results.json').write_text(json.dumps({'experiment':serialize(e),'iperf':doc},indent=2))
                self.save_rows(eid,IperfParser.intervals(doc,proto),0,sid,None,0,started)
        except asyncio.CancelledError: pass
        except Exception as ex:
            log.exception('server failed'); self.server.update(status='ERROR',error=str(ex))
        finally: await self.manager.stop('iperf_server')
    async def stop_server(self):
        if self.server_task and not self.server_task.done():
            self.server['status']='STOPPING'; self.server_task.cancel(); await self.server_task
        self.server.update(status='STOPPED',pid=None)
    async def shutdown(self):
        for id in list(self.tasks): await self.stop(id)
        await self.stop_server(); await self.manager.shutdown()
