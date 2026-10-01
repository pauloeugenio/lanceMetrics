# Local validation — 2026-10-01

Tested on Ubuntu/Linux x86_64, Python 3.12.3, Node 20.20.2, system Chrome and iperf3 3.16. No physical two-host or native macOS test was performed.

- pytest: **29 passed**. Includes validation, injection rejection, parser provenance/missing values, database/API, bearer auth, cross-origin rejection, profiles/uploads, subprocess termination, real localhost TCP/UDP/reverse tests, local server persistence, two-stage profile, WebSocket snapshot, cancellation, CSV/JSON, raw preservation on connection refusal, occupied port and duplicate server protection.
- Playwright/Chrome: **1 complete workflow passed**. Login, server start, actual UDP test, completed chart view, CSV/JSON/SVG downloads, raw output, two-stage profile preview/save, server stop and responsive viewport check. Screenshot: dashboard.png. Browser validation produces genuine localhost records in the local database.
- TypeScript + Vite production build passed. The full local Plotly bundle produces a non-fatal size warning (~5 MB uncompressed).
- Bash syntax and executable permissions verified for lanceMetrics/install.sh/start.sh/stop.sh.
- Python compile/import checks passed.
- SQLite integrity check: **ok**; existing experiments/profiles survived a second installer execution.
- Example profile validated: **13 stages / 130 seconds**.
- Backend started successfully through start.sh; stop.sh terminated owned backend/iperf processes.
- Diagnostics: **READY WITH WARNINGS** due to a pre-existing process occupying port 5201. Tests used dynamically allocated ports; that process was left untouched.

A Starlette test-client deprecation warning for httpx remains; it does not fail tests. Restricted sandbox socket access requires running integration/browser validation with appropriate permissions. Older iperf3 versions return JSON at session completion; live receiver measurements are not synthesized.

For repeatable commands and research limitations, see README.md and METRICS.md.

## Recovery fixes — 2026-10-01

32 backend tests passed, including preparation failure, orphan RUNNING recovery and immediate/concurrent cancellation. Two Chrome workflows passed, including dashboard completion with experiment WebSocket intentionally unavailable and immediate STOP TEST. Async experiment responses now respect navigation; dashboard reconciles every 3 seconds with request timeouts. The active installation was moved to /home/paulo/lanceMetrics after stopping the verified old backend. Existing selected database and source files were backed up before changes.

## Web application stop button — 2026-10-01

34 backend tests passed, including authenticated/idempotent shutdown and a real isolated uvicorn shutdown during an active UDP run with an open experiment WebSocket. Server/client process records were cleaned, the stopped experiment persisted, and shutdown completed within the 10-second test deadline. Three Chrome workflows passed, including confirmation cancellation/acceptance and restart instructions (the browser test mocks the shutdown reply to keep its shared server available). The isolated backend integration test executes the actual stop operation.
