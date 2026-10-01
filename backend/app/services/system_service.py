import platform,socket,shutil,subprocess,datetime,psutil
from ..core import VERSION

def iperf_info():
    exe=shutil.which('iperf3')
    if not exe: return {'installed':False,'version':None,'json_stream':False}
    version=subprocess.run([exe,'--version'],capture_output=True,text=True,timeout=5).stdout.splitlines()[0]
    helptext=subprocess.run([exe,'--help'],capture_output=True,text=True,timeout=5).stdout
    return {'installed':True,'version':version,'json_stream':'--json-stream' in helptext}
def system_info():
    try: states=psutil.net_if_stats()
    except OSError: states={}
    try: addresses=psutil.net_if_addrs()
    except OSError: addresses={}
    interfaces=[{'interface':n,'ip':a.address,'state':('UP' if states[n].isup else 'DOWN') if n in states else 'UNKNOWN'} for n,items in addresses.items() for a in items if a.family in (socket.AF_INET,socket.AF_INET6)]
    return {'application_version':VERSION,'os':platform.platform(),'kernel':platform.release(),'architecture':platform.machine(),'hostname':socket.gethostname(),'python':platform.python_version(),'timezone':str(datetime.datetime.now().astimezone().tzinfo),'interfaces':interfaces,'iperf':iperf_info()}
