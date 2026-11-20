# Architecture and evidence contract

## Scope and implementation direction

One A3 Ultra, one configured SDK agent and one operator. Build cumulative releases with Python, FastAPI/Jinja and small browser JavaScript modules. Use SQLite from M2 and filesystem media storage from M4A. One Docker Compose service owns one SDK connection and one worker process. Choose and lock compatible package/runtime versions in M1; no prior environment is authoritative.

Use the [UI specification](UI-SPEC.md) for product behavior, [deployment contract](DEPLOYMENT.md) for runtime, and [verification contract](VERIFICATION.md) for acceptance. Introduce files as needed rather than prebuilding later milestones.

Suggested responsibility boundaries:

```text
src/linksoul_studio/
  app.py                 # composition and lifecycle
  config.py              # validated server-side settings
  sdk/                   # real and fixture adapters
  events/                # normalized collection, ordering, correlation
  storage/               # SQLite migrations and media references
  diagnostics/           # redaction, rotation, incident summaries
  verification/          # scenarios, evidence-derived checks, reports
  web/                   # routes, templates and browser assets
tests/
docs/verification/       # curated validation summaries, no secrets
data/                    # ignored local runtime data; /data in container
```

## SDK and provider boundary

Normalize inbound callbacks and outgoing response operations behind an adapter. Fixture scenarios use the same collector/storage/presentation path. Register one passive callback before initialization; initialize/release with the application lifecycle. Prevent duplicate SDK owners, reloaders and multiple web workers.

Begin M1 with a minimal isolated configuration appropriate to actual supported input, preferably ASR text for simple connection testing. An arrival-only test or inference-unavailable response is not a working conversation. M2 adds a minimal real text reply provider. M4A verifies the target `AudioVideo2TtsCallback` and integrates ASR/model/TTS as required. M4B adds media capture; vision inference is optional for review. M5 instruments providers already used by the application.

Callbacks must stay responsive. Use bounded collection and background storage/decoding/muxing; expose overflow, dropped chunks and lag. Preserve required response ordering. Capture only traffic/state actually exposed to this agent; access to all built-in behavior is not assumed.

Robot inputs arrive through LinkSoul to the application; application responses return through LinkSoul. If a future UI offers typed text or uploads, label them application-originated and integrate a verified route; a passive callback is not an arbitrary PC-to-robot upload API.

## Event identity and timing

Every normalized record includes application record ID, schema version, `fixture`/`robot` mode, connection-run ID, kind, source, direction, collector UTC timestamp and sequence. Add available agent/event/item/task/request/flow IDs and original source timestamp without inventing them. Our session/trace/span IDs are application IDs, not assumed SDK fields.

- Correlate by supported identifiers. Keep robot-wide or ambiguous evidence on a session-level unassigned track; never attach it merely to the newest turn.
- A shared event ID can cover many valid chunks. Preserve chunk order and deduplicate history snapshots by their documented identity, not by treating every event ID as a unique record.
- Use monotonic time within one collector run for local durations. Retain UTC/source clocks separately. Clock resets and reconnects must remain visible; unrelated clocks cannot establish latency.
- Record stream start/end/partial/error state. Discrete events use markers; durations require observed boundaries. State bands hold the last report with age/staleness and gaps, not continuous physical measurement.
- Media time mappings connect playback offsets with capture/receipt evidence and disclose uncertainty. Time alignment is not causal turn association.

## Evidence and robot outcomes

Use `SDK captured`, `Application measured`, `Robot reported`, `Inferred`, `Unavailable`. An attempted send is distinct from confirmed delivery, acceptance, running, completion, failure and interruption. Only supported evidence advances the lifecycle; silence/timeout leaves execution unconfirmed unless an actual failure is reported.

Store original supported state shapes while deriving readable summaries. Differentiate manipulation capability/mode from action progress or arm joint telemetry. Local pose/semantic location is not GPS. Module documentation does not guarantee publication by this robot.

Normal review never sends robot commands. Motion verification uses a separately scoped operator action with a supported capability; the monitor observes it.

## Persistence and diagnostics

All durable state resides under the configurable data directory (`/data` in Compose):

| Store | Content | First release |
| --- | --- | --- |
| `logs/app.jsonl`, `logs/sdk.jsonl` | Sanitized rotating diagnostics | M1 |
| `verification/fixture/`, `verification/robot/` | Atomic check reports with versions/evidence IDs | M1 |
| `linksoul.sqlite3` | Sessions, events, text, spans, state and media metadata | M2 |
| `media/` | Original supported captures and bounded playback derivatives | M4A onward |

Logs are not the conversation/media store. Exclude credentials, authorization/signature headers, media and full conversation/provider bodies from diagnostics. Inspect SDK logging before enabling it; use a sanitized bridge where SDK messages contain sensitive content. Exports exclude recordings/conversation content by default.

Set explicit rotation and retention limits, visible storage health and bounded media work. Write media/reports atomically where applicable; reconcile missing/orphaned files. Media routes use validated IDs, not arbitrary paths. Migrations preserve existing records; rollback declares compatible schema or restores a complete backup.

## Decisions to record during implementation

Record tested versions, real input/provider choices, state schemas observed, capture formats, synchronization tolerances and any departures from this architecture. Keep historical decisions concise and distinguish a proposal from an implemented/verified behavior.

## M1 implementation decisions — 2026-11-20

FastAPI serves a plain HTML/CSS/JavaScript console with one-second state polling. One lifecycle-owned service consumes a bounded 512-event queue; callbacks enqueue fixed metadata only. Live history retains 120 entries, a check up to 2048 entries; overflow invalidates verification. A monotonic clock measures freshness; UTC timestamps and run/sequence/event IDs identify evidence. Only online discovery selects an agent; reconnect invalidates prior presence/input and repeated or missing event IDs cannot satisfy new-input verification.

A filesystem ownership lock and one Uvicorn worker protect the SDK/data owner. Atomic mode-separated JSON reports are manually retained; rotating metadata logs contain no formatted SDK messages, callback bodies or media. The fixture storage-failure scenario performs a real failed write on an isolated temporary path, then saves a Failed report to the working store. Actual persistent-store failures prevent a saved-success claim.

The pinned SDK adapter uses Asr2LlmCallback only. Its transport subclass enforces certificate/hostname validation and surfaces close/error callbacks absent from the public API. These private hooks are an explicit compatibility dependency and must be retested on upgrade. Response attempts have separate outbound evidence and never imply delivery/execution. Later timeline/media work remains outside M1.

## M2 implementation decisions — 2026-11-20

Studio 0.2.0 introduces schema version 1 in `linksoul.sqlite3`. Migration from M1 creates the database without changing its logs/reports; newer unsupported schema versions fail visibly. Sessions are mode/agent/connection scoped. Each gateway reconnect, selected-agent offline boundary and service restart closes the prior session; unfinished pending turns become incomplete. IDs from different connections do not establish unique associations by themselves. History snapshots stay separate from outgoing text; ambiguous/missing identities remain unassigned. Snapshot deduplication uses agent, mode and the bounded normalized snapshot, while each streaming chunk receives its own record and sequence, including repeated identical chunks.

One 32-entry text queue and one background worker perform persistence/inference outside the SDK callback. The existing 512-entry metadata queue remains. SQLite operations are serialized and transactional; the database uses WAL, foreign keys, a 128 MiB page cap and a 1 MiB retained WAL journal limit. Default retention is 100 sessions per mode, 200 turns/session, 4,000 events/session and 8,192 characters/text event. Oldest sessions expire when new sessions exceed the limit. Capture limits/write failures stay visible and invalidate M2 checks; automatic database shrinking is unnecessary because freed pages are reused. Backups must cover the entire stopped volume, including any WAL files.

M2 is an explicitly selected connection operation using the same single Asr2LlmCallback. The M1 Connect control keeps its isolated inference-unavailable behavior. M2 optionally calls a server-configured Ollama `/api/chat` provider with the current input only, no tools or skills, a bounded response and timeout. Generated text is persisted before SDK calls. Calls run interrupt → text delta → item done → reply done, with attempted/returned records. SDK return does not prove transport acceptance or playback. Inference failure, missing identity, conflicting repeated requests, oversized input or connection change prevents a second/inappropriate reply. Fixture scenarios use the same SQLite event/turn path, with simulated sources and no SDK sends.

M2 restart verification checkpoints a digest of all session events and input/reply associations. Only a different service run with the same digest and at least three complete turns can pass the reopen check. Reports contain IDs and checks, not conversation bodies. Detailed spans, media and execution observation remain later stages.
