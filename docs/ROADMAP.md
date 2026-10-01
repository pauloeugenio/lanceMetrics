# Roadmap

## Phase 1 — implemented MVP
Client/server iperf3 TCP/UDP and reverse mode, profiles, raw preservation, aggregate parsing, SQLite, web experiment archive, charts, CSV/JSON, printable reports, token access, terminal installation/lifecycle/diagnostics, local integration tests.

Remaining hardening: native macOS acceptance testing, broader automated browser interaction coverage, granular permissions/TLS setup, persistent streaming server observations without rearm gaps, precise server/client correlation, stream/congestion UI, server-generated PDF, profile editing history, improved socket owner diagnostics, dark theme.

## Phase 2 — dataset replay
Implement TrafficGenerator for actual kinematic dataset UDP sender/receiver, uploader, sequence numbers and timestamps; do not use iperf3 as payload sender. Preserve payload schema and sequence logs. Clock-aware one-way delay is valid only with demonstrated synchronization and quantified error.

## Phase 3 — distributed experiments
Authenticated peer status/start/stop with predefined operations, UUID/session/stage exchange, explicit synchronization and provenance, experiment consolidation, multi-node orchestration and clock synchronization awareness.

## Phase 4
Multiple flows and network topology experiments, concurrent isolated runs and more advanced statistical analysis.


## Video Streaming — implemented extension

Multiple streaming uploads; safe UUID library; real ffprobe metadata/packet-window source analysis; Preserve Source and controlled H.264; sequential/concurrent UDP and RTP MPEG-TS; actual received-video preview; separate payload measurement and RTP sequence/jitter observability; shared archive and per-session exports; owned process shutdown; optional authorized peer coordination with real RX retrieval.

Next: native macOS and real multi-machine WAN/5G acceptance, stronger RTP sequence-source validation and loss outside observation boundaries, RTCP integration, verified NTP/chrony/PTP provenance and combined clock-aligned metrics, reconstructed receiver media with PSNR/SSIM/VMAF, library lifecycle/quota management and optional audio-capable preview. Existing dataset replay and distributed clock work remain on the roadmap.
