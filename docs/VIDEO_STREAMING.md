# Video Streaming Experiment

Video Streaming extends the existing LANCE Metrics experiment archive, authenticated API, SQLite database, WebSocket updates, process manager, charts and printable reports. It never sends video through iperf3.

## Install and start

Ubuntu/Debian: `sudo apt-get install -y ffmpeg`; macOS: `brew install ffmpeg`. The updated `./install.sh` checks both `ffmpeg` and `ffprobe`. It does not install Homebrew automatically. Run `./lanceMetrics` → Diagnostics to see each tool's version. This Ubuntu installation also includes official FFmpeg/ffprobe packages under `.venv/video-tools`, so the module works without sudo. The application prefers system tools and falls back to that local installation; its libraries are passed only to video subprocesses. This optional local installation is specific to this machine, not a bundled macOS/Linux installer artifact. Start the web interface with the existing script. HTTP/token traffic should stay on a trusted laboratory network or use an HTTPS reverse proxy.

## Receiver (machine B)

1. Open **Video Streaming**, select **Video Receiver**.
2. Set Listen Address `0.0.0.0`, Base Port `5000`, matching UDP or RTP/UDP transport.
3. For concurrent runs set stream count to the number of selected videos; ports are `5000, 5002, 5004, …`.
4. Click **START VIDEO RECEIVER**. Status becomes `WAITING_FOR_STREAM`. Actual reception changes it to `RECEIVING`.
5. Keep this screen open for the actual decoded **LIVE VIDEO PREVIEW**, sender IP, session metadata and measured RX counters. Incoming sessions also appear in Experiments.

Only sockets created by this receiver are opened. A conflict is rejected before any listening sockets are retained. Firewall rules must permit the chosen UDP ports and, for optional coordination, the LANCE HTTP API port. No firewall configuration is changed automatically.

## Sender (machine A)

1. Open **New Experiment → Experiment Type → Video Streaming**, or use its sidebar entry.
2. Select **Video Sender**, select multiple files in one chooser or drop them together. Formats: `.mp4 .avi .mkv .mov .mpg .mpeg`.
3. Upload progress is shown per file and across the batch. Successful uploads form a single-copy UUID library. Original names remain metadata; they never form storage paths.
4. Select the library videos or **Select All**. Queue operations: Move Up, Move Down, Remove and Deselect All. Remove changes the queue, not the library file.
5. Enter the destination IP/hostname, base port, transport and playback mode. **Real-time** uses FFmpeg `-re`; Maximum speed does not.
6. Choose Sequential (one stream after another) or Concurrent (one independent stream and port per selected video).
7. Choose Preserve Source or Controlled Bitrate. Controlled supports H.264, arbitrary positive configured Mbps up to the documented schema bound, presets ultrafast/superfast/veryfast and optional zerolatency. Common bitrate suggestions are 5/10/20/30/50 Mbps.
8. Click **Run Selected Videos / START EXPERIMENT**. Details show active filename, video index, playback progress, remaining content time, next video, FFmpeg state and distinct Source/Target/TX/RX metrics.

Concurrent transcodes can be CPU intensive. Port allocation alone cannot detect an unrelated service on a *remote* machine. Receiver socket reservation and optional peer preparation provide the authoritative destination conflict check.

## Optional receiver peer coordination

Open **Receiver Peer** on the Sender. Enter the Receiver LANCE URL (for example `http://192.168.150.2:8080`) and its access token. The token is used only for authenticated predefined video API operations; it is excluded from the experiment config, manifests, process arguments and exports. Redirects are refused so credentials are not forwarded to another origin.

The Receiver must first be explicitly started with matching transport and enough ports. Sender checks readiness, announces each experiment/session/video UUID and source metadata, requests decoder preparation, transmits, requests session finalization, retrieves RX results and proceeds to the next video. Concurrent streams prepare independent ports. Completion finalizes the correlated Receiver experiment. Stop notifies the Receiver, stops the corresponding decoders and preserves partial records as `ABORTED`; the armed Receiver can accept future experiments. Peer control responses are bounded to 5 MiB per call; unusually long sessions can exceed this result-transfer limit and require future paginated/streaming peer retrieval. Peer failures are reported, never replaced with invented receiver measurements.

Without peer coordination, the Receiver discovers streams when data arrives, uses local UUIDs and identifies the sender/port. Original filenames and source metadata are unknown. An idle interval closes a manual session; default 2 seconds, and the unpaired sequential sender inserts a 2.5-second gap. Keep the Receiver idle boundary at its default for this mode. A long network stall can therefore split a manual video. Without an announcement channel, exact cross-host video/session correlation cannot be inferred from raw MPEG-TS. Use the peer fields when per-video names and cross-host results are needed.

## Upload and analysis bounds

Each selected file is sent as a separate raw HTTP streaming upload. Two browser uploads run concurrently. The API iterates request chunks directly to disk, without buffering a whole file or a whole multipart batch in memory. A content-type check, supported extension and file-only ffprobe validation are required. Invalid or partial files are removed.

`LANCE_VIDEO_MAX_BYTES` defaults to 2 GiB per file; `LANCE_VIDEO_LIBRARY_BYTES` defaults to 50 GiB total. Set these environment variables before starting the service. At most 100 videos can be selected in an experiment/batch. ffprobe metadata has a 30-second timeout; temporal packet analysis has a 10-minute timeout and 100000-window bound. Analysis is streamed from ffprobe and stores per-window byte totals, not the packet list. It may need a larger window for very long files. Successful library uploads are not deleted when an experiment is deleted.

The library shows real duration, size, container, video/audio codec, dimensions, FPS, average container bitrate and stream bitrate when available. Missing metadata stays null/N/A. Analyze Temporal Bitrate groups actual packet sizes from the original video/audio streams by presentation time; default 1 second. It excludes container overhead and can differ from the file's average container bitrate. Source windows are snapshotted before transmission, available in live charts and preserved in each experiment session for export. The final window uses its observed remaining content duration when known.

## Transport and encoding

UDP sends MPEG-TS datagrams. RTP/UDP sends MPEG-TS in RTP payload type 33, with the 90 kHz RTP clock. Python ingress/egress relays count real datagrams and relay their payload without changing the experimental packet format. The Receiver strips the RTP header only for its local MPEG-TS decoder. RTCP control traffic is not part of these payload counters. Ports are allocated at +2 to avoid ambiguity and leave adjacent ports available for future RTCP integration.

Preserve Source uses `-c copy` and remuxes compatible source video/audio into MPEG-TS; no 10 Mbps target is imposed. Container headers, RTP/UDP overhead, timestamps and pacing can still change transmitted bitrate. Unsupported video codecs are rejected with instructions to use Controlled Bitrate; audio/container combinations may also fail in FFmpeg, with the real log preserved. There is no silent transcode pretending to preserve the original source.

Controlled Bitrate uses libx264 and optional AAC audio, `-b:v`, `-maxrate`, `-bufsize`, selected preset and zerolatency. This controls the encoder rather than guarantees constant TX rate. Preserve Source may retain H.265/MPEG codecs; H.264 is the controlled encoder currently supported.

## Metrics and scientific interpretation

- **Source Average Bitrate**: ffprobe-reported average container bitrate. **Temporal Source**: original encoded packet payload bytes/window.
- **Configured Target**: requested encoder video rate, null in Preserve Source. Audio/mux/transport overhead is additional.
- **Actual TX**: UDP payload bytes successfully submitted through the Sender relay's socket, including RTP headers for RTP. This is application submission, not proof of NIC delivery or reception. Datagram count is the actual successful send count.
- **Actual RX**: UDP payload bytes and datagrams returned by the Receiver's socket, before the preview relay. Decoder errors or preview frame drops do not remove already received network bytes.
- Interval bps = newly observed payload bytes × 8 / actual monotonic interval seconds. Byte/packet fields in timeline rows are **cumulative** per session; do not sum cumulative rows.
- UDP loss and jitter: **N/A**, because raw MPEG-TS over UDP does not provide reliable packet identity or network timing.
- RTP loss: gaps in extended sequence numbers from first through highest observed packet, with wrap, duplicates and reordering accounted for. Packets before the first arrival and lost after the final observed sequence cannot be inferred. Missing SSRC/protocol consistency invalidates loss/jitter observability. Sequence tracking is bounded to 2000000 unique packets, after which loss is N/A while reception continues; unusual extreme sessions must not be interpreted as complete sequence accounting.
- RTP jitter: RFC3550 interarrival jitter using receiver monotonic time and the 90 kHz RTP timestamp, not independently compared machine wall clocks. It is receiver userspace interarrival timing, not hardware timestamping or one-way latency. Collector scheduling/CPU load can influence it. Observed gaps cannot distinguish path loss from receiver socket-buffer drops.
- Session average TX/RX divides session bytes by its measured elapsed time. Aggregate TX/RX divides total bytes by the overall experiment wall duration, including preparation/transitions and counting simultaneous streams against the same wall interval. Aggregate loss uses sum(lost)/sum(expected), never mean(percent). Missing required session values yield N/A. Aggregate jitter is weighted by received packet count over available complete session observations.

Remote RX chart rows are aligned to the Sender's nominal session start for visual comparison only, and include `receiver_elapsed_time` and `clock_alignment` provenance. This does not establish clock synchronization. Source windows use content time; on real-time playback they can also be positioned relative to session start. Maximum-speed playback keeps content-time Source in a separate chart because content time and wall time differ.

Combined clock-aligned CSV and one-way delay are explicitly unavailable until validated NTP/chrony/PTP synchronization and its uncertainty are recorded. They are never estimated from unrelated UTC timestamps. PSNR, SSIM and VMAF are future services requiring reconstructed receiver media and source/receiver frame alignment; this release does not claim those metrics.

## Preview

Receiver relays decoded local MPEG-TS to FFmpeg, which produces JPEG frames at up to 8 fps and width/height bounded to 640×360. An authenticated WebSocket sends the latest frame to the browser. Buffers retain the latest frame rather than a playback history. The browser displays the actual received video, with no fabricated animation. The preview needs decodable keyframes and enough input for probing; startup and CPU load can affect when the first frame appears. This preview omits audio and reduces visual resolution/frame rate; it does not change the experiment stream's encoding or datagram metrics. Preview latency includes decoder/relay/browser buffering and is **not network latency**.

## Persistence and export

New additive SQLite tables: `video_assets`, `video_sessions`. Existing experiment, measurement and profile tables remain intact. `create_all` creates the new tables at startup; session foreign keys cascade on experiment deletion. Session snapshots also live in the existing experiment JSON for history and WebSocket clients. An explicit correlation UUID links sender and receiver when local database UUIDs must be distinct.

```
data/videos/<asset UUID>.<extension>
data/experiments/<experiment UUID>/
  config.json
  environment_sender.json     # or environment_receiver.json
  video_manifest.json
  sessions/<session UUID>/
    metadata.json
    ffmpeg_sender.log         # on sender
    ffmpeg_receiver.log       # on receiver
    metrics_sender.csv
    metrics_receiver.csv      # also retrieved by an authorized sender peer
    source_bitrate.csv
    receiver_result.json      # when coordinated
```

Download experiment JSON, manifest JSON, all/per-video timeline CSV, session results CSV, sender/receiver CSV and source CSV. Charts reuse the application's Plotly PNG/SVG buttons; Report/PDF uses browser printing. Select a video session to inspect its complete metadata and filter charts/exports. Combined Metrics CSV returns a clear unavailable reason until clocks are validated. Experiment deletion removes measurements/session records/raw experiment files but preserves the library.

Processes use the existing ProcessManager PID/create-time/argument identity records and list arguments without a shell. Stop affects only owned FFmpeg processes, never `pkill`/`killall`. Web-server shutdown also stops video tasks and listening sockets.

## APIs

All HTTP routes below require the existing Bearer token and mutation origin policy:

- `GET /api/video/status`, `GET /api/video/library`
- `POST /api/video/library/upload?filename=<original>` with raw video body
- `POST /api/video/library/{uuid}/analyze` with `window_seconds`
- `POST /api/video/experiments/start`, `POST /api/video/experiments/{id}/stop`
- `POST /api/video/receiver/start`, `POST /api/video/receiver/stop`
- `GET /api/video/peer/ready`, `POST /api/video/peer/prepare`, `/finish`, `/complete`
- `GET /api/video/experiments/{id}/export/{json|manifest|metrics|sessions|sender|receiver|source|combined}`; optional `session_id`
- `GET /api/video/experiments/{id}/source-data`
- `GET /api/video/experiments/{id}/sessions/{uuid}/log/{sender|receiver}`
- `/ws/video/preview/{port}` authenticates with the first `{ "token": "…" }` message, matching the existing WebSocket pattern.

Existing `/api/experiments`, export, deletion and `/ws/experiments/{id}` remain the shared archive interfaces. Legacy `/api/tests/{id}/stop` also dispatches video stops appropriately.

## Validation

Run `.venv/bin/python -m pytest backend/tests -q`, `npm run build --prefix frontend`, and `npm run test:e2e --prefix frontend` with the bundled server running. Real integration tests are skipped only when FFmpeg/ffprobe are unavailable. They generate small synthetic videos in temporary directories, upload two files, analyze the source, transmit sequential/concurrent UDP and RTP, confirm RX bytes/decoded preview frames/session persistence, and verify owned processes disappear. A separate two-instance test exercises real HTTP peer preparation, Controlled Bitrate, receiver result retrieval and remote abort. No large test binary belongs in Git.

The implementation uses portable Python sockets/asyncio and FFmpeg. Native macOS and real two-machine 5G/6G acceptance require testing in those environments; localhost validation does not establish WAN performance or clock accuracy.

References: [FFmpeg formats](https://ffmpeg.org/ffmpeg-formats.html), [FFmpeg protocols](https://ffmpeg.org/ffmpeg-protocols.html), [RTP RFC3550](https://www.rfc-editor.org/rfc/rfc3550).
