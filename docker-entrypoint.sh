#!/usr/bin/env bash
set -euo pipefail
cd /app
mkdir -p data/experiments data/profiles logs run
for directory in data logs run; do
    [ -w "$directory" ] || { echo "Directory /app/$directory must be writable by UID 10001" >&2; exit 1; }
done
touch run/installed
if [ "${1:-serve}" != serve ]; then
    exec "$@"
fi
# The original start.sh daemonizes uvicorn. Supervise its identity and forward
# shutdown through the original stop.sh; tini reaps orphaned subprocesses.
exec python - <<'PY'
import signal
import subprocess
import time
from backend.app.terminal import owned

stopping = False
def stop_requested(signum, frame):
    global stopping
    stopping = True

signal.signal(signal.SIGTERM, stop_requested)
signal.signal(signal.SIGINT, stop_requested)
tail = None
try:
    subprocess.run(['bash', './start.sh'], check=True)
    process = owned('backend')
    if process is None:
        raise RuntimeError('Backend identity unavailable after startup')
    tail = subprocess.Popen(['tail', '-n', '0', '-F', 'logs/backend.log'])
    while not stopping and process.is_running() and process.status() != 'zombie':
        time.sleep(0.5)
finally:
    subprocess.run(['bash', './stop.sh'], check=True)
    if tail is not None:
        tail.terminate()
        tail.wait(timeout=5)
PY
