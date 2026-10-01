"""Terminal orchestration and diagnostics; lifecycle logic lives outside the menu."""
import os,sys,subprocess,socket,platform,shutil,json,sqlite3,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from .core import VERSION
def executable(): return str(ROOT/'.venv/bin/python') if (ROOT/'.venv/bin/python').exists() else sys.executable
def info():
    try:
        from .services.system_service import system_info
        return system_info()
    except (ImportError,OSError):
        return {'os':platform.platform(),'architecture':platform.machine(),'hostname':socket.gethostname(),'interfaces':[]}
def primary_ip():
    for n in info()['interfaces']:
        if n['state']=='UP' and ':' not in n['ip'] and not n['ip'].startswith('127.'): return n['ip']
    return '127.0.0.1'
def owned(name):
    try:
        import psutil
        data=json.loads((ROOT/'run'/f'{name}.json').read_text()); p=psutil.Process(data['pid'])
        if p.create_time()!=data['create_time']: return None
        if p.cmdline()!=data['command']: return None
        return p
    except (ImportError,OSError,ValueError,KeyError): return None
    except Exception: return None
def status():
    data=info(); port=os.environ.get('LANCE_PORT','8080')
    print('\nLANCE Metrics Status\n'+'-'*50)
    p=owned('backend'); print('Backend / bundled frontend:',f'Running PID {p.pid}' if p else 'Stopped')
    p=owned('iperf_server'); print('iperf3 server:',f'Running PID {p.pid}' if p else 'Stopped')
    print(json.dumps(data,indent=2)); print(f'Web / API: http://localhost:{port} / http://{primary_ip()}:{port}')
    token=ROOT/'run/access.token'
    if token.exists(): print('Web access token:',token.read_text().strip())
def diagnostics():
    results=[]
    def check(label,ok): results.append(ok); print(f'[{"PASS" if ok else "FAIL"}] {label}')
    check('Python >= 3.10',sys.version_info>=(3,10));check('Virtual environment',(ROOT/'.venv/bin/python').exists())
    for module in ('fastapi','uvicorn','sqlalchemy','pydantic','psutil'):
        result=subprocess.run([executable(),'-c',f'import {module}'],capture_output=True)
        check('Backend dependency '+module,result.returncode==0)
    check('Frontend build',(ROOT/'frontend/dist/index.html').exists());check('iperf3',shutil.which('iperf3') is not None)
    from .services.video_tools import tool_path,tool_env
    for binary in ('ffmpeg','ffprobe'):
        found=tool_path(binary)
        check('FFmpeg' if binary=='ffmpeg' else 'ffprobe',found is not None)
        if found:
            result=subprocess.run([found,'-version'],capture_output=True,text=True,timeout=5,env=tool_env(binary))
            print('       '+result.stdout.splitlines()[0])
    try:
        with sqlite3.connect(':memory:') as db: db.execute('select 1')
        check('SQLite',True)
    except sqlite3.Error: check('SQLite',False)
    for name in ('data','logs','run'):check(name+' directory',os.access(ROOT/name,os.W_OK))
    warnings=False
    for port in (int(os.environ.get('LANCE_PORT','8080')),5201):
        s=None
        try:
            s=socket.socket();s.bind(('127.0.0.1',port));print(f'[PASS] Port {port} available')
        except OSError as ex:
            print(f'[WARN] Port {port}: {ex}');warnings=True
            try:
                import psutil
                for conn in psutil.net_connections(kind='inet'):
                    if conn.laddr and conn.laddr.port==port and conn.pid:
                        process=psutil.Process(conn.pid);print(f'       PID {conn.pid} · {process.name()}')
            except Exception: print('       Process identification unavailable with current permissions')
        finally:
            if s:s.close()
    print('NOT READY' if not all(results) else 'READY WITH WARNINGS' if warnings else 'READY')
    return 0 if all(results) else 1
def run_script(name):return subprocess.run(['bash',str(ROOT/name)],cwd=ROOT).returncode
def logs():
    choices={'1':'lanceMetrics.log','2':'backend.log','3':'backend.log','4':'iperf.log'}
    while True:
        print('\n[1] Application Log [2] Backend Log [3] Bundled Frontend Log [4] iperf Log [5] Follow Live Log [0] Back')
        choice=input('Choose: ').strip()
        if choice=='0':return
        path=ROOT/'logs'/choices.get(choice,'lanceMetrics.log')
        if not path.exists():print('No log yet');continue
        try:subprocess.run(['tail','-n','100',*(['-f'] if choice=='5' else []),str(path)])
        except KeyboardInterrupt:print('\nLog follow stopped')
def web_shutdown_menu():
    while True:
        print('\nFINALIZAR SERVIDOR WEB\n[1] Finalizar servidor web\n[0] Voltar ao menu principal')
        try:choice=input('Escolha uma opção: ').strip()
        except (EOFError,KeyboardInterrupt):print();return
        if choice=='0':return
        if choice=='1':
            if run_script('stop.sh')==0:
                print('Servidor web finalizado. A interface deixa de responder no navegador.')
                return
            print('A parada falhou. Consulte logs/backend.log.')
        else:print('Opção inválida.')

def menu():
    while True:
        installed=(ROOT/'run/installed').exists()
        print('\n'+'='*64+f'\n                    LANCE Metrics v{VERSION}\n         Network Performance Measurement Platform\n'+'='*64)
        print(f'{platform.platform()} | {socket.gethostname()} | {primary_ip()}')
        print('Installed' if installed else 'LANCE Metrics has not been installed on this machine.')
        if not installed:
            print('[1] Install LANCE Metrics\n[2] Run Diagnostics\n[0] Exit')
            try: initial=input('Choose an option: ').strip()
            except (EOFError,KeyboardInterrupt):print();return
            if initial=='0':return
            if initial=='2':diagnostics();continue
            if initial=='1' and run_script('install.sh')==0:
                os.execv(executable(),[executable(),'-m','backend.app.terminal'])
            continue
        print('[1] Install / Update LANCE Metrics\n[2] Start LANCE Metrics\n[3] Stop Web Interface / Parar servidor web\n[4] Restart LANCE Metrics\n[5] Show Status\n[6] Show Logs\n[7] Open Web Interface\n[8] System Information\n[9] Run Diagnostics\n[10] Finalizar servidor web (menu exclusivo)\n[0] Exit')
        try:choice=input('Choose an option: ').strip()
        except (EOFError,KeyboardInterrupt):print();return
        try:
            if choice=='0':return
            if choice=='1':run_script('install.sh')
            elif choice=='2':
                if not installed:
                    if input('Install now? [y/N] ').lower()!='y':continue
                    if run_script('install.sh'):continue
                run_script('start.sh')
            elif choice=='3':run_script('stop.sh')
            elif choice=='4':
                if run_script('stop.sh')==0:run_script('start.sh')
            elif choice=='5':status()
            elif choice=='6':logs()
            elif choice=='7':
                url='http://localhost:'+os.environ.get('LANCE_PORT','8080');print(url);print('Network: http://'+primary_ip()+':'+os.environ.get('LANCE_PORT','8080'))
                if input('Open in browser? [y/N] ').lower()=='y':webbrowser.open(url)
            elif choice=='8':
                status()
                for cmd in (['node','--version'],['npm','--version']):
                    if shutil.which(cmd[0]):subprocess.run(cmd)
                print('Application disk usage:',sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()),'bytes')
                dbfile=ROOT/'data/lanceMetrics.sqlite'
                if dbfile.exists():
                    with sqlite3.connect(dbfile) as db:
                        for table in ('experiments','profiles'):print(table,db.execute('select count(*) from '+table).fetchone()[0])
            elif choice=='9':diagnostics()
            elif choice=='10':web_shutdown_menu()
        except KeyboardInterrupt:print('\nOperation interrupted')
if __name__=='__main__':
    command=sys.argv[1] if len(sys.argv)>1 else 'menu'
    if command=='diagnostics':sys.exit(diagnostics())
    elif command=='status':status()
    elif command=='stop-web':sys.exit(run_script('stop.sh'))
    elif command=='web-menu':web_shutdown_menu()
    else:menu()
