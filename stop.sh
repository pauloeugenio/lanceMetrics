#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
[ -x .venv/bin/python ] || { echo 'Application is not installed'; exit 0; }
exec .venv/bin/python -m backend.app.lifecycle stop
