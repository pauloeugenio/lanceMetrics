# LANCE Metrics: measurement semantics

All throughput values use bits/s internally and decimal Mbps in charts. Bytes are payload/transfer bytes reported by iperf3; they are not Ethernet wire utilization. NULL means unavailable, never zero. Rows retain role, stage, session, duration and reporting provenance.

| Metric | Measurement location | Unit | Interpretation |
|---|---|---|---|
| Target bandwidth | Requested configuration | bits/s | UDP `-b` is **per stream**; displayed aggregate multiplies by stream count. TCP single tests are unlimited; TCP profiles use `-b` pacing. Target is not a measurement. |
| Sender throughput | Data sender | bits/s | iperf's bytes/time at origin, not proof of destination delivery. |
| Receiver throughput | Data receiver | bits/s | Delivered bytes/time at destination. Receiver and sender summary durations can differ. |
| Transfer | Respective sender/receiver | bytes | Independently reported bytes. Never substitute TX for RX. |
| Jitter | UDP receiver | ms | iperf's smoothed interarrival transit variation estimator; not latency, one-way delay, or sender jitter. |
| Loss | UDP receiver | datagrams / % | Sequence-based missing datagrams reported by receiver. Reordering and late arrivals can affect observations. |
| Datagrams sent | UDP sender | count | Sender reported packet count. |
| Datagrams received | UDP receiver | count | iperf receiver `packets` is expected total including missing packets; received is explicitly derived as `packets - lost_packets`. Raw counters remain available. |
| TCP retransmissions | TCP sender | count | Retransmitted segments when platform/version provides them. Not application packet loss. |

`sum_sent` and `sum_received` define end-summary roles even in reverse mode. Standalone server observations deliberately retain only the locally observed role; unavailable remote-role aggregates can be zero placeholders in iperf JSON and are left NULL by LANCE Metrics. Interval `sender` flags define role. Receiver jitter and loss never come from a sender-labelled interval. Older UDP `end.sum` can mix roles: only receiver statistics are extracted; ambiguous throughput remains NULL.

End summary throughputs are weighted by the actual iperf-reported duration for their respective sender/receiver roles across sessions, excluding inter-session gaps. Missing durations produce NULL rather than an assumed estimate. Interval maxima are maxima of available interval observations, not instantaneous peaks. Summary jitter across stages is a duration-weighted descriptive statistic; it is not a pooled RFC jitter estimator. Packet counts and bytes sum across sessions; combined loss is recomputed from total missing/expected datagrams. If a metric is absent from any completed stage, its combined experiment summary remains NULL; session summaries retain any available partial observations.

JSON streaming is enabled only when `iperf3 --help` advertises it. Older versions use `-J` and update structured plots after the session ends. `--get-server-output` can include receiver intervals when supported; those remain separate observations. No wall-clock alignment across machines is claimed. Datapoints use session-relative interval time plus actual local stage offsets. Client-retrieved remote interval time is an approximate session-relative comparison, not synchronized timestamps.

Profiles run distinct sessions with at least 0.5 seconds between stages for server rearm. Startup, control exchange and rearm add measured gaps. Do not interpret profiles as continuously varying rates in a single flow. Servers use one-off JSON sessions with automatic rearm, so there is a brief unavailability window between sessions.

Raw per-stream data, congestion details and CPU observations remain in JSON. The current UI normalizes aggregate metrics, not all per-stream fields. Maximums from unavailable intervals remain N/A. Stopped/crashed sessions preserve raw partial output; they are not valid completed runs.

Primary references: [iperf3 invocation](https://software.es.net/iperf/invoking.html), [iperf3 source](https://github.com/esnet/iperf), [UDP summary role correction](https://github.com/esnet/iperf/issues/1218).


## Video metric provenance

Video Source Average is ffprobe container bitrate; source temporal windows sum original encoded packet bytes and exclude container overhead. Target is the configured video encoder rate and is null in Preserve Source. Actual TX counts UDP payload successfully submitted by sendto; actual RX counts payload returned by recvfrom. Neither uses ffprobe bitrate or FFmpeg progress size as a network counter. Payload includes MPEG-TS and RTP headers when selected, excludes IP/UDP/link headers, and differs from physical NIC throughput. Packet/byte timeline counters are cumulative per session.

Raw UDP has no reliable sequence identity: loss/jitter are null. RTP MPEG-TS type 33 tracks extended sequences, unique reception, gaps, wrap and reordering; loss outside the first/highest received sequence is unknown. Sequence tracking is bounded and turns loss unavailable when exhausted. Jitter uses RFC3550 interarrival smoothing with a 90 kHz clock; session jitter averages those receiver observations, aggregate jitter weights by received packet count. Aggregate loss is total lost/total expected. Aggregate throughput divides total bytes by experiment wall time, including concurrent overlap and transitions. Missing input metrics yield null/N/A.

Receiver rows imported by a peer are aligned by nominal session start for plotting, labeled as unsynchronized, and cannot measure one-way delay. Combined clock-aligned CSV requires verified synchronization and is unavailable. Browser preview frames and latency never replace experimental stream/network metrics. Detailed formulas and limitations: [VIDEO_STREAMING.md](VIDEO_STREAMING.md).
