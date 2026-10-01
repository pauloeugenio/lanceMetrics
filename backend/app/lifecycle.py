import sys,subprocess,time,json,urllib.request,os,psutil
from .core import ROOT
from .terminal import owned,primary_ip

def start():
    if os.geteuid()==0:raise SystemExit('Run the application as a regular user, not root.')
    if not (ROOT/'run/installed').exists():raise SystemExit('Run ./install.sh first')
    if owned('backend'):print('LANCE Metrics already running');return
    port=int(os.environ.get('LANCE_PORT','8080'));host=os.environ.get('LANCE_BIND','0.0.0.0')
    cmd=[sys.executable,'-m','uvicorn','backend.app.main:app','--host',host,'--port',str(port),'--ws','websockets']
    with (ROOT/'logs/backend.log').open('ab') as log:
        p=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
    meta={'pid':p.pid,'create_time':psutil.Process(p.pid).create_time(),'command':cmd,'port':port}
    (ROOT/'run/backend.json').write_text(json.dumps(meta)); (ROOT/'run/backend.pid').write_text(str(p.pid))
    for _ in range(100):
        if p.poll() is not None:raise SystemExit('Backend failed. See logs/backend.log')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=.3) as r:
                if r.status==200:break
        except Exception:time.sleep(.1)
    else:
        p.terminate();p.wait(timeout=10);raise SystemExit('Backend startup timeout')
    print(f'LANCE Metrics started successfully.\nLocal: http://localhost:{port}\nNetwork: http://{primary_ip()}:{port}\nAPI: http://localhost:{port}/docs')
    print('Access token:',(ROOT/'run/access.token').read_text().strip())
def stop():
    p=owned('backend')
    if p:
        p.terminate()
        try:p.wait(timeout=15)
        except psutil.TimeoutExpired:raise SystemExit('Backend did not stop; inspect logs before retrying.')
    # Identity verification avoids signalling unrelated processes after PID reuse.
    for file in (ROOT/'run').glob('iperf_*.json'):
        name=file.stem;child=owned(name)
        if child:
            child.terminate()
            try:child.wait(timeout=5)
            except psutil.TimeoutExpired:child.kill();child.wait(timeout=5)
        file.unlink(missing_ok=True)
    (ROOT/'run/backend.json').unlink(missing_ok=True);(ROOT/'run/backend.pid').unlink(missing_ok=True)
    print('LANCE Metrics stopped.')
if __name__=='__main__':
    if sys.argv[1]=='start':start()
    elif sys.argv[1]=='stop':stop()
