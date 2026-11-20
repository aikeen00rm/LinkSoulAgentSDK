# M4A — Captured audio and playback

```text
Implement docs/milestones/04-audio-review.md. Follow AGENTS.md and update the handoff when finished.
```

## Outcome and dependencies

Hear recorded input/output and compare them with text and the trace. Requires M3; real raw-audio capture plus ASR/TTS providers are hardware dependencies. Read shared references, SDK notes, official callback contract and installed code.

## Visible UI

Separate input/output players, actual waveforms, capture settings/coverage, partial/missing recording labels, synchronized trace cursor and **Verify M4A**. Label output as generated/sent audio rather than sound independently recorded from the robot speaker.

## Build

- Verify and integrate the target `AudioVideo2TtsCallback` on the isolated agent, retaining the earlier test configuration explicitly. One passive callback is active at a time. Confirm configuration and response ordering before changing the pipeline.
- Integrate minimal application ASR/model/TTS needed for a working conversation. Provider details beyond useful boundary/error reporting belong to M5.
- Capture exposed input/output chunks, verified codec/sample rate/channels, original timing, sequence, source and completion state. Bound queues and perform assembly/I/O off callbacks.
- Persist media and references with atomic completion/partial status, retention, access controls and orphan reconciliation. Keep media outside logs/default exports.
- Provide actual browser playback/seek linked to trace time. Use true timing alignment where available; otherwise label turn-level/uncertain alignment. Word timings require actual evidence.
- Bundle required codecs in Compose and document media migrations/backup. Capture disabled, unsupported path, corrupt/missing media and disk/write errors remain visible.

## Quick verification

| Mode | Operator action | Expected visible result |
| --- | --- | --- |
| Fixture | Play known input/output files and seek | Audible correct recordings with aligned cursor |
| Fixture | Recreate container and replay | Media and turn association survive |
| Fixture | Disable capture or use corrupt/partial media | Explicit coverage/failure state, usable text/trace |
| Fixture | Exercise storage/queue limits | Visible loss/error without blocking SDK callback processing |
| Robot | Speak a known phrase and interrupt a reply | Available recordings match the turn; partial output is labeled |

Automate stream assembly, association, limits and failure handling. Browser-play real encoded fixtures; a decorative waveform does not pass.

## Release gate

Available input/output recordings play and seek after recreation with correct associations. Actual supported directions/codecs are documented; missing capture is not passed through fixtures. Review playback never sends robot commands.

## Scope boundary

Camera capture/playback ships in M4B/M4C. No inferred word timing or independent speaker verification.

## Delivery record

- Implementation: Not started
- Changed paths / run commands / media migrations: Pending
- Versions / callback / codecs / providers: Pending
- Automated + fixture UI checks: Not run
- Compose checks: Not run
- Real-robot checks: Not run
- Evidence / alignment tolerance / limitations: Pending
- Next action: Implement M4A after M3; then M4B. M5 can also start after M4A.
