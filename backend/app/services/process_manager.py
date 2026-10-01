import asyncio,json,psutil,logging
from ..core import ROOT
log=logging.getLogger(__name__)
class ProcessManager:
    def __init__(self): self.processes={}
    async def spawn(self,key,args,metadata=None,env=None):
        p=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,start_new_session=True,env=env)
        self.processes[key]=p
        (ROOT/'run'/f'{key}.json').write_text(json.dumps({'pid':p.pid,'create_time':psutil.Process(p.pid).create_time(),'command':args,**(metadata or {})}))
        log.info('process start %s pid=%s',key,p.pid)
        return p
    async def stop(self,key,grace_seconds=5):
        p=self.processes.get(key)
        if p and p.returncode is None:
            p.terminate()
            try: await asyncio.wait_for(p.wait(),grace_seconds)
            except asyncio.TimeoutError: p.kill(); await p.wait()
        self.forget(key)
    def forget(self,key):
        self.processes.pop(key,None); (ROOT/'run'/f'{key}.json').unlink(missing_ok=True)
    async def shutdown(self):
        for key in list(self.processes): await self.stop(key)
