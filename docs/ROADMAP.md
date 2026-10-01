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
