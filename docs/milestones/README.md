# Milestone roadmap

Eight achievable releases, retaining M4A/M4B/M4C as the three media stages. Each ships a usable visible UI, guided quick checks, automatic diagnostics and a cumulative Docker Compose deployment. Current implementation status is authoritative in [STATUS](../STATUS.md).

| ID | Contract | Dependency | Visible result |
| --- | --- | --- | --- |
| M1 | [Connection](01-connection.md) | None | Connection console, setup and guided checks |
| M2 | [Conversations](02-conversations.md) | M1 foundation; real reply provider for hardware gate | Saved sessions, inputs and replies |
| M3 | [Horizontal trace](03-turn-trace.md) | M2 | Parallel time lanes, cursor and evidence inspector |
| M4A | [Audio](04-audio-review.md) | M3; raw audio and ASR/TTS for hardware gate | Players, waveform and trace alignment |
| M4B | [Images](04b-image-review.md) | M4A; supported camera source | Thumbnails and captured-frame preview |
| M4C | [Video](04c-video-review.md) | M4B; codec/timestamp evidence | Saved video play/seek with trace |
| M5 | [Processing](05-processing.md) | M3 + M4A; actual provider calls | Provider spans and failure attribution |
| M6 | [Robot outcomes](06-robot-outcomes.md) | M3; supported state publication | Movement/manipulation/action/speech evidence |

Default order follows the table. M6 may follow M3 early to establish robot-state coverage. M5 can ship after M4A without waiting for images/video. M6 only needs M4A when comparing reports with recorded audio. One chat implements one requested milestone; these dependency options do not expand its scope automatically.

M1–M3 produce a useful text recorder/debugger. M4A–M4C add media in manageable steps. M5–M6 explain application processing and reported robot outcomes. Minimal inference belongs in the first stage requiring it, not postponed until the tracing stage.

## Start a clean chat

Use the per-milestone prompt at the top of its contract, or replace the path below:

```text
Implement docs/milestones/01-connection.md.
Follow AGENTS.md. Read current status and that milestone's required references.
Deliver its usable UI, Docker Compose deployment, guided passing/failure checks,
and automatically saved diagnostic logs. Preserve earlier milestone behavior/data.
Continue independent fixture work if hardware access is missing; label hardware
checks pending. Record actual checks and update the milestone delivery record,
docs/STATUS.md and tested run instructions before finishing. Keep later stages out
of scope. Do not repeat the historical fresh-start reset.
```

## Required shared references

Every milestone uses [architecture](../ARCHITECTURE.md), [UI specification](../UI-SPEC.md), [verification](../VERIFICATION.md) and [Compose requirements](../DEPLOYMENT.md). SDK integrations additionally use [SDK notes](../SDK-NOTES.md), official references and the actual installed package.

Fixture readiness is not hardware acceptance. If an implementation dependency is missing, identify it precisely; if only hardware validation is blocked, complete valid independent fixture work and leave that gate pending. Each contract ends with the handoff fields the next chat needs.
