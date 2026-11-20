# Project status

Updated: 2026-11-20 (Australia/Melbourne).

## Current handoff

M2 saved-conversation implementation is ready for hardware verification. Studio 0.2.0 adds versioned SQLite sessions/turns/events, ordered text reconstruction, separate history/unassigned evidence, a session/turn browser, bounded storage, optional Ollama text replies and guided restart/failure checks. M1 connection behavior and saved reports are preserved. All 35 automated checks, fixture browser scenarios and Compose build/health/recreation passed. See [M2 evidence](verification/m2-2026-11-20.md).

Open [conversation review](http://127.0.0.1:8001/conversations) or [M1 connection](http://127.0.0.1:8001/). Robot access and a live model remain unconfigured; neither milestone is hardware-accepted.
The durable product requirements are the Markdown documents in this repository. The user owns one A3 Ultra, wants the horizontal media/trace UI, and will use a separate chat for each milestone.

| Milestone | Implementation | Fixture/UI checks | Compose checks | Robot checks | Acceptance |
| --- | --- | --- | --- | --- | --- |
| [M1 Connection](milestones/01-connection.md) | Ready for verification | Passed | Passed | Not run | Pending hardware |
| [M2 Conversations](milestones/02-conversations.md) | Ready for verification | Passed | Passed | Not run | Pending hardware |
| [M3 Horizontal trace](milestones/03-turn-trace.md) | Not started | Not run | Not run | Not run | Pending |
| [M4A Audio](milestones/04-audio-review.md) | Not started | Not run | Not run | Not run | Pending |
| [M4B Images](milestones/04b-image-review.md) | Not started | Not run | Not run | Not run | Pending |
| [M4C Video](milestones/04c-video-review.md) | Not started | Not run | Not run | Not run | Pending |
| [M5 Processing](milestones/05-processing.md) | Not started | Not run | Not run | Not run | Pending |
| [M6 Robot outcomes](milestones/06-robot-outcomes.md) | Not started | Not run | Not run | Not run | Pending |

## Dependencies to resolve

- Verified host: macOS arm64, Docker Engine 29.6.2 / Compose 5.3.1; Linux arm64 image. Other architectures unverified.
- A3 Ultra firmware, developer entitlement, regional gateway, application credentials and isolated test-agent association. Keep credentials out of chat.
- SDK installed and locked at 1.5.0a1; real agent callback/input configuration remains pending.
- Live Ollama model/server for M2 (adapter and isolated HTTP-contract tests implemented); ASR/TTS for M4A; optional vision provider if image-based answers are added.
- Actual raw audio/image/video formats, timing and robot-state publication. Built-in conversation observation is unproven.

## Next concrete action

Configure/confirm an isolated ASR-text developer agent for the A3 Ultra and a reachable Ollama model. Keep credentials in `.env`. Complete M1's real connection/reconnect/input check, then explicitly connect M2 replies, capture three real interactions, save a checkpoint and verify after recreation. Physical playback stays unknown without separate evidence. M3 can build on the fixture-ready text store while hardware gates remain pending.

M2 changed paths: `src/linksoul_studio/{conversations,recorder,provider,app,service,robot,config}.py`, web templates/static, `tests/test_m2.py`, version/lock, Compose/environment and handoff docs. Schema 1 adds SQLite without changing M1 evidence. Run commands, versions, report IDs, limits and backup/rollback are in the linked validation and deployment records.

## Update after every milestone

Record changed paths, exact run/build commands, versions, tests actually run, saved evidence references, remaining limitations and one next concrete action. Use implementation states `Not started`, `In progress`, `Ready for verification`, `Implemented`; checks use `Not run`, `Passed`, `Failed`, `Unsupported`. Acceptance remains pending until the contract's gate has evidence, regardless of fixture success.
