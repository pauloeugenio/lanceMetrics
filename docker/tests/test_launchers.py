"""Deployment launchers: exercise CLI behavior without changing host Docker/data."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lance-launcher-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project with spaces"
        self.root.mkdir()
        for name in ("lanceMetrics",):
            shutil.copy2(ROOT / name, self.root / name)
        (self.root / "bare-metal").mkdir()
        for name in ("install.sh", "start.sh", "stop.sh", "lanceMetrics"):
            shutil.copy2(ROOT / "bare-metal" / name, self.root / "bare-metal" / name)
        (self.root / "docker").mkdir()
        shutil.copy2(ROOT / "docker/docker-compose.yml", self.root / "docker/docker-compose.yml")
        shutil.copy2(ROOT / "docker/manage.sh", self.root / "docker/manage.sh")
        for name in ("all-in-one.sh", "docker-compose.all-in-one.yml"):
            shutil.copy2(ROOT / "docker" / name, self.root / "docker" / name)
        self.bin = Path(self.temp.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.temp.name) / "calls.jsonl"
        fake = self.bin / "docker"
        fake.write_text("#!" + sys.executable + "\n" + r'''import json,os,sys
args=sys.argv[1:]
with open(os.environ['MOCK_LOG'],'a') as f:
    f.write(json.dumps({'args':args,'http':os.getenv('LANCE_HTTP_PORT'),'iperf':os.getenv('LANCE_IPERF_PORT'),'video':os.getenv('LANCE_VIDEO_PORT_RANGE')})+'\n')
if args[:2]==['image','inspect']:
    sys.exit(int(os.getenv('MOCK_IMAGE_MISSING','0')))
if args and args[0]=='inspect':
    print(os.getenv('MOCK_HEALTH','running healthy'))
if 'config' in args and '--images' in args:
    print(os.getenv('LANCE_IMAGE','lancemetrics:local'))
if 'ps' in args and '--quiet' in args:
    print('mock-'+args[-1])
if 'port' in args:
    if os.getenv('MOCK_NO_PORT'):sys.exit(1)
    port=os.getenv('LANCE_HTTP_PORT','8080')
    if any('docker-compose.all-in-one.yml' in arg for arg in args):
        port='8082' if 'lance-cliente' in args else '8081'
    print('0.0.0.0:'+port)
''')
        fake.chmod(0o755)
        self.env = {key:value for key,value in os.environ.items() if not key.startswith('LANCE_')}
        self.env.update(PATH=str(self.bin)+os.pathsep+os.environ['PATH'],MOCK_LOG=str(self.log))
        self.env.pop('DISPLAY',None)
        self.env.pop('WAYLAND_DISPLAY',None)

    def run_cli(self,*args,**env):
        return subprocess.run(['bash',str(self.root/'lanceMetrics'),*(args or ('start',))],cwd='/tmp',env=dict(self.env,**env),capture_output=True,text=True,timeout=10)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_first_start_builds_and_runs_detached_then_shows_url(self):
        result=self.run_cli(MOCK_IMAGE_MISSING='1')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('http://localhost:8080',result.stdout)
        calls=self.calls()
        self.assertTrue(any('build' in c['args'] for c in calls))
        self.assertTrue(any(c['args'][-3:]==['up','-d','--no-build'] for c in calls))

    def test_existing_image_is_reused(self):
        self.assertEqual(self.run_cli().returncode,0)
        self.assertFalse(any('build' in c['args'] or 'pull' in c['args'] for c in self.calls()))

    def test_ports_persist_and_are_separated_by_instance(self):
        result=self.run_cli('--name','receiver','--port','8082','--iperf-port','5202','--video-ports','6000-6018')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('http://localhost:8082',result.stdout)
        self.assertTrue((self.root/'docker/.instances/receiver.env').exists())
        result=self.run_cli('start','--name','receiver')
        self.assertIn('http://localhost:8082',result.stdout)
        self.assertIn('http://localhost:8080',self.run_cli('--name','sender').stdout)
        self.assertIn('http://localhost:8083',self.run_cli('--name','receiver','--port','8083').stdout)

    def test_stop_preserves_data(self):
        result=self.run_cli('stop','--name','receiver')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(any(c['args'][-1]=='stop' for c in self.calls()))
        self.assertFalse(any('down' in c['args'] or 'volume' in c['args'] for c in self.calls()))

    def test_update_builds_local_and_pulls_published_image(self):
        self.assertEqual(self.run_cli('update').returncode,0)
        self.assertTrue(any('build' in c['args'] for c in self.calls()))
        self.log.unlink()
        self.assertEqual(self.run_cli('update',LANCE_IMAGE='example/lancemetrics:latest').returncode,0)
        self.assertTrue(any('pull' in c['args'] for c in self.calls()))
        self.assertFalse(any('build' in c['args'] for c in self.calls()))

    def test_failed_container_reports_logs_without_success_url(self):
        result=self.run_cli(MOCK_HEALTH='exited unhealthy')
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn('disponível em',result.stdout)
        self.assertTrue(any('logs' in c['args'] for c in self.calls()))

    def test_invalid_options_fail_before_docker(self):
        for args in [('--port','0'),('--port','65536'),('--video-ports','6000-5000'),('--name','../escape'),('--port',),('--unknown',)]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_cli(*args).returncode,0)
        self.assertEqual(self.calls(),[])

    def test_help_and_headless_open(self):
        self.assertEqual(self.run_cli('--help').returncode,0)
        self.assertEqual(self.calls(),[])
        result=self.run_cli('open')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Abra manualmente',result.stdout)

    def test_restart_and_stopped_status(self):
        self.assertEqual(self.run_cli('restart').returncode,0)
        self.assertTrue(any('restart' in c['args'] for c in self.calls()))
        result=self.run_cli('status',MOCK_NO_PORT='1')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Aplicação parada',result.stdout)

    def test_native_shortcuts_keep_project_root_and_arguments(self):
        python=self.root/'bare-metal/.venv/bin/python'
        python.parent.mkdir(parents=True)
        python.write_text('#!/usr/bin/env bash\nprintf "ROOT=%s\\n" "$PWD"\nprintf "ARG=%s\\n" "$@"\n')
        python.chmod(0o755)
        (self.root/'bare-metal/frontend/dist').mkdir(parents=True)
        (self.root/'bare-metal/frontend/dist/index.html').touch()
        for script in ['bare-metal/start.sh','bare-metal/stop.sh','bare-metal/lanceMetrics']:
            with self.subTest(script=script):
                args=['diagnostics'] if script.endswith('lanceMetrics') else []
                result=subprocess.run(['bash',str(self.root/script),*args],cwd='/tmp',env=self.env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('ROOT='+str(self.root/'bare-metal'),result.stdout)
                if args:self.assertIn('ARG=diagnostics',result.stdout)

    def test_repository_visible_root_contains_only_two_directories_and_menu(self):
        visible={p.name for p in ROOT.iterdir() if not p.name.startswith('.')}
        self.assertEqual(visible,{'docker','bare-metal','lanceMetrics'})

    def test_menu_starts_shows_link_and_exit_keeps_container_running(self):
        result=subprocess.run(['bash',str(self.root/'lanceMetrics')],input='1\n0\n',cwd='/tmp',env=self.env,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('[1] Iniciar LANCE Metrics',result.stdout)
        self.assertIn('http://localhost:8080',result.stdout)
        self.assertFalse(any('stop' in c['args'] or 'down' in c['args'] for c in self.calls()))

    def test_menu_recovers_after_invalid_choice_and_failed_action(self):
        result=subprocess.run(['bash',str(self.root/'lanceMetrics')],input='invalid\n1\n0\n',cwd='/tmp',env=dict(self.env,MOCK_HEALTH='exited unhealthy'),capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Opção inválida',result.stdout)
        self.assertIn('Não foi possível concluir',result.stdout)

    def test_menu_can_exit_without_docker_access(self):
        result=subprocess.run(['bash',str(self.root/'lanceMetrics')],input='0\n',cwd='/tmp',env=self.env,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.calls(),[])

    def test_all_in_one_starts_two_services_and_shows_both_links(self):
        result=self.run_cli('all-start')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Servidor: http://localhost:8081',result.stdout)
        self.assertIn('Cliente:  http://localhost:8082',result.stdout)
        self.assertIn('http://lance-cliente:8080',result.stdout)
        checks=[c for c in self.calls() if c['args'][0]=='inspect']
        self.assertEqual(len(checks),2)
        self.assertTrue(all('lancemetrics-all-in-one' in c['args'] for c in self.calls() if c['args'][0]=='compose' and 'version' not in c['args']))

    def test_all_in_one_stop_preserves_both_volumes(self):
        result=self.run_cli('all-stop')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('preservados',result.stdout)
        self.assertTrue(any(c['args'][-1]=='stop' for c in self.calls()))
        self.assertFalse(any('down' in c['args'] or 'volume' in c['args'] for c in self.calls()))

    def test_simplified_menu_routes_all_in_one_start_stop(self):
        result=subprocess.run(['bash',str(self.root/'lanceMetrics')],input='4\n5\n0\n',cwd='/tmp',env=self.env,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('[3] Ver logs (Ctrl+C para voltar)',result.stdout)
        self.assertIn('[4] Teste All in one',result.stdout)
        self.assertNotIn('Reiniciar LANCE Metrics',result.stdout)
        self.assertNotIn('Abrir no navegador',result.stdout)
        self.assertIn('Teste All in one parado',result.stdout)

if __name__=='__main__':
    unittest.main()
