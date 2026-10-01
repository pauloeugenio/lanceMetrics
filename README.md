# LANCE Metrics v0.1.0

**Network Performance Measurement and Experiment Platform**

A local laboratory application for reproducible iperf3 experiments. The same installation operates as a client or server. Measured sender and receiver data remain distinct; missing metrics stay N/A. Raw output, environment, commands and session configuration are retained.

## Quick start

```bash
chmod +x lanceMetrics
./lanceMetrics
```

Choose **[1] Install / Update**, then **[2] Start**. Open http://localhost:8080 and enter the access token printed by start/status. On other machines use the host's detected network URL. The backend serves the built frontend and API on the same port; no separate frontend daemon is required.

Independent scripts:

```bash
./install.sh
./start.sh
./stop.sh
./lanceMetrics status
./lanceMetrics diagnostics
```

## Requirements and installation

Ubuntu/Debian or macOS, Python 3.10+, Node 18+, npm, iperf3. Bash, SQLite and about 300 MB for dependencies/build. Installer creates a project-local .venv, installs missing OS dependencies, uses locked Python/npm dependencies, builds frontend and initializes SQLite without erasing existing data.

Ubuntu/Debian: missing OS dependencies use sudo apt; never run the application as root. If venv creation reports missing ensurepip, install `sudo apt install python3-venv` and rerun. Node must be at least 18; older distribution Node packages may require an upgrade through your preferred package provider.

macOS: existing Homebrew can install missing Python, Node and iperf3. Homebrew itself is never installed automatically; see https://brew.sh when required. Installation needs Internet access; ordinary execution does not.

## Terminal menu

Install/update, start, stop, restart, real status/PIDs, log tail/follow, browser opening, system information and diagnostics. Ctrl+C exits log follow only. Browser opening tolerates headless hosts. `LANCE_PORT=8081 ./start.sh` selects a different web/API port; `LANCE_BIND=127.0.0.1` restricts the bind address. Set the same port environment for status/diagnostics. Default bind is 0.0.0.0 for lab LAN access.

## Server machine

Start application → **Server** → listen address `0.0.0.0` (or specific local IP), port `5201` → **START SERVER**. Allow TCP 5201 for control and TCP/UDP 5201 for traffic in your network firewall. The web service uses TCP 8080. Completed local observations appear in Experiments independently of the client machine. STOP SERVER terminates only the process owned by this instance.

The structured receiver uses one-off sessions and automatically rearms. It briefly stops listening between sessions. Current/last client is detected from completed structured output; unavailable current-client information is N/A.

## Client machine: UDP / TCP

Start application → **New Experiment** → enter destination IP/hostname. UDP example: 10 Mbps, 10 seconds, 1 second interval, one stream; click START TEST. Observe TX/RX, receiver jitter/loss, counts and charts when data becomes available. For TCP select TCP: ordinary tests use unlimited throughput; retransmissions appear when reported. Reverse mode makes the server the sender. Cancel with STOP TEST.

iperf3 versions supporting `--json-stream` provide local interval updates through WebSocket. Older versions (including locally validated 3.16) provide structured results at the end of a session; the UI explicitly says Waiting for data. Receiver intervals are available only when server-output JSON includes them. No metrics are fabricated to fill live cards.

## Traffic profiles

Upload `examples/traffic_profile.json` in **Traffic Profiles**, or create stages with Add/Duplicate/Delete/Up/Down. Preview target bandwidth, save and select RUN PROFILE. Configure destination and start. Example contains 13 stages of 10 seconds, from 10 through 200 Mbps and back. Saved profiles can be exported as JSON. TCP profiles use paced `-b`; UDP rates apply **per stream**.

Each stage launches a separate iperf session. A 0.5 s inter-stage pause allows receiver rearm. Actual offsets/gaps, session UUIDs and command arguments are recorded. This is not continuous within-session dynamic bandwidth adjustment.

## Results, charts and reports

Experiments/Reports list real stored runs, with search and protocol filter. Select a run to view configuration, environment, stage sessions, normalized metrics, raw output and charts. CSV/JSON downloads include identifiers/provenance. Chart buttons save PNG/SVG. **Download report / PDF** opens browser print: choose Save as PDF; no server PDF engine is required.

- Database: `data/lanceMetrics.sqlite` (WAL mode)
- Raw client sessions: `data/experiments/<UUID>/stage_N.stdout` and `.stderr`
- Reproducibility configuration: `data/experiments/<UUID>/config.json`
- Normalized client snapshot: `data/experiments/<UUID>/results.json`
- Server observations: `data/experiments/<UUID>/server.json` and `.stderr`
- Profiles: `data/profiles/<id>.json` plus SQLite
- Logs: `logs/lanceMetrics.log`, `logs/backend.log`, `logs/iperf.log`
- Process identities/token: `run/`

Backup database using SQLite backup or after shutdown along with experiment/profile directories. Do not edit the database while the application runs. No automated data deletion is performed.

## Stack and architecture

Python/FastAPI/Pydantic, SQLAlchemy/SQLite, asyncio subprocesses, authenticated REST/WebSocket, React/TypeScript/Vite, Plotly. Central version in backend/app/core.py. Terminal delegates lifecycle to scripts; one FastAPI process serves the built web UI. See [Architecture](docs/ARCHITECTURE.md), [Metrics](docs/METRICS.md), [Roadmap](docs/ROADMAP.md) and [Local validation](docs/VALIDATION.md).

## Validation

```bash
.venv/bin/python -m pytest backend/tests -q
npm run build --prefix frontend
bash -n lanceMetrics install.sh start.sh stop.sh
./lanceMetrics diagnostics
```

Integration tests use localhost real iperf3 (TCP, UDP, reverse, stages, persistence, exports, WebSocket and cancellation), skipping if iperf3 is absent. Tests use a temporary independent data root. Tests require permission to open localhost sockets. Frontend build checks TypeScript. An optional Chrome/Playwright workflow test is available: start the application, then `npm run test:e2e --prefix frontend`. It uses the existing system Chrome on Linux or a Playwright-installed Chromium elsewhere; set PLAYWRIGHT_CHROME to override the browser executable. The test writes genuine localhost observations and a small saved profile into the running installation.

## Troubleshooting

Connection refused: start destination server and check address/port/firewall. Address in use: inspect the occupying process; this tool never kills unrelated processes. iperf3 missing: rerun installer. Backend failure: inspect `logs/backend.log`. Unavailable metrics: inspect raw JSON/version; N/A is intentional. Lost token: use terminal status, or read `run/access.token` locally. Change token only while stopped by removing that file and restarting. After an unexpected crash run stop.sh before start.sh to clean up owned child processes.

## Research limitations

No clock synchronization is assumed; no one-way delay is calculated. Jitter is receiver-specific. UDP receiver expected packet count includes missing datagrams; received counts are explicitly derived. Summaries and interval maxima have different meanings; read METRICS.md before publication. Environment is recorded, but CPU load, routing, network topology, NIC offloads and competing traffic still need experimental control by the researcher. Sender/server independent databases are not automatically synchronized.

The MVP has no remote peer control, dataset replay, dark theme, per-stream/congestion dashboard, or server-generated PDF. Plotly uses a relatively large local bundle (~5 MB uncompressed); Vite reports a bundle-size warning, which does not prevent builds. Starlette currently emits a deprecation warning about its httpx test-client adapter; API tests still pass. macOS support is implemented but needs native acceptance testing. Deployment is intended for trusted laboratory networks: token-protected HTTP is unencrypted; use TLS for untrusted environments. Full validation on two physical hosts is still required.

## Logo, parada pelo script e acompanhamento

O logo usa a imagem original fornecida no login e na barra lateral. Para encerrar o servidor web, abra `./lanceMetrics` e escolha **[3] Stop Web Interface / Parar servidor web**, ou execute `./lanceMetrics stop-web` (`./stop.sh` continua funcionando). A parada também encerra os processos iperf gerenciados. Fechar o navegador ou sair do menu não encerra o serviço. Reinicie com a opção [2] ou `./start.sh`.

Durante um teste, o dashboard e os detalhes mostram **TESTE EM EXECUÇÃO**, tempo decorrido, duração programada, estágio, destino/protocolo e progresso do tempo programado. Conexão, transições e coleta de resultados podem ampliar a duração total. A barra é um acompanhamento visual, não uma métrica de throughput. Versões de iperf sem JSON streaming mantêm TX/RX/jitter/perda como N/A até receberem resultados estruturados.

## Excluir experimentos

A tabela de experimentos tem checkboxes, seleção de todos os itens visíveis, o botão **Excluir selecionados** e uma coluna **Ações** com lixeira individual. A confirmação informa que resultados, medições e arquivos brutos serão removidos permanentemente. Testes em execução/finalização não podem ser excluídos. Um lote é validado por inteiro antes da exclusão; registros ausentes ou ativos impedem a remoção de todos os itens. Arquivos são restaurados se a transação do banco falhar. Profiles são mantidos. Exporte os resultados que deseja guardar antes de confirmar.


## Video Streaming Experiment

The existing project now supports real FFmpeg video transmission independently of iperf3. Use **New Experiment → Experiment Type → Video Streaming** or its sidebar entry. Multiple streaming uploads, ffprobe metadata and source analysis, ordered sequential/concurrent queues, source-preserving remux or controlled H.264, real Receiver JPEG preview, measured UDP/RTP payload counters, optional token-authenticated Receiver peer coordination, partial stop results and per-video exports share the current archive.

Install FFmpeg/ffprobe with `sudo apt-get install -y ffmpeg` on Ubuntu/Debian or `brew install ffmpeg` on macOS; `./install.sh` and Diagnostics check both. Start the Receiver on machine B first, then upload/select videos on Sender A. Concurrent uses ports base/base+2/base+4. Optional Receiver Peer URL/token retrieves correlated RX results; otherwise RX remains N/A at the Sender.

See [VIDEO_STREAMING.md](docs/VIDEO_STREAMING.md) for the complete two-machine workflow, uploads, measurement definitions, APIs, export formats, limits and reproducibility. UDP loss/jitter are N/A; RTP uses sequence observability and RFC3550 jitter. Preview delay and unrelated machine timestamps never establish network one-way latency.
