#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
[ -x .venv/bin/python ] || { echo 'Run ./install.sh first'; exit 1; }
[ -f frontend/dist/index.html ] || { echo 'Frontend build missing. Run ./install.sh'; exit 1; }
.venv/bin/python -c 'import fastapi,uvicorn,sqlalchemy,pydantic,psutil,websockets' || { echo 'Backend dependencies missing. Run ./install.sh'; exit 1; }
exec .venv/bin/python -m backend.app.lifecycle start
