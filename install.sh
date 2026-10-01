#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [ "$(id -u)" = 0 ]; then echo 'Run as a regular user. sudo is used only for OS packages.'; exit 1; fi
printf 'LANCE Metrics installation · %s · %s\n' "$(uname -s)" "$(uname -m)"
case "$(uname -s)" in
 Linux)
  if [ -f /etc/os-release ]; then . /etc/os-release; fi
  case "${ID:-} ${ID_LIKE:-}" in *ubuntu*|*debian*) ;; *) echo 'Unsupported automatic installer. Install Python >=3.10, venv, Node >=18 and iperf3 manually.'; exit 1;; esac
  packages=()
  command -v python3 >/dev/null || packages+=(python3)
  python3 -c 'import venv,ensurepip' >/dev/null 2>&1 || packages+=(python3-venv)
  command -v iperf3 >/dev/null || packages+=(iperf3)
  if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then packages+=(ffmpeg); fi
  command -v node >/dev/null || packages+=(nodejs)
  command -v npm >/dev/null || packages+=(npm)
  if [ "${#packages[@]}" -gt 0 ]; then sudo apt-get update; sudo apt-get install -y "${packages[@]}"; fi
 ;;
 Darwin)
  if ! command -v brew >/dev/null; then
   for bin in python3 iperf3 ffmpeg ffprobe node npm; do command -v "$bin" >/dev/null || { echo 'Homebrew is required to automatically install missing dependencies on macOS. See https://brew.sh'; exit 1; }; done
  else
   command -v python3 >/dev/null || brew install python
   command -v iperf3 >/dev/null || brew install iperf3
   if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then brew install ffmpeg; fi
   command -v node >/dev/null || brew install node
  fi
 ;;
 *) echo 'Unsupported operating system'; exit 1;;
esac
python3 -c 'import sys; assert sys.version_info >= (3,10), "Python >=3.10 required"'
node -e 'if(Number(process.versions.node.split(".")[0])<18)throw Error("Node >=18 required")'
mkdir -p data/experiments data/profiles logs run
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
npm run build --prefix frontend
.venv/bin/python -c 'from backend.app.database import init_db; init_db()'
chmod +x lanceMetrics install.sh start.sh stop.sh
touch run/installed
.venv/bin/python -m backend.app.terminal diagnostics
printf '\nInstallation complete. Run ./lanceMetrics and choose [2], or ./start.sh\n'
