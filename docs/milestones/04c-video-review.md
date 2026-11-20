# M4C — Saved video synchronized with the trace

```text
Implement docs/milestones/04c-video-review.md. Follow AGENTS.md and update the handoff when finished.
```

## Outcome and dependencies

Play and seek saved camera video with corresponding trace and available audio. Requires M4B plus actual codec/keyframe/timestamp evidence. Read shared references and relevant official/installed SDK frame behavior.

## Visible UI

Real video player, play/pause/seek, recording status, shared trace cursor, still-frame inspection, visible recording gaps and **Verify M4C**. Display whether media synchronization is measured, inferred or unavailable.

## Build

- Verify the real video encoding, initialization/keyframe requirements, cadence and timestamp units. A callback buffer is not assumed to be a complete playable frame/clip.
- Assemble bounded recording segments and produce a browser-playable container/derivative. Prefer remuxing when compatible; disclose any transcoding and preserve source metadata.
- Package tested decoder/muxer versions in the image. Bound CPU/work queues, segment size, disk usage and retention; expose lag/drops/full-disk errors.
- Map media offsets, source clocks and collector time explicitly. Reconnects/clock resets become separate segments; missing intervals do not disappear into apparently continuous footage.
- Synchronize player and trace cursor with actual timing evidence. Audio/video alignment requires a verified mapping; unknown offsets stay unknown.
- Preserve finalized clips through crashes/recreation and mark incomplete segments. Saved playback and seeking never transmit robot commands or media.

## Quick verification

| Mode | Operator action | Expected visible result |
| --- | --- | --- |
| Fixture | Play/seek a clip with known audiovisual markers | Cursor/media alignment within recorded tolerance; controlled-fixture target ≤250 ms |
| Fixture | Missing keyframe or truncated segment | Partial/unavailable playback with explanation |
| Fixture | Dropped frames, reconnect or clock reset | Visible gap/segment boundary, no fabricated continuity |
| Compose | Recreate and seek saved clip | Finalized media remains playable and associated |
| Robot | Record an identifiable short scene | Real clip plays; actual codec and timing alignment documented |

Automate stream ordering, segment lifecycle, clock mappings and failures. Browser play/seek actual encoded media; record browser/image architecture and codec versions.

## Release gate

A real saved clip plays/seeks after recreation with correct evidence association and documented synchronization tolerance. Unsupported/unsynchronized media is explicit. Fixture playback does not prove hardware capture.

## Scope boundary

Low-latency live streaming/WebRTC, telepresence, multiple cameras, fleet video and automatic physical verification. Saved video is the required first delivery.

## Delivery record

- Implementation: Not started
- Changed paths / run commands / migrations: Pending
- Versions / codecs / timing mappings: Pending
- Automated + fixture UI checks: Not run
- Compose checks: Not run
- Real-robot checks: Not run
- Evidence / synchronization tolerance / limitations: Pending
- Next action: Implement M4C after M4B; finish outstanding M5/M6 work.
