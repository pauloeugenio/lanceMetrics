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

## Logo and execution feedback — 2026-10-01

36 backend tests and 4 Chrome workflows passed. Original JPEG loaded in login/sidebar; elapsed timer advanced during a real UDP run in details and dashboard; STOP TEST removed the execution indicator. System now directs web shutdown to the script. The stop-web CLI dispatches stop.sh; a real stop/start verification confirmed that HTTP stopped responding and then recovered. Production build passed.

## Individual and bulk deletion — 2026-10-01

41 backend tests and 5 Chrome workflows passed. New checks cover authentication/origin protection, deletion of measurements and raw files, batch validation with running/missing records, deduplication, invalid selection, active task protection, database failure rollback and symlink rejection. Browser validation creates only its own error experiments, checks confirmation cancellation, individual deletion, select-visible checkboxes and batch deletion, and confirms those IDs become unavailable. Existing user records are not selected by that test.


## Video Streaming acceptance — 2026-10-01

Before modifying the existing application, **41 backend tests and 5 browser workflows passed**. The final backend run using the normal `.venv/bin/python -m pytest backend/tests -q --tb=short` command passed **66 tests in 55.47 seconds**, with no skipped video integrations. The installed user-local official Ubuntu FFmpeg/ffprobe 6.1.1 tools were discovered directly by the application and tests.

Final browser suite: **6 passed in 36.6 seconds**, covering the original five workflows plus 20 simultaneous file selections/uploads, real metadata, queue selection, two concurrent streams, actual decoded Receiver images, saved per-video results/charts and CSV download. Existing cases covered logo/timer/dashboard stop, iperf server, real UDP run, exports, profile preview, deletion, and terminal shutdown guidance.

Backend coverage includes all existing TCP/UDP/reverse/profile/export/process/shutdown cases; probe parser and real probe; streaming upload validation/limits; safe command arguments; concurrent port validation/reservation; real sequential/concurrent video; RTP packet loss/jitter observability; timestamp/sequence wrap; nullable UDP metrics; queue order; VideoSession persistence/deletion; startup filesystem failure terminal states; partial abort; and two independent uvicorn instances with separate SQLite roots, authenticated peer preparation, controlled H.264, RX retrieval, remote stop and owned process cleanup. Small synthetic sources were generated in temporary directories, without adding a binary dataset to the repository.

`npm run build` passed TypeScript and Vite (18.04 seconds on final UI build). `bash -n install.sh start.sh stop.sh lanceMetrics` passed. Diagnostics passed both FFmpeg and ffprobe with real versions; occupied 8080 belongs to the active LANCE service, while an existing unrelated service occupies 5201 and was left untouched. The pre-existing large Plotly bundle warning and two Python deprecation/runtime warnings remain.

Database comparison against `data/pre-video-migration.sqlite` confirmed all **55 pre-activation experiment UUIDs and 10 profile definitions remained present and unchanged**. The new tables are `video_assets` and `video_sessions`. Final service inspection found FFmpeg/ffprobe available, zero active experiments, Receiver STOPPED, and zero owned FFmpeg PID metadata files.

Visual evidence: [actual Receiver preview](video-receiver.png), [video results and chart](video-results.png). Scope: Linux localhost and independent local instances; native macOS and physical two-host/5G/6G testing remain environment-specific acceptance work. Combined clock-aligned metrics, one-way latency and PSNR/SSIM/VMAF are explicitly not claimed.

Detailed delivery inventory and reproduction: [VIDEO_DELIVERY.md](VIDEO_DELIVERY.md), [VIDEO_STREAMING.md](VIDEO_STREAMING.md).
